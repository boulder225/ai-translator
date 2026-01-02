from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
import os

from anthropic import Anthropic

from .terminology import GlossaryMatch, TranslationMemory, TranslationRecord

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPT_FILE = PROJECT_ROOT / "prompt.md"
PROMPT_TRANSLATOR_FILE = PROJECT_ROOT / "prompt-translator.md"
PROMPT_REVIEWER_FILE = PROJECT_ROOT / "prompt-reviewer.md"


def _load_prompt_template() -> str:
    if PROMPT_FILE.exists():
        template = PROMPT_FILE.read_text(encoding="utf-8").strip()
        print(f"[prompt] Loaded custom prompt template from {PROMPT_FILE}")
        return template
    return (
        "You are a professional translator. Translate the provided text accurately, "
        "regardless of its context or document type. For legal, insurance, or administrative documents, "
        "use formal professional tone. For other document types, adapt the style appropriately. "
        "Always preserve numbering, respect capitalization, and never add commentary. "
        "Never refuse to translate - always provide a translation."
    )


def _load_prompt_template_for_role(role: str) -> str:
    """
    Load prompt template based on user role.
    - translator role: use default prompt.md
    - reviewer role: use prompt-reviewer.md
    - admin and other roles: use default prompt.md
    Returns role-specific prompt if available, otherwise returns default prompt.
    """
    role_lower = role.strip().lower() if role else ""
    
    if role_lower == "reviewer":
        if PROMPT_REVIEWER_FILE.exists():
            template = PROMPT_REVIEWER_FILE.read_text(encoding="utf-8").strip()
            print(f"[prompt] Loaded reviewer prompt template from {PROMPT_REVIEWER_FILE}")
            return template
        return (
            "You are an expert reviewer specializing in translation quality assurance. "
            "Review the translation for accuracy, completeness, quality, and consistency. "
            "Provide a revised translation that addresses any issues found. "
            "For legal, insurance, or administrative documents, use formal professional tone. "
            "Always preserve numbering, respect capitalization, and never add commentary."
        )
    else:
        # Default prompt for translator, admin, and other roles
        return _load_prompt_template()


PROMPT_TEMPLATE = _load_prompt_template()


def _format_glossary(matches: Sequence[GlossaryMatch]) -> str:
    if not matches:
        return "- (none)"
    lines = []
    # Limit glossary to prevent prompt bloat (reduced for faster processing)
    MAX_GLOSSARY_ENTRIES = 20  # Reduced from 50 for faster API calls
    MAX_GLOSSARY_LENGTH = 5_000  # Reduced from 10k
    for match in matches[:MAX_GLOSSARY_ENTRIES]:
        context = f" ({match.entry.context})" if match.entry.context else ""
        lines.append(f"- {match.entry.term} -> {match.entry.translation}{context}")
    result = "\n".join(lines)
    if len(result) > MAX_GLOSSARY_LENGTH:
        result = result[:MAX_GLOSSARY_LENGTH] + "\n[... glossary truncated ...]"
    elif len(matches) > MAX_GLOSSARY_ENTRIES:
        result += f"\n[... {len(matches) - MAX_GLOSSARY_ENTRIES} more glossary entries ...]"
    return result


def _format_memory(records: Sequence[TranslationRecord]) -> str:
    if not records:
        return "- (none)"
    lines = []
    # Limit memory to prevent prompt bloat (reduced for faster processing)
    MAX_MEMORY_ENTRIES = 5  # Reduced from 10 for faster API calls
    MAX_MEMORY_LENGTH = 8_000  # Reduced from 20k
    for record in records[:MAX_MEMORY_ENTRIES]:
        # Truncate individual memory entries if too long
        source = record.source_text[:500] + "..." if len(record.source_text) > 500 else record.source_text
        translated = record.translated_text[:500] + "..." if len(record.translated_text) > 500 else record.translated_text
        lines.append(f"- {source} -> {translated}")
    result = "\n".join(lines)
    if len(result) > MAX_MEMORY_LENGTH:
        result = result[:MAX_MEMORY_LENGTH] + "\n[... memory truncated ...]"
    elif len(records) > MAX_MEMORY_ENTRIES:
        result += f"\n[... {len(records) - MAX_MEMORY_ENTRIES} more memory entries ...]"
    return result


DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")


@dataclass
class ClaudeTranslator:
    api_key: str
    model: str = DEFAULT_MODEL
    max_tokens: int = 8192  # Increased from 512 for faster, complete responses
    dry_run: bool = False
    use_file_attachments: bool = False  # Experimental: use file attachments for large texts
    custom_prompt_template: str | None = None  # Optional custom prompt template

    def __post_init__(self) -> None:
        if not self.dry_run and not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required unless dry_run is enabled.")
        self._client = Anthropic(api_key=self.api_key) if not self.dry_run else None
        # Use custom prompt if provided, otherwise use default
        self._prompt_template = self.custom_prompt_template or PROMPT_TEMPLATE

    def translate_paragraph(
        self,
        paragraph: str,
        *,
        source_lang: str,
        target_lang: str,
        glossary_matches: Sequence[GlossaryMatch],
        memory_hits: Sequence[TranslationRecord],
    ) -> str:
        if not paragraph.strip():
            return paragraph
        
        # Safety check: truncate extremely long paragraphs to avoid token limit errors
        # Claude has ~200k token limit (~800k chars total)
        # Leave room for prompt template, glossary, and memory sections
        # Be very conservative: max 100k chars for paragraph (~25k tokens)
        MAX_PARAGRAPH_LENGTH = 100_000
        paragraph_text = paragraph.strip()
        if len(paragraph_text) > MAX_PARAGRAPH_LENGTH:
            logger.warning(
                f"Paragraph too long ({len(paragraph_text)} chars), truncating to {MAX_PARAGRAPH_LENGTH} chars"
            )
            paragraph_text = paragraph_text[:MAX_PARAGRAPH_LENGTH] + "\n[... truncated ...]"
        
        # Format glossary and memory
        glossary_section = _format_glossary(glossary_matches)
        memory_section = _format_memory(memory_hits)
        
        prompt = _build_prompt(
            base_template=self._prompt_template,
            source_lang=source_lang,
            target_lang=target_lang,
            glossary_section=glossary_section,
            memory_section=memory_section,
            paragraph=paragraph_text,
        )
        
        # Final safety check: estimate total prompt size
        # Rough estimate: ~4 chars per token, 200k token limit = ~800k chars
        # Be conservative and warn if approaching limit
        TOTAL_PROMPT_LIMIT = 700_000  # Leave safety margin
        if len(prompt) > TOTAL_PROMPT_LIMIT:
            logger.error(
                f"Total prompt too long ({len(prompt)} chars, limit: {TOTAL_PROMPT_LIMIT}). "
                f"Template: {len(self._prompt_template)}, Glossary: {len(glossary_section)}, "
                f"Memory: {len(memory_section)}, Paragraph: {len(paragraph_text)}"
            )
            # Emergency truncation: reduce paragraph further
            remaining = TOTAL_PROMPT_LIMIT - len(self._prompt_template) - len(glossary_section) - len(memory_section) - 1000
            if remaining > 1000:
                paragraph_text = paragraph_text[:remaining] + "\n[... emergency truncation ...]"
                prompt = _build_prompt(
                    base_template=self._prompt_template,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    glossary_section=glossary_section,
                    memory_section=memory_section,
                    paragraph=paragraph_text,
                )
            else:
                raise ValueError(
                    f"Prompt too long even after truncation. "
                    f"Template alone is {len(self._prompt_template)} chars. "
                    f"Consider splitting the document or reducing glossary/memory size."
                )
        
        if self.dry_run:
            return f"[{target_lang} draft] {paragraph}"
        
        # Detailed logging of request
        prompt_length = len(prompt)
        paragraph_length = len(paragraph_text)
        glossary_length = len(glossary_section)
        memory_length = len(memory_section)
        template_length = len(PROMPT_TEMPLATE)
        
        # Estimate token count (rough: ~4 chars per token)
        estimated_tokens = prompt_length // 4
        
        logger.info("=" * 80)
        logger.info("🚀 CLAUDE API REQUEST DETAILS")
        logger.info("=" * 80)
        logger.info(f"Model: {self.model}")
        logger.info(f"Max tokens: {self.max_tokens}")
        logger.info(f"Total prompt length: {prompt_length:,} characters (~{estimated_tokens:,} tokens)")
        logger.info(f"  - Template: {template_length:,} chars")
        logger.info(f"  - Glossary: {glossary_length:,} chars ({len(glossary_matches)} entries)")
        logger.info(f"  - Memory: {memory_length:,} chars ({len(memory_hits)} entries)")
        logger.info(f"  - Paragraph to translate: {paragraph_length:,} chars")
        logger.info(f"  - Other (instructions, formatting): {prompt_length - template_length - glossary_length - memory_length - paragraph_length:,} chars")
        logger.info(f"Source language: {source_lang} -> Target language: {target_lang}")
        logger.info("-" * 80)
        logger.info(f"📝 PARAGRAPH PREVIEW (first 500 chars):")
        logger.info(f"{paragraph_text[:500]}...")
        logger.info("-" * 80)
        logger.info("⏱️  Sending request to Claude API...")
        
        import time
        start_time = time.time()

        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
                timeout=300.0,  # Reduced to 5 minutes for faster failure detection
            )
            elapsed_time = time.time() - start_time
            translated = response.content[0].text.strip()
            translated_length = len(translated)
            
            # Log response details
            logger.info("=" * 80)
            logger.info("✅ CLAUDE API RESPONSE RECEIVED")
            logger.info("=" * 80)
            logger.info(f"⏱️  Request duration: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)")
            logger.info(f"📊 Response length: {translated_length:,} characters")
            if hasattr(response, 'usage'):
                logger.info(f"📈 Token usage:")
                logger.info(f"  - Input tokens: {getattr(response.usage, 'input_tokens', 'N/A')}")
                logger.info(f"  - Output tokens: {getattr(response.usage, 'output_tokens', 'N/A')}")
            logger.info(f"📝 TRANSLATION PREVIEW (first 500 chars):")
            logger.info(f"{translated[:500]}...")
            logger.info("=" * 80)
            
            return translated
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error("=" * 80)
            logger.error("❌ CLAUDE API CALL FAILED")
            logger.error("=" * 80)
            logger.error(f"⏱️  Failed after: {elapsed_time:.2f} seconds")
            logger.error(f"❌ Error type: {type(e).__name__}")
            logger.error(f"❌ Error message: {str(e)}")
            logger.error(f"📝 Request details:")
            logger.error(f"  - Prompt length: {prompt_length:,} chars (~{estimated_tokens:,} tokens)")
            logger.error(f"  - Paragraph length: {paragraph_length:,} chars")
            logger.error(f"  - Model: {self.model}")
            logger.error(f"  - Max tokens: {self.max_tokens}")
            logger.error("=" * 80)
            raise

    def translate_document(
        self,
        document_text: str,
        *,
        source_lang: str,
        target_lang: str,
        glossary_matches: Sequence[GlossaryMatch] | None = None,
        memory_hits: Sequence[TranslationRecord] | None = None,
        reference_doc_pairs: dict[str, str] | None = None,
    ) -> str:
        """
        Translate entire document in a single API call.
        No chunking, no paragraph splitting - send everything at once.
        """
        if not document_text.strip():
            return document_text
        
        glossary_matches = glossary_matches or []
        memory_hits = memory_hits or []
        
        # Format glossary, memory, and reference doc
        glossary_section = _format_glossary(glossary_matches)
        memory_section = _format_memory(memory_hits)
        reference_doc_section = _format_reference_doc(reference_doc_pairs) if reference_doc_pairs else None
        
        # Build prompt with entire document
        prompt = _build_prompt(
            base_template=self._prompt_template,
            source_lang=source_lang,
            target_lang=target_lang,
            glossary_section=glossary_section,
            memory_section=memory_section,
            paragraph=document_text,  # Entire document as "paragraph"
            reference_doc_section=reference_doc_section,
        )
        
        # Safety check for token limits
        TOTAL_PROMPT_LIMIT = 700_000  # Conservative limit
        if len(prompt) > TOTAL_PROMPT_LIMIT:
            logger.warning(
                f"Document very large ({len(document_text):,} chars). "
                f"Total prompt: {len(prompt):,} chars (~{len(prompt)//4:,} tokens). "
                f"Proceeding with single API call..."
            )
        
        if self.dry_run:
            return f"[{target_lang} draft] {document_text}"
        
        prompt_length = len(prompt)
        estimated_tokens = prompt_length // 4
        
        logger.info("=" * 80)
        logger.info("🚀 CLAUDE API REQUEST - ENTIRE DOCUMENT (SINGLE SHOT)")
        logger.info("=" * 80)
        logger.info(f"Model: {self.model}")
        logger.info(f"Max tokens: {self.max_tokens}")
        logger.info(f"Document length: {len(document_text):,} characters")
        logger.info(f"Total prompt length: {prompt_length:,} characters (~{estimated_tokens:,} tokens)")
        logger.info(f"Source language: {source_lang} -> Target language: {target_lang}")
        logger.info(f"Glossary entries: {len(glossary_matches)}")
        logger.info(f"Memory entries: {len(memory_hits)}")
        logger.info("-" * 80)
        logger.info(f"📝 DOCUMENT PREVIEW (first 500 chars):")
        logger.info(f"{document_text[:500]}...")
        logger.info("-" * 80)
        logger.info("⏱️  Sending entire document to Claude API in single call...")
        
        import time
        start_time = time.time()

        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
                timeout=600.0,  # 10 minutes for large documents
            )
            elapsed_time = time.time() - start_time
            translated = response.content[0].text.strip()
            translated_length = len(translated)
            
            logger.info("=" * 80)
            logger.info("✅ CLAUDE API RESPONSE RECEIVED")
            logger.info("=" * 80)
            logger.info(f"⏱️  Request duration: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)")
            logger.info(f"📊 Response length: {translated_length:,} characters")
            if hasattr(response, 'usage'):
                logger.info(f"📈 Token usage:")
                logger.info(f"  - Input tokens: {getattr(response.usage, 'input_tokens', 'N/A')}")
                logger.info(f"  - Output tokens: {getattr(response.usage, 'output_tokens', 'N/A')}")
            logger.info(f"📝 TRANSLATION PREVIEW (first 500 chars):")
            logger.info(f"{translated[:500]}...")
            logger.info("=" * 80)
            
            return translated
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error("=" * 80)
            logger.error("❌ CLAUDE API CALL FAILED")
            logger.error("=" * 80)
            logger.error(f"⏱️  Failed after: {elapsed_time:.2f} seconds")
            logger.error(f"❌ Error type: {type(e).__name__}")
            logger.error(f"❌ Error message: {str(e)}")
            logger.error(f"📝 Request details:")
            logger.error(f"  - Document length: {len(document_text):,} chars")
            logger.error(f"  - Prompt length: {prompt_length:,} chars (~{estimated_tokens:,} tokens)")
            logger.error(f"  - Model: {self.model}")
            logger.error(f"  - Max tokens: {self.max_tokens}")
            logger.error("=" * 80)
            raise

    def translate_document_streaming(
        self,
        document_text: str,
        *,
        source_lang: str,
        target_lang: str,
        glossary_matches: Sequence[GlossaryMatch] | None = None,
        memory_hits: Sequence[TranslationRecord] | None = None,
        reference_doc_pairs: dict[str, str] | None = None,
    ):
        """
        Translate entire document with streaming support.
        Yields chunks of translated text as they arrive from Claude API.

        Yields:
            str: Chunks of translated text
        """
        if not document_text.strip():
            return

        # Build prompt (same as non-streaming version)
        glossary_section = _format_glossary(glossary_matches)
        memory_section = _format_memory(memory_hits)
        reference_doc_section = _format_reference_doc(reference_doc_pairs) if reference_doc_pairs else None

        prompt = _build_prompt(
            base_template=self._prompt_template,
            source_lang=source_lang,
            target_lang=target_lang,
            glossary_section=glossary_section,
            memory_section=memory_section,
            paragraph=document_text,
            reference_doc_section=reference_doc_section,
        )

        prompt_length = len(prompt)
        estimated_tokens = prompt_length // 4

        logger.info("=" * 80)
        logger.info("🔄 STREAMING CLAUDE API REQUEST")
        logger.info("=" * 80)
        logger.info(f"📊 Document details:")
        logger.info(f"  - Document length: {len(document_text):,} characters")
        logger.info(f"  - Source: {source_lang} -> Target: {target_lang}")
        logger.info(f"  - Glossary matches: {len(glossary_matches) if glossary_matches else 0}")
        logger.info(f"  - Memory hits: {len(memory_hits) if memory_hits else 0}")
        logger.info(f"  - Reference doc pairs: {len(reference_doc_pairs) if reference_doc_pairs else 0}")
        logger.info(f"📏 Prompt details:")
        logger.info(f"  - Total prompt length: {prompt_length:,} characters (~{estimated_tokens:,} tokens)")
        logger.info(f"🎯 Model: {self.model}")
        logger.info(f"⏱️  Starting streaming translation...")
        logger.info("=" * 80)

        import time
        start_time = time.time()

        try:
            # Use streaming API
            with self._client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for text in stream.text_stream:
                    yield text

            elapsed_time = time.time() - start_time

            logger.info("=" * 80)
            logger.info("✅ CLAUDE API STREAMING COMPLETED")
            logger.info("=" * 80)
            logger.info(f"⏱️  Total duration: {elapsed_time:.2f} seconds")
            logger.info("=" * 80)

        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error("=" * 80)
            logger.error("❌ CLAUDE API STREAMING FAILED")
            logger.error("=" * 80)
            logger.error(f"⏱️  Failed after: {elapsed_time:.2f} seconds")
            logger.error(f"❌ Error type: {type(e).__name__}")
            logger.error(f"❌ Error message: {str(e)}")
            logger.error("=" * 80)
            raise


