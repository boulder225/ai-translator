"""
Glossary and Memory enricher: Apply glossary terms and translation memory to translated text and highlight them.
"""
from __future__ import annotations

import re
import logging
from typing import Sequence

from .terminology import Glossary, GlossaryMatch, TranslationMemory, TranslationRecord

logger = logging.getLogger(__name__)


def apply_glossary_with_highlighting(
    translated_text: str,
    glossary: Glossary | None,
    source_lang: str,
    target_lang: str,
) -> tuple[str, list[dict]]:
    """
    Apply glossary terms to translated text and highlight replaced terms.
    
    Finds glossary translations in the translated text and highlights them.
    Also finds source terms that might not have been translated and replaces them.
    
    Args:
        translated_text: The translated text to enrich
        glossary: Glossary to apply
        source_lang: Source language code
        target_lang: Target language code
    
    Returns:
        Tuple of (enriched_text_with_highlights, list_of_applied_terms)
        enriched_text uses HTML-like markers: <glossary>term</glossary>
    """
    if not glossary:
        return translated_text, []
    
    applied_terms = []
    enriched_text = translated_text
    
    logger.info(f"[apply_glossary_with_highlighting] Applying glossary: {glossary.name}")
    logger.info(f"[apply_glossary_with_highlighting] Translated text length: {len(translated_text)}")
    
    # Strategy 1: Find glossary translations in the translated text and highlight them
    # Sort entries by translation length (longest first) to avoid partial matches
    entries_by_translation = sorted(
        glossary.iter_entries(), 
        key=lambda e: len(e.translation) if e.translation else 0, 
        reverse=True
    )
    
    # Track positions to avoid overlapping replacements
    replacement_positions: list[tuple[int, int, str, GlossaryEntry, bool]] = []
    # Format: (start, end, matched_text, entry, is_translation_match)
    
    # Find glossary translations in translated text
    for entry in entries_by_translation:
        if not entry.translation or not entry.translation.strip():
            continue
        
        # Use word boundaries to avoid partial matches
        # Escape special regex characters in translation
        escaped_translation = re.escape(entry.translation)
        # Use word boundaries for whole-word matching
        pattern = r'\b' + escaped_translation + r'\b'
        
        for match in re.finditer(pattern, enriched_text, re.IGNORECASE):
            start, end = match.span()
            matched_text = enriched_text[start:end]
            
            # Check for overlaps
            overlap = False
            for pos_start, pos_end, _, _, _ in replacement_positions:
                if not (end <= pos_start or start >= pos_end):
                    overlap = True
                    break
            
            if not overlap:
                replacement_positions.append((start, end, matched_text, entry, True))
                applied_terms.append({
                    "term": entry.term,
                    "translation": entry.translation,
                    "matched_text": matched_text,
                    "context": entry.context,
                    "type": "translation_match",
                })
    
    # Strategy 2: Find source terms that weren't translated and replace them
    # (This helps catch cases where Claude didn't translate a term)
    entries_by_term = sorted(
        glossary.iter_entries(),
        key=lambda e: len(e.term) if e.term else 0,
        reverse=True
    )
    
    for entry in entries_by_term:
        if not entry.term or not entry.translation:
            continue
        
        # Only check if source and target languages match glossary direction
        # Skip if term and translation are the same (no point highlighting)
        if entry.term.lower() == entry.translation.lower():
            continue
        
        # Find source term in translated text (might not have been translated)
        escaped_term = re.escape(entry.term)
        pattern = r'\b' + escaped_term + r'\b'
        
        for match in re.finditer(pattern, enriched_text, re.IGNORECASE):
            start, end = match.span()
            matched_text = enriched_text[start:end]
            
            # Check for overlaps
            overlap = False
            for pos_start, pos_end, _, _, _ in replacement_positions:
                if not (end <= pos_start or start >= pos_end):
                    overlap = True
                    break
            
            if not overlap:
                # Replace source term with translation and highlight
                replacement_positions.append((start, end, matched_text, entry, False))
                applied_terms.append({
                    "term": entry.term,
                    "translation": entry.translation,
                    "matched_text": matched_text,
                    "replaced_with": entry.translation,
                    "context": entry.context,
                    "type": "source_replacement",
                })
    
    # Sort positions by start index (reverse order for safe replacement)
    replacement_positions.sort(key=lambda x: x[0], reverse=True)
    
    # Apply replacements from end to start to preserve positions
    for start, end, matched_text, entry, is_translation_match in replacement_positions:
        if is_translation_match:
            # Just highlight existing translation
            highlighted = f"<glossary>{matched_text}</glossary>"
        else:
            # Replace source term with translation and highlight
            highlighted = f"<glossary>{entry.translation}</glossary>"
        
        enriched_text = enriched_text[:start] + highlighted + enriched_text[end:]
    
    logger.info(f"[apply_glossary_with_highlighting] Applied {len(applied_terms)} glossary terms")
    logger.info(f"[apply_glossary_with_highlighting] Breakdown: {sum(1 for t in applied_terms if t.get('type') == 'translation_match')} translation matches, {sum(1 for t in applied_terms if t.get('type') == 'source_replacement')} source replacements")
    
    return enriched_text, applied_terms


