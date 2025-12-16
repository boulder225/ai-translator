from __future__ import annotations

import re
from typing import Sequence

from .term_sources import TermSourceChain, TermTranslation


def extract_terms(text: str, min_length: int = 4) -> list[str]:
    """Extract potential legal terms from text (focus on multi-word phrases and capitalized terms)."""
    # Extract multi-word phrases (2-4 words) - these are likely legal terms
    phrases = re.findall(r'\b\w+(?:\s+\w+){1,3}\b', text.lower())
    
    # Extract capitalized terms (likely proper nouns, legal entities)
    capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
    capitalized_lower = [c.lower() for c in capitalized]
    
    # Extract single words that are longer (likely technical terms)
    words = re.findall(r'\b\w{6,}\b', text.lower())
    
    # Combine and deduplicate, filter by length
    all_terms = list(set(phrases + capitalized_lower + words))
    return [term for term in all_terms if len(term) >= min_length]


def lookup_term_hierarchy(
    term: str,
    *,
    source_chain: TermSourceChain,
    source_lang: str,
    target_lang: str,
) -> TermTranslation:
    """Look up term translation using the provided source chain."""
    return source_chain.lookup(term, source_lang, target_lang)


def apply_term_translations(
    text: str,
    term_translations: Sequence[TermTranslation],
    *,
    skip_placeholders: bool = True,
) -> str:
    """
    Replace terms in text with their translations, longest matches first.
    
    Args:
        text: Original text
        term_translations: List of term translations to apply
        skip_placeholders: If True, skip placeholder terms (e.g., [TERM]) to avoid
                          bloating the text. Placeholders don't help translation anyway.
    
    Returns:
        Text with terms replaced by their translations
    """
    # Filter out placeholders if requested (they just make text longer)
    if skip_placeholders:
        term_translations = [t for t in term_translations if t.source != "placeholder"]
    
    # Sort by length (longest first) to handle overlapping terms
    sorted_terms = sorted(term_translations, key=lambda t: len(t.source_term), reverse=True)
    
    result = text
    for term_trans in sorted_terms:
        # Case-insensitive replacement
        pattern = re.compile(re.escape(term_trans.source_term), re.IGNORECASE)
        result = pattern.sub(term_trans.translated_term, result)
    
    return result
