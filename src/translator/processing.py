from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Callable, Sequence

logger = logging.getLogger(__name__)

from .claude_client import ClaudeTranslator
from .docx_io import read_paragraphs
from .pdf_io import read_paragraphs_from_pdf, read_paragraphs_from_txt
from .pdf_writer import write_pdf, write_pdf_to_bytes
from .term_hierarchy import TermTranslation, apply_term_translations, extract_terms, lookup_term_hierarchy
from .term_sources import GlossarySource, MemorySource, PlaceholderSource, TermSourceChain
from .terminology import Glossary, GlossaryMatch, TranslationMemory, TranslationRecord

# Chunking configuration - optimized for speed
MAX_PARAGRAPH_LENGTH = 15_000  # Increased from 10k to reduce number of chunks
CHUNK_OVERLAP = 100  # Reduced from 200 for faster processing

DOCX_SUFFIX = ".docx"
PDF_SUFFIX = ".pdf"
TXT_SUFFIX = ".txt"


ProgressCallback = Callable[[int, int, int], None]
ChunkProgressCallback = Callable[[int, int, int, int, int], None]  # paragraph_idx, chunk_idx, total_chunks, chunk_length, total_paragraphs
TranslationCallback = Callable[[int, str], None]  # paragraph_idx, translated_text