def apply_glossary_replacements(
    translated_text: str,
    glossary: Glossary | None,
    source_lang: str,
    target_lang: str,
) -> tuple[str, list[dict]]:
    """
    Apply glossary replacements: find source terms in translated text and replace with glossary translations.
    Also highlights terms that match glossary translations.
    
    This is a more aggressive approach that actually replaces terms.
    """
    if not glossary:
        return translated_text, []
    
    applied_terms = []
    enriched_text = translated_text
    
    logger.info(f"[apply_glossary_replacements] Applying glossary: {glossary.name}")
    
    # Get all entries sorted by term length (longest first)
    entries = sorted(glossary.iter_entries(), key=lambda e: len(e.term), reverse=True)
    
    replacement_positions: list[tuple[int, int, str, str, GlossaryEntry]] = []
    
    for entry in entries:
        if not entry.term or not entry.translation:
            continue
        
        # Find source term in translated text (case-insensitive)
        pattern = re.escape(entry.term)
        
        for match in re.finditer(pattern, enriched_text, re.IGNORECASE):
            start, end = match.span()
            matched_text = enriched_text[start:end]
            
            # Check for overlaps
            overlap = False
            for pos_start, pos_end, _, _, _ in replacement_positions:
                if not (end <= pos_start or start >= pos_end):
                    overlap = True
                    break
            
            if not overlap:
                # Replace with glossary translation and highlight
                replacement_positions.append((start, end, matched_text, entry.translation, entry))
                applied_terms.append({
                    "term": entry.term,
                    "translation": entry.translation,
                    "matched_text": matched_text,
                    "replaced_with": entry.translation,
                    "context": entry.context,
                })
    
    # Apply replacements from end to start
    replacement_positions.sort(key=lambda x: x[0], reverse=True)
    
    for start, end, matched_text, replacement, entry in replacement_positions:
        # Replace and highlight
        highlighted_replacement = f"<glossary>{replacement}</glossary>"
        enriched_text = enriched_text[:start] + highlighted_replacement + enriched_text[end:]
    
    logger.info(f"[apply_glossary_replacements] Applied {len(applied_terms)} glossary replacements")
    
    return enriched_text, applied_terms