def _format_reference_doc(reference_doc_pairs: dict[str, str] | None) -> str:
    """Format reference document translation pairs for prompt."""
    if not reference_doc_pairs:
        return "- (none)"
    
    lines = []
    for source, target in sorted(reference_doc_pairs.items(), key=lambda x: len(x[0]), reverse=True)[:50]:  # Limit to 50 pairs
        lines.append(f"- {source} -> {target}")
    
    result = "\n".join(lines)
    if len(reference_doc_pairs) > 50:
        result += f"\n[... {len(reference_doc_pairs) - 50} more pairs ...]"
    return result


def _build_prompt(
    *,
    base_template: str,
    source_lang: str,
    target_lang: str,
    glossary_section: str,
    memory_section: str,
    paragraph: str,
    reference_doc_section: str | None = None,
) -> str:
    """Build translation prompt with glossary and memory support."""
    prompt_parts = [
        f"{base_template}\n\n",
        "## Dati specifici per questa richiesta\n",
        f"- Lingua di partenza: {source_lang}\n",
        f"- Lingua di arrivo: {target_lang}\n\n",
        "### Istruzione importante\n",
        "**Traduci SEMPRE il testo fornito, indipendentemente dal contesto.** ",
        "Anche se il documento non sembra essere legale o assicurativo, procedi comunque con la traduzione. ",
        "Applica lo stile e il registro appropriati al tipo di documento, mantenendo sempre qualità professionale.\n\n",
    ]
    
    # Reference document has highest priority - add it first
    if reference_doc_section:
        prompt_parts.extend([
            "### ⚠️ CRITERI DI TRADUZIONE DAL DOCUMENTO DI RIFERIMENTO (PRIORITÀ MASSIMA)\n",
            "**IMPORTANTE:** Questi criteri hanno la PRIORITÀ ASSOLUTA su glossario, memoria e qualsiasi altra fonte.\n",
            "Devi seguire ESATTAMENTE queste traduzioni quando appaiono nel testo:\n",
            f"{reference_doc_section}\n\n",
        ])
    
    prompt_parts.extend([
        "### Glossario rilevante\n",
        f"{glossary_section}\n\n",
        "### Traduzioni precedenti / memoria\n",
        f"{memory_section}\n\n",
        "### Testo da tradurre\n",
        f"{paragraph}",
    ])
    
    return "".join(prompt_parts)