def _split_into_chunks(text: str, max_length: int = MAX_PARAGRAPH_LENGTH, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split long text into smaller chunks with overlap for context preservation.
    
    Tries to split at sentence boundaries when possible.
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    import re
    
    # Try to split at sentence boundaries (., !, ? followed by space)
    sentences = re.split(r'([.!?]\s+)', text)
    current_chunk = ""
    
    for i in range(0, len(sentences), 2):
        sentence = sentences[i] + (sentences[i+1] if i+1 < len(sentences) else "")
        
        # If adding this sentence would exceed max_length, save current chunk
        if current_chunk and len(current_chunk) + len(sentence) > max_length:
            chunks.append(current_chunk.strip())
            # Start new chunk with overlap from previous chunk
            if overlap > 0 and current_chunk:
                overlap_text = current_chunk[-overlap:].strip()
                current_chunk = overlap_text + " " + sentence
            else:
                current_chunk = sentence
        else:
            current_chunk += sentence
    
    # Add remaining chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    # Fallback: if still too long, split by character count
    if not chunks or any(len(chunk) > max_length * 1.5 for chunk in chunks):
        chunks = []
        start = 0
        while start < len(text):
            end = start + max_length
            if end < len(text):
                # Try to find a good break point (space, punctuation)
                for break_char in ['\n\n', '\n', '. ', ' ', '']:
                    break_pos = text.rfind(break_char, start, end)
                    if break_pos > start:
                        end = break_pos + len(break_char)
                        break
            chunks.append(text[start:end].strip())
            start = end - overlap if overlap > 0 and end < len(text) else end
    
    return chunks if chunks else [text]


def _build_term_source_chain(
    glossary: Glossary | None,
    memory: TranslationMemory,
    reference_doc_pairs: dict[str, str] | None = None,
) -> TermSourceChain:
    """
    Build a term source chain with the standard hierarchy.
    
    This function creates the default source chain. To customize the chain
    (e.g., add custom sources, change order), you can:
    
    1. Modify this function to include your custom sources
    2. Or pass a custom TermSourceChain directly to the translation functions
    
    The standard hierarchy is:
    1. Reference Document (highest priority - exact matches from reference doc)
    2. Glossary (exact match)
    3. Translation Memory (similarity)
    4. Placeholder (fallback)
    
    Args:
        glossary: Optional glossary for exact term matching
        memory: Translation memory for similarity search
        reference_doc_pairs: Optional dictionary of translation pairs from reference document
    
    Returns:
        TermSourceChain with sources in priority order
    """
    from .term_sources import ReferenceDocSource
    
    sources = []
    
    # Reference document has highest priority
    if reference_doc_pairs:
        sources.append(ReferenceDocSource(reference_doc_pairs))
    
    # Standard sources
    sources.extend([
        GlossarySource(glossary),
        MemorySource(memory),
        PlaceholderSource(),
    ])
    
    return TermSourceChain(sources)


@dataclass(slots=True)
class TranslationStats:
    paragraphs_total: int
    empty_paragraphs: int = 0
    reused_from_memory: int = 0
    model_calls: int = 0
    glossary_matches: int = 0
    paragraph_logs: list[dict[str, object]] = field(default_factory=list)


@dataclass(slots=True)
class TranslationOutcome:
    input_path: Path
    output_path: Path
    file_type: str
    translations: list[str]
    stats: TranslationStats
    duration_seconds: float


def _translate_paragraphs(
    paragraphs: Sequence[str],
    *,
    translator: ClaudeTranslator,
    glossary: Glossary | None,
    memory: TranslationMemory,
    source_lang: str,
    target_lang: str,
    progress_callback: ProgressCallback | None = None,
    chunk_progress_callback: ChunkProgressCallback | None = None,
    translation_callback: TranslationCallback | None = None,
    skip_memory: bool = False,
) -> tuple[list[str], TranslationStats]:
    """Translate paragraphs one by one. Simple and straightforward."""
    logger.info(f"Translating {len(paragraphs)} paragraphs: {source_lang} -> {target_lang}")
    stats = TranslationStats(paragraphs_total=len(paragraphs))
    translated: list[str] = []
    
    for idx, paragraph in enumerate(paragraphs, start=1):
        text = paragraph.strip()
        paragraph_log = {
            "index": idx,
            "length": len(paragraph),
            "source_preview": text[:120],
            "used_memory": False,
            "model_called": False,
        }
        
        # Skip empty paragraphs
        if not text:
            logger.debug(f"Paragraph {idx}: empty, skipping")
            stats.empty_paragraphs += 1
            translated.append(paragraph)
            stats.paragraph_logs.append(paragraph_log)
            if progress_callback:
                progress_callback(idx, len(paragraphs), 0)
            continue
        
        # Check memory first (unless skipped)
        memory_hit = None if skip_memory else memory.get(text, source_lang, target_lang)
        
        if memory_hit:
            # Use cached translation
            logger.info(f"Paragraph {idx}: using memory cache")
            translated_text = memory_hit.translated_text
            stats.reused_from_memory += 1
            paragraph_log["used_memory"] = True
        else:
            # Need to translate
            logger.info(f"Paragraph {idx}: translating ({len(text)} chars)")
            
            # Get glossary matches
            glossary_matches = glossary.matches_in_text(text) if glossary else []
            stats.glossary_matches += len(glossary_matches)
            
            # Get memory suggestions
            memory_suggestions = memory.similar(text, source_lang, target_lang, limit=3, threshold=80.0) if not skip_memory else []
            
            # Split if too long
            chunks = _split_into_chunks(text, MAX_PARAGRAPH_LENGTH, CHUNK_OVERLAP)
            
            if len(chunks) > 1:
                # Translate chunks and combine
                logger.info(f"Paragraph {idx}: splitting into {len(chunks)} chunks")
                translated_chunks = []
                for chunk_idx, chunk in enumerate(chunks, 1):
                    logger.info(f"Paragraph {idx}: translating chunk {chunk_idx}/{len(chunks)}")
                    chunk_matches = glossary.matches_in_text(chunk) if glossary else []
                    chunk_suggestions = memory.similar(chunk, source_lang, target_lang, limit=2, threshold=75.0) if not skip_memory else []
                    chunk_translated = translator.translate_paragraph(
                        paragraph=chunk,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        glossary_matches=chunk_matches,
                        memory_hits=chunk_suggestions,
                    )
                    translated_chunks.append(chunk_translated)
                    stats.model_calls += 1
                    if not skip_memory:
                        memory.record(chunk, chunk_translated, source_lang, target_lang)
                
                # Combine chunks (simple join, overlap handled by translator)
                translated_text = " ".join(translated_chunks)
            else:
                # Single chunk
                translated_text = translator.translate_paragraph(
                    paragraph=text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    glossary_matches=glossary_matches,
                    memory_hits=memory_suggestions,
                )
                stats.model_calls += 1
                if not skip_memory:
                    memory.record(text, translated_text, source_lang, target_lang)
            
            paragraph_log["model_called"] = True
            logger.info(f"Paragraph {idx}: complete ({len(translated_text)} chars)")
        
        # Store result
        paragraph_log["output_preview"] = translated_text[:120]
        translated.append(translated_text)
        stats.paragraph_logs.append(paragraph_log)
        
        # Update progress (may raise KeyboardInterrupt if cancelled)
        if progress_callback:
            try:
                progress_callback(idx, len(paragraphs), len(text))
            except KeyboardInterrupt:
                logger.info(f"Translation cancelled at paragraph {idx}")
                raise
    
    logger.info(f"Translation complete: {stats.model_calls} API calls, {stats.reused_from_memory} from memory")
    return translated, stats


def _read_input_file(input_path: Path) -> tuple[list[str], str]:
    import hashlib
    
    logger.info(f"[_read_input_file] ===== STARTING FILE READ =====")
    logger.info(f"[_read_input_file] Input path: {input_path}")
    logger.info(f"[_read_input_file] Absolute path: {input_path.resolve()}")
    logger.info(f"[_read_input_file] File exists: {input_path.exists()}")
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")
    
    # Read file content and compute hash BEFORE parsing
    with open(input_path, 'rb') as f:
        raw_content = f.read()
        file_hash = hashlib.md5(raw_content).hexdigest()
    
    logger.info(f"[_read_input_file] File size: {len(raw_content):,} bytes")
    logger.info(f"[_read_input_file] File hash: {file_hash}")
    logger.info(f"[_read_input_file] First 200 bytes: {raw_content[:200]}")
    
    suffix = input_path.suffix.lower()
    logger.info(f"[_read_input_file] File suffix: {suffix}")
    
    if suffix == DOCX_SUFFIX:
        logger.info(f"[_read_input_file] Detected DOCX format, hash: {file_hash[:16]}...")
        paragraphs = read_paragraphs(input_path)
        logger.info(f"[_read_input_file] Read {len(paragraphs)} paragraphs from DOCX")
        if paragraphs:
            logger.info(f"[_read_input_file] First paragraph preview: {paragraphs[0][:100]}...")
        return paragraphs, "DOCX"
    if suffix == ".pdf":
        logger.info(f"[_read_input_file] Detected PDF format, hash: {file_hash[:16]}...")
        paragraphs = read_paragraphs_from_pdf(input_path)
        logger.info(f"[_read_input_file] Read {len(paragraphs)} paragraphs from PDF")
        if paragraphs:
            logger.info(f"[_read_input_file] First paragraph preview: {paragraphs[0][:100]}...")
        return paragraphs, "PDF"
    if suffix == TXT_SUFFIX:
        logger.info(f"[_read_input_file] Detected TXT format, hash: {file_hash[:16]}...")
        paragraphs = read_paragraphs_from_txt(input_path)
        logger.info(f"[_read_input_file] Read {len(paragraphs)} paragraphs from TXT")
        if paragraphs:
            logger.info(f"[_read_input_file] First paragraph preview: {paragraphs[0][:100]}...")
        return paragraphs, "TXT"
    
    logger.error(f"[_read_input_file] Unsupported file type: {suffix}")
    raise ValueError("Unsupported file type. Use DOCX, PDF, or TXT.")


def translate_file(
    input_path: Path,
    *,
    output_path: Path,
    glossary: Glossary | None,
    memory: TranslationMemory,
    translator: ClaudeTranslator,
    source_lang: str,
    target_lang: str,
    progress_callback: ProgressCallback | None = None,
    chunk_progress_callback: ChunkProgressCallback | None = None,
    translation_callback: TranslationCallback | None = None,
    skip_memory: bool = False,
) -> TranslationOutcome:
    """Simple translation: read file, translate paragraphs, write PDF."""
    import hashlib
    
    logger.info(f"[translate_file] ===== STARTING TRANSLATION =====")
    logger.info(f"[translate_file] Input path: {input_path}")
    logger.info(f"[translate_file] Absolute path: {input_path.resolve()}")
    logger.info(f"[translate_file] File exists: {input_path.exists()}")
    
    # Verify file hash at the start of translate_file
    if input_path.exists():
        with open(input_path, 'rb') as f:
            verify_content = f.read()
            verify_hash = hashlib.md5(verify_content).hexdigest()
        logger.info(f"[translate_file] File hash at start: {verify_hash}")
        logger.info(f"[translate_file] File size: {len(verify_content):,} bytes")
    
    logger.info(f"[translate_file] Calling _read_input_file")
    paragraphs, file_type = _read_input_file(input_path)
    
    if not paragraphs:
        raise ValueError("No text found to translate.")

    output = output_path if output_path.suffix.lower() == PDF_SUFFIX else output_path.with_suffix(PDF_SUFFIX)
    logger.info(f"Output: {output}")

    start = perf_counter()
    translations, stats = _translate_paragraphs(
        paragraphs,
        translator=translator,
        glossary=glossary,
        memory=memory,
        source_lang=source_lang,
        target_lang=target_lang,
        progress_callback=progress_callback,
        skip_memory=skip_memory,
    )
    duration = perf_counter() - start

    logger.info(f"Writing PDF: {output}")
    write_pdf(translations, output)
    logger.info(f"Complete: {duration:.2f}s, {len(translations)} paragraphs")

    return TranslationOutcome(
        input_path=input_path,
        output_path=output,
        file_type=file_type,
        translations=translations,
        stats=stats,
        duration_seconds=duration,
    )


def extract_translation_pairs_from_reference_doc(
    reference_doc_path: Path,
    translator: ClaudeTranslator,
    source_lang: str,
    target_lang: str,
) -> dict[str, str]:
    """
    Extract translation pairs from a reference document using Claude.
    
    The reference document should contain examples of how terms/phrases were translated.
    Claude will analyze it and extract source->target translation pairs.
    
    Args:
        reference_doc_path: Path to reference document (DOCX, PDF, or TXT)
        translator: Claude translator instance
        source_lang: Source language code
        target_lang: Target language code
    
    Returns:
        Dictionary mapping source terms (lowercase) to target translations
    """
    logger.info(f"[extract_translation_pairs] Extracting translation pairs from reference doc: {reference_doc_path}")
    
    # Read reference document text
    reference_text = _read_file_as_text(reference_doc_path)
    
    if not reference_text or len(reference_text.strip()) < 50:
        logger.warning(f"[extract_translation_pairs] Reference doc has insufficient text ({len(reference_text)} chars)")
        return {}
    
    # Use Claude to extract translation pairs
    extraction_prompt = f"""You are analyzing a reference document that shows translation guidelines and examples.

Your task is to extract translation pairs (source term/phrase -> target translation) from this document.

The document is written in {source_lang} and contains translations to {target_lang}.

Extract ALL translation pairs you can find. Look for:
- Direct translations (e.g., "Appartement" -> "Apartment" or "dog")
- Translation guidelines (e.g., "translate X as Y")
- Side-by-side comparisons
- Any examples showing how terms were translated

Return ONLY a JSON object with this exact format:
{{
  "pairs": [
    {{"source": "source term", "target": "target translation"}},
    {{"source": "another term", "target": "another translation"}}
  ]
}}

Be thorough - extract as many pairs as possible. Include phrases, not just single words.

Reference document:
{reference_text[:10000]}  # Limit to first 10k chars to avoid token limits
"""
    
    try:
        # Use Claude to extract pairs
        response = translator._client.messages.create(
            model=translator.model,
            max_tokens=4096,
            messages=[
                {"role": "user", "content": extraction_prompt}
            ]
        )
        
        import json
        import re
        
        # Extract JSON from response
        content = response.content[0].text
        # Try to find JSON in the response
        json_match = re.search(r'\{[^{}]*"pairs"[^{}]*\[.*?\]\s*\}', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            data = json.loads(json_str)
            pairs = data.get("pairs", [])
            
            # Build dictionary
            translation_pairs = {}
            for pair in pairs:
                source = pair.get("source", "").strip().lower()
                target = pair.get("target", "").strip()
                if source and target:
                    translation_pairs[source] = target
            
            logger.info(f"[extract_translation_pairs] Extracted {len(translation_pairs)} translation pairs from reference doc")
            return translation_pairs
        else:
            logger.warning(f"[extract_translation_pairs] Could not parse JSON from Claude response")
            return {}
            
    except Exception as e:
        logger.error(f"[extract_translation_pairs] Error extracting pairs: {e}", exc_info=True)
        return {}


def _read_file_as_text(input_path: Path) -> str:
    """Read entire file as raw text without parsing into paragraphs."""
    import hashlib
    import logging
    
    logger = logging.getLogger(__name__)
    suffix = input_path.suffix.lower()
    
    logger.info(f"[_read_file_as_text] Reading entire file as text: {input_path}")
    logger.info(f"[_read_file_as_text] File type: {suffix}")
    
    # Read raw file content
    with open(input_path, 'rb') as f:
        raw_content = f.read()
        file_hash = hashlib.md5(raw_content).hexdigest()
    
    logger.info(f"[_read_file_as_text] File hash: {file_hash}")
    logger.info(f"[_read_file_as_text] File size: {len(raw_content):,} bytes")
    
    # Extract text based on file type
    if suffix == ".docx":
        from docx import Document
        doc = Document(input_path)
        # Join all paragraphs with double newlines
        text = "\n\n".join(para.text for para in doc.paragraphs if para.text.strip())
    elif suffix == ".pdf":
        import pdfplumber
        text_parts = []
        with pdfplumber.open(input_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    text_parts.append(page_text)
        text = "\n\n".join(text_parts)
    elif suffix == ".txt":
        with open(input_path, 'r', encoding='utf-8') as f:
            text = f.read()
    else:
        raise ValueError(f"Unsupported file type: {suffix}")
    
    logger.info(f"[_read_file_as_text] Extracted text length: {len(text):,} characters")
    logger.info(f"[_read_file_as_text] First 200 chars: {text[:200]}...")
    
    return text


def translate_file_to_memory(
    input_path: Path,
    *,
    glossary: Glossary | None,
    memory: TranslationMemory,
    translator: ClaudeTranslator,
    source_lang: str,
    target_lang: str,
    progress_callback: ProgressCallback | None = None,
    skip_memory: bool = False,
    reference_doc_pairs: dict[str, str] | None = None,
) -> tuple[bytes, list[str], dict]:
    """
    Translate entire file in a single API call - no chunking, no paragraph splitting.
    Returns: (pdf_bytes, translated_paragraphs, report_dict)
    """
    import hashlib
    from datetime import datetime, timezone
    
    logger.info(f"[translate_file_to_memory] ===== STARTING SINGLE-SHOT TRANSLATION =====")
    logger.info(f"[translate_file_to_memory] Input path: {input_path}")
    logger.info(f"[translate_file_to_memory] Absolute path: {input_path.resolve()}")
    
    # Verify file hash
    if input_path.exists():
        with open(input_path, 'rb') as f:
            verify_content = f.read()
            verify_hash = hashlib.md5(verify_content).hexdigest()
        logger.info(f"[translate_file_to_memory] File hash: {verify_hash}")
        logger.info(f"[translate_file_to_memory] File size: {len(verify_content):,} bytes")
    
    # Read entire file as text (no paragraph parsing)
    logger.info(f"[translate_file_to_memory] Reading entire file as text...")
    document_text = _read_file_as_text(input_path)
    
    if not document_text or not document_text.strip():
        raise ValueError("No text found to translate.")

    # Apply reference document translations first (highest priority)
    reference_doc_matches = []
    reference_doc_applied = {}
    if reference_doc_pairs:
        logger.info(f"[translate_file_to_memory] ===== APPLYING REFERENCE DOCUMENT TRANSLATIONS =====")
        logger.info(f"[translate_file_to_memory] Reference doc has {len(reference_doc_pairs)} translation pairs")
        
        # Find terms in document that match reference doc pairs
        import re
        normalized_doc = document_text.lower()
        for source_term, target_term in reference_doc_pairs.items():
            # Case-insensitive search for the source term
            pattern = re.compile(re.escape(source_term), re.IGNORECASE)
            matches = pattern.findall(document_text)
            if matches:
                reference_doc_matches.append({
                    "source": source_term,
                    "target": target_term,
                    "count": len(matches)
                })
                reference_doc_applied[source_term.lower()] = target_term
                logger.info(f"[translate_file_to_memory] Reference doc: '{source_term}' -> '{target_term}' (found {len(matches)} times)")
        
        logger.info(f"[translate_file_to_memory] Applied {len(reference_doc_applied)} reference doc translations")
    
    # Get glossary matches for entire document (excluding terms already in reference doc)
    glossary_matches = []
    if glossary:
        logger.info(f"[translate_file_to_memory] Looking up glossary matches...")
        all_glossary_matches = glossary.matches_in_text(document_text)
        # Filter out matches that conflict with reference doc
        for match in all_glossary_matches:
            term_lower = match.entry.term.lower()
            if term_lower not in reference_doc_applied:
                glossary_matches.append(match)
            else:
                logger.info(f"[translate_file_to_memory] Skipping glossary match '{match.entry.term}' (overridden by reference doc)")
        logger.info(f"[translate_file_to_memory] Found {len(glossary_matches)} glossary matches (after filtering reference doc conflicts)")
    
    # STEP 1: Check translation memory first (if memory is enabled)
    translated_text = None
    memory_used = False
    memory_hits = []
    memory_record_used = None  # Store the memory record if entire translation came from memory
    
    if not skip_memory:
        logger.info(f"[translate_file_to_memory] ===== STEP 1: CHECKING TRANSLATION MEMORY =====")
        logger.info(f"[translate_file_to_memory] Memory enabled (skip_memory=False), checking for existing translation...")
        logger.info(f"[translate_file_to_memory] Document length: {len(document_text):,} characters")
        
        # Look for high-similarity matches (95%+ threshold for direct use)
        memory_hits = memory.similar(document_text, source_lang, target_lang, limit=1, threshold=95.0)
        
        if memory_hits and len(memory_hits) > 0:
            best_match = memory_hits[0]
            # Check similarity score - if very high, use memory directly
            from rapidfuzz import fuzz
            similarity_score = fuzz.token_set_ratio(document_text, best_match.source_text)
            
            logger.info(f"[translate_file_to_memory] Found memory match with similarity: {similarity_score}%")
            logger.info(f"[translate_file_to_memory] Memory source preview: {best_match.source_text[:150]}...")
            logger.info(f"[translate_file_to_memory] Memory translation preview: {best_match.translated_text[:150]}...")
            
            if similarity_score >= 95.0:
                translated_text = best_match.translated_text
                # CRITICAL FIX: Remove ReportLab XML tags (<para>, </para>) from memory content
                # These tags should not be in memory, but if they are (from a previous bug), remove them
                if '<para>' in translated_text or '</para>' in translated_text:
                    translated_text = re.sub(r'</?para>', '', translated_text, flags=re.IGNORECASE)
                    logger.warning(f"[translate_file_to_memory] Removed <para> tags from memory content (should not have been there)")
                memory_used = True
                memory_record_used = best_match  # Store for highlighting
                logger.info(f"[translate_file_to_memory] ✅ STEP 1 RESULT: Using translation from memory (similarity: {similarity_score}%)")
                logger.info(f"[translate_file_to_memory] ✅ No Claude API call needed - translation retrieved from memory")
            else:
                logger.info(f"[translate_file_to_memory] ⚠️ STEP 1 RESULT: Memory match similarity too low ({similarity_score}% < 95%)")
                logger.info(f"[translate_file_to_memory] ⚠️ Will proceed to STEP 2: Query Claude API")
                # Get more memory hits for Claude context
                memory_hits = memory.similar(document_text, source_lang, target_lang, limit=10, threshold=80.0)
                logger.info(f"[translate_file_to_memory] Found {len(memory_hits)} memory hits for Claude context")
        else:
            logger.info(f"[translate_file_to_memory] ⚠️ STEP 1 RESULT: No memory matches found (threshold: 95%)")
            logger.info(f"[translate_file_to_memory] ⚠️ Will proceed to STEP 2: Query Claude API")
            # Get memory hits for Claude context anyway (lower threshold)
            memory_hits = memory.similar(document_text, source_lang, target_lang, limit=10, threshold=80.0)
            logger.info(f"[translate_file_to_memory] Found {len(memory_hits)} memory hits for Claude context (threshold: 80%)")
    else:
        logger.info(f"[translate_file_to_memory] ===== STEP 1: SKIPPED (skip_memory=True) =====")
        logger.info(f"[translate_file_to_memory] Translation memory disabled, proceeding directly to Claude API")
    
    # STEP 2: If memory wasn't used, call Claude API
    if not memory_used:
        logger.info(f"[translate_file_to_memory] ===== STEP 2: QUERYING CLAUDE API =====")
        # Update progress
        if progress_callback:
            progress_callback(1, 1, len(document_text))
        
        # Translate entire document in single API call
        logger.info(f"[translate_file_to_memory] Sending entire document to Claude API (single call)")
        logger.info(f"[translate_file_to_memory] Document length: {len(document_text):,} characters")
        logger.info(f"[translate_file_to_memory] Glossary matches: {len(glossary_matches)}")
        logger.info(f"[translate_file_to_memory] Memory hits for context: {len(memory_hits)}")
        
        start = perf_counter()
        translated_text = translator.translate_document(
            document_text=document_text,
            source_lang=source_lang,
            target_lang=target_lang,
            glossary_matches=glossary_matches,
            memory_hits=memory_hits,
            reference_doc_pairs=reference_doc_applied if reference_doc_pairs else None,
        )
        duration = perf_counter() - start
        
        logger.info(f"[translate_file_to_memory] ✅ STEP 2 RESULT: Claude API translation completed in {duration:.2f}s")
        logger.info(f"[translate_file_to_memory] Translated length: {len(translated_text):,} characters")
        
        # STEP 3: Store translation in memory for future use
        if not skip_memory:
            logger.info(f"[translate_file_to_memory] ===== STEP 3: STORING TRANSLATION IN MEMORY =====")
            logger.info(f"[translate_file_to_memory] Storing translation in memory for future use...")
            logger.info(f"[translate_file_to_memory] Source text length: {len(document_text):,} characters")
            logger.info(f"[translate_file_to_memory] Translated text length: {len(translated_text):,} characters")
            
            try:
                # CRITICAL FIX: Remove ReportLab XML tags before storing in memory
                # Ensure memory never contains <para> tags
                cleaned_translated_text = re.sub(r'</?para>', '', translated_text, flags=re.IGNORECASE)
                memory.record(document_text, cleaned_translated_text, source_lang, target_lang)
                logger.info(f"[translate_file_to_memory] ✅ STEP 3 RESULT: Translation stored in memory successfully")
                logger.info(f"[translate_file_to_memory] Memory file: {memory.path}")
                logger.info(f"[translate_file_to_memory] Total records in memory: {len(memory._records)}")
            except Exception as e:
                logger.error(f"[translate_file_to_memory] ❌ STEP 3 ERROR: Failed to store translation in memory: {e}")
                logger.exception(e)
        else:
            logger.info(f"[translate_file_to_memory] ===== STEP 3: SKIPPED (skip_memory=True) =====")
            logger.info(f"[translate_file_to_memory] Translation memory disabled, not storing translation")
    else:
        # Memory was used - simulate duration for reporting
        duration = 0.1  # Very fast since no API call
        logger.info(f"[translate_file_to_memory] ===== STEP 2: SKIPPED (using memory translation) =====")
        logger.info(f"[translate_file_to_memory] No Claude API call needed - translation retrieved from memory")
        logger.info(f"[translate_file_to_memory] ===== STEP 3: SKIPPED (translation already in memory) =====")
        logger.info(f"[translate_file_to_memory] Translation already exists in memory, no need to store again")

    logger.info(f"[translate_file_to_memory] Translation complete: {duration:.2f}s")
    logger.info(f"[translate_file_to_memory] Translated length: {len(translated_text):,} characters")

    # Apply reference document translations to ensure they're used (highest priority)
    # Note: Reference doc pairs are already in Claude's prompt, but we verify and track usage here
    applied_reference_doc_terms = []
    if reference_doc_pairs and reference_doc_matches:
        logger.info(f"[translate_file_to_memory] ===== VERIFYING REFERENCE DOC TRANSLATIONS =====")
        import re
        enriched_text = translated_text
        
        # Check which reference doc terms were found and track overrides
        for match_info in reference_doc_matches:
            source_term = match_info["source"]
            target_term = match_info["target"]
            
            # Check if this overrode glossary or memory
            overridden_glossary = any(m.entry.term.lower() == source_term.lower() for m in glossary_matches)
            overridden_memory = False
            if memory_hits:
                # Check if any memory hit contains this source term
                for mem_hit in memory_hits:
                    if source_term.lower() in mem_hit.source_text.lower():
                        overridden_memory = True
                        break
            
            applied_reference_doc_terms.append({
                "source": source_term,
                "target": target_term,
                "count": match_info["count"],
                "overridden_glossary": overridden_glossary,
                "overridden_memory": overridden_memory,
            })
            logger.info(f"[translate_file_to_memory] Reference doc: '{source_term}' -> '{target_term}' (found {match_info['count']} times, overrode glossary: {overridden_glossary}, memory: {overridden_memory})")
        
        logger.info(f"[translate_file_to_memory] Tracked {len(applied_reference_doc_terms)} reference doc translation applications")
        enriched_text = translated_text  # Claude should have already applied them via prompt
    else:
        enriched_text = translated_text
    
    # Apply reference doc highlighting first (highest priority)
    from .glossary_enricher import apply_glossary_with_highlighting, apply_memory_with_highlighting, apply_reference_doc_with_highlighting
    if reference_doc_pairs:
        enriched_text, applied_reference_doc_highlighting = apply_reference_doc_with_highlighting(
            translated_text=enriched_text,
            reference_doc_pairs=reference_doc_pairs,
        )
        logger.info(f"[translate_file_to_memory] Reference doc highlighting: {len(applied_reference_doc_highlighting)} terms highlighted")
    else:
        applied_reference_doc_highlighting = []
    
    # Apply glossary to enrich translation and highlight terms (excluding reference doc terms)
    enriched_text, applied_glossary_terms = apply_glossary_with_highlighting(
        translated_text=enriched_text,
        glossary=glossary,
        source_lang=source_lang,
        target_lang=target_lang,
    )
    # Filter out glossary terms that were overridden by reference doc
    applied_glossary_terms = [t for t in applied_glossary_terms 
                             if t.get("term", "").lower() not in reference_doc_applied]
    logger.info(f"[translate_file_to_memory] Glossary enrichment: {len(applied_glossary_terms)} terms highlighted (after filtering reference doc)")
    
    # Apply translation memory to enrich translation and highlight approved terms
    if not skip_memory:
        enriched_text, applied_memory_terms = apply_memory_with_highlighting(
            translated_text=enriched_text,
            memory=memory,
            source_lang=source_lang,
            target_lang=target_lang,
            original_text=document_text,
            memory_record_used=memory_record_used if memory_used else None,
        )
        logger.info(f"[translate_file_to_memory] Memory enrichment: {len(applied_memory_terms)} terms highlighted")
    else:
        applied_memory_terms = []
        logger.info(f"[translate_file_to_memory] Memory enrichment skipped (skip_memory=True)")
    
    # Use enriched text for further processing
    translated_text = enriched_text

    # Split translated text into paragraphs for PDF generation
    # Use double newlines as paragraph separators
    translated_paragraphs = [p.strip() for p in translated_text.split("\n\n") if p.strip()]
    if not translated_paragraphs:
        # Fallback: use single newlines
        translated_paragraphs = [p.strip() for p in translated_text.split("\n") if p.strip()]
    if not translated_paragraphs:
        # Last resort: entire text as one paragraph
        translated_paragraphs = [translated_text]
    
    # Split source document text into paragraphs for side-by-side display
    source_paragraphs = [p.strip() for p in document_text.split("\n\n") if p.strip()]
    if not source_paragraphs:
        # Fallback: use single newlines
        source_paragraphs = [p.strip() for p in document_text.split("\n") if p.strip()]
    if not source_paragraphs:
        # Last resort: entire text as one paragraph
        source_paragraphs = [document_text]

    # Generate PDF in memory with source and translated content side by side
    logger.info(f"[translate_file_to_memory] Generating PDF from {len(source_paragraphs)} source paragraphs and {len(translated_paragraphs)} translated paragraphs")
    pdf_bytes = write_pdf_to_bytes(
        translated_paragraphs=translated_paragraphs,
        title=f"Translated Document ({source_lang}->{target_lang})",
        source_paragraphs=source_paragraphs,
        source_lang=source_lang,
        target_lang=target_lang,
    )
    logger.info(f"[translate_file_to_memory] PDF generated: {len(pdf_bytes):,} bytes")

    # Build report
    report = {
        "input_file": str(input_path),
        "file_type": input_path.suffix.lower().replace(".", "").upper(),
        "source_lang": source_lang,
        "target_lang": target_lang,
        "duration_seconds": round(duration, 3),
        "pdf_size_bytes": len(pdf_bytes),
        "translation_method": "memory" if memory_used else "single_shot",  # Indicate source
        "memory_used": memory_used,  # Flag if memory was used instead of Claude
        "stats": {
            "paragraphs_total": len(translated_paragraphs),
            "empty_paragraphs": 0,
            "reused_from_memory": 1 if memory_used else (1 if memory_hits else 0),
            "model_calls": 0 if memory_used else 1,  # No API call if memory used
            "glossary_matches": len(glossary_matches),
            "glossary_applied": len(applied_glossary_terms),
            "document_length_chars": len(document_text),
            "translated_length_chars": len(translated_text),
        },
        "applied_glossary_terms": applied_glossary_terms,
        "applied_memory_terms": applied_memory_terms,
        "applied_reference_doc_terms": applied_reference_doc_terms,
        "reference_doc_pairs_count": len(reference_doc_pairs) if reference_doc_pairs else 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    # Update stats to include reference doc info
    if reference_doc_pairs:
        report["stats"]["reference_doc_matches"] = len(reference_doc_matches)
        report["stats"]["reference_doc_applied"] = len(applied_reference_doc_terms)

    return pdf_bytes, translated_paragraphs, report


def build_report_payload(
    *,
    outcome: TranslationOutcome,
    source_lang: str,
    target_lang: str,
    generated_at: datetime | None = None,
) -> dict:
    timestamp = generated_at or datetime.now(timezone.utc)
    return {
        "input_file": str(outcome.input_path),
        "output_file": str(outcome.output_path),
        "file_type": outcome.file_type,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "duration_seconds": round(outcome.duration_seconds, 3),
        "stats": {
            "paragraphs_total": outcome.stats.paragraphs_total,
            "empty_paragraphs": outcome.stats.empty_paragraphs,
            "reused_from_memory": outcome.stats.reused_from_memory,
            "model_calls": outcome.stats.model_calls,
            "glossary_matches": outcome.stats.glossary_matches,
            "paragraphs": outcome.stats.paragraph_logs,
        },
        "generated_at": timestamp.isoformat(),
    }