def apply_memory_with_highlighting(
    translated_text: str,
    memory: TranslationMemory | None,
    source_lang: str,
    target_lang: str,
    original_text: str | None = None,
    memory_record_used: TranslationRecord | None = None,
) -> tuple[str, list[dict]]:
    """
    Apply translation memory to translated text and highlight replaced terms.
    
    Finds similar translations in memory and replaces/highlights them.
    
    Args:
        translated_text: The translated text to enrich
        memory: Translation memory to apply
        source_lang: Source language code
        target_lang: Target language code
        original_text: Optional original text for better matching
    
    Returns:
        Tuple of (enriched_text_with_highlights, list_of_applied_terms)
        enriched_text uses HTML-like markers: <memory>term</memory>
    """
    if not memory:
        return translated_text, []
    
    applied_terms = []
    enriched_text = translated_text
    
    logger.info(f"[apply_memory_with_highlighting] Applying translation memory")
    logger.info(f"[apply_memory_with_highlighting] Translated text length: {len(translated_text)}")
    
    # Special case: If entire translation came from memory, highlight the whole text
    if memory_record_used:
        memory_translation = memory_record_used.translated_text.strip()
        translated_stripped = translated_text.strip()
        # Check if the entire translation matches the memory record (allowing for whitespace differences)
        if memory_translation == translated_stripped or memory_translation.replace('\n', ' ').replace('  ', ' ') == translated_stripped.replace('\n', ' ').replace('  ', ' '):
            logger.info(f"[apply_memory_with_highlighting] Entire translation came from memory - highlighting full text")
            # Split into paragraphs and highlight each paragraph
            paragraphs = enriched_text.split('\n\n')
            highlighted_paragraphs = []
            for para in paragraphs:
                if para.strip():
                    highlighted_paragraphs.append(f"<memory>{para.strip()}</memory>")
                    applied_terms.append({
                        "source_text": memory_record_used.source_text[:100] + "..." if len(memory_record_used.source_text) > 100 else memory_record_used.source_text,
                        "translated_text": para.strip()[:100] + "..." if len(para.strip()) > 100 else para.strip(),
                        "matched_text": para.strip(),
                        "type": "full_memory_match",
                    })
                else:
                    highlighted_paragraphs.append(para)
            enriched_text = '\n\n'.join(highlighted_paragraphs)
            logger.info(f"[apply_memory_with_highlighting] Highlighted {len([p for p in paragraphs if p.strip()])} paragraphs from memory")
            return enriched_text, applied_terms
    
    # Strategy: Find similar translations in memory
    # We'll look for segments of translated text that match memory records
    
    # Split translated text into sentences/segments for matching
    # Use sentence boundaries, paragraphs, or fixed-length chunks
    sentences = re.split(r'([.!?]\s+)', translated_text)
    segments = []
    for i in range(0, len(sentences), 2):
        if i + 1 < len(sentences):
            segment = sentences[i] + sentences[i + 1]
        else:
            segment = sentences[i]
        if segment.strip():
            segments.append(segment.strip())
    
    # If no good segments, use paragraphs
    if len(segments) < 2:
        segments = [s.strip() for s in translated_text.split('\n\n') if s.strip()]
    
    # If still no segments, use the whole text
    if not segments:
        segments = [translated_text]
    
    replacement_positions: list[tuple[int, int, str, TranslationRecord]] = []
    
    # Strategy: Find memory translations that appear in the translated text
    # We look for exact matches of memory translations (approved translations)
    
    # Get all memory records for this language pair
    memory_records = [
        record for record in memory 
        if record.source_lang == source_lang and record.target_lang == target_lang
    ]
    
    logger.info(f"[apply_memory_with_highlighting] Found {len(memory_records)} memory records for {source_lang}->{target_lang}")
    
    # Sort by translation length (longest first) to avoid partial matches
    memory_records_sorted = sorted(
        memory_records,
        key=lambda r: len(r.translated_text) if r.translated_text else 0,
        reverse=True
    )
    
    # For each memory record, find if its translation appears in the translated text
    for record in memory_records_sorted:
        memory_translation = record.translated_text.strip()
        if not memory_translation or len(memory_translation) < 3:
            continue
        
        # Find occurrences of memory translation in translated text
        # For short texts (< 50 chars), use word boundaries
        # For longer texts, use direct matching (allowing for whitespace differences)
        escaped_translation = re.escape(memory_translation)
        
        if len(memory_translation) < 50:
            # Short text: use word boundaries for whole-word matching
            pattern = r'\b' + escaped_translation + r'\b'
        else:
            # Long text: match directly, allowing for whitespace normalization
            # Replace multiple spaces/newlines with flexible whitespace matching
            normalized_memory = re.sub(r'\s+', r'\\s+', escaped_translation)
            pattern = normalized_memory
        
        for match in re.finditer(pattern, enriched_text, re.IGNORECASE | re.DOTALL):
            start, end = match.span()
            matched_text = enriched_text[start:end]
            
            # Check for overlaps (prioritize glossary over memory)
            overlap = False
            # Check if this position overlaps with any existing tags
            for pos_start, pos_end, _, _ in replacement_positions:
                if not (end <= pos_start or start >= pos_end):
                    overlap = True
                    break
            
            # Also check if there are tags nearby
            context_start = max(0, start - 100)
            context_end = min(len(enriched_text), end + 100)
            context = enriched_text[context_start:context_end]
            if re.search(r'<glossary>.*?</glossary>', context) or re.search(r'<memory>.*?</memory>', context):
                # Check if tags overlap with our position
                for tag_match in re.finditer(r'<glossary>.*?</glossary>|<memory>.*?</memory>', context):
                    tag_start = context_start + tag_match.start()
                    tag_end = context_start + tag_match.end()
                    if not (end <= tag_start or start >= tag_end):
                        overlap = True
                        break
            
            if not overlap:
                replacement_positions.append((start, end, matched_text, record))
                applied_terms.append({
                    "source_text": record.source_text[:100] + "..." if len(record.source_text) > 100 else record.source_text,
                    "translated_text": memory_translation[:100] + "..." if len(memory_translation) > 100 else memory_translation,
                    "matched_text": matched_text[:100] + "..." if len(matched_text) > 100 else matched_text,
                })
                # For long texts, only mark first occurrence. For short texts, mark all occurrences
                if len(memory_translation) >= 50:
                    break  # Only mark first occurrence of long memory translations
    
    # Sort positions by start index (reverse order for safe replacement)
    replacement_positions.sort(key=lambda x: x[0], reverse=True)
    
    # Apply replacements from end to start to preserve positions
    for start, end, matched_text, record in replacement_positions:
        # Wrap the matched text with memory marker
        highlighted = f"<memory>{matched_text}</memory>"
        enriched_text = enriched_text[:start] + highlighted + enriched_text[end:]
    
    logger.info(f"[apply_memory_with_highlighting] Applied {len(applied_terms)} memory terms")
    
    return enriched_text, applied_terms

