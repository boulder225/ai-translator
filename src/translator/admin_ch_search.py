from __future__ import annotations

import logging
import re
import warnings
from urllib.parse import quote

# Suppress deprecation warning from duckduckgo_search (if used as fallback)
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*duckduckgo_search.*")

try:
    # Prefer the new ddgs package
    from ddgs import DDGS
except ImportError:
    try:
        # Fallback to old package name (with warning suppression)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

logger = logging.getLogger(__name__)

# Language code mapping for admin.ch
LANG_MAP = {
    "fr": "fr",
    "de": "de",
    "en": "en",
    "it": "it",
}


def _extract_translation_from_html(html: str, term: str, target_lang: str) -> str | None:
    """
    Extract translation from HTML content.
    
    Looks for common patterns in admin.ch multilingual pages:
    - Language switcher links
    - Parallel content sections
    - Translation tables
    - Simple text matching in target language sections
    """
    if not BeautifulSoup:
        return None
    
    try:
        soup = BeautifulSoup(html, "html.parser")
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Look for language switcher links (common pattern on admin.ch)
        lang_links = soup.find_all("a", href=re.compile(r"lang=|/de/|/fr/|/en/|/it/"))
        for link in lang_links:
            href = link.get("href", "")
            text = link.get_text(strip=True)
            # If link text matches our term and href suggests target language
            if term.lower() in text.lower() and target_lang in href.lower():
                return text.strip()
        
        # Look for translation pairs in tables or definition lists
        # Common pattern: <dt>French term</dt><dd>German term</dd>
        for dl in soup.find_all(["dl", "table"]):
            terms = dl.find_all(["dt", "th", "td"])
            for i, elem in enumerate(terms):
                text = elem.get_text(strip=True)
                if term.lower() in text.lower() and i + 1 < len(terms):
                    # Check next element for translation
                    next_elem = terms[i + 1]
                    translation = next_elem.get_text(strip=True)
                    if translation and translation != text and len(translation) < 100:
                        return translation
        
        # Look for multilingual content sections with lang attribute
        lang_sections = soup.find_all(attrs={"lang": re.compile(target_lang, re.I)})
        for section in lang_sections:
            text = section.get_text(strip=True)
            # Look for term-like phrases in target language sections
            if len(text) < 300:
                # Check if this section might contain the translation
                words = text.split()
                if len(words) <= 10:  # Short phrases are more likely to be terms
                    # Check if it's related to our term (contains similar words)
                    term_words = set(term.lower().split())
                    text_words = set(word.lower().strip(".,;:!?") for word in words)
                    # If there's some overlap or it's a short phrase, consider it
                    if len(term_words & text_words) > 0 or len(words) <= 5:
                        return text.strip()
        
        # Fallback: Look for the term in page title or headings
        title = soup.find("title")
        if title and target_lang in title.get_text().lower():
            title_text = title.get_text(strip=True)
            if len(title_text) < 150:
                return title_text
        
        # Look in h1-h3 headings
        for heading in soup.find_all(["h1", "h2", "h3"]):
            heading_text = heading.get_text(strip=True)
            if len(heading_text) < 100 and target_lang in heading.get("lang", "").lower():
                return heading_text
        
    except Exception as e:
        logger.debug(f"Error parsing HTML: {e}")
    
    return None


def _search_duckduckgo(term: str, target_lang: str) -> list[dict[str, str]]:
    """Search admin.ch using DuckDuckGo."""
    if not DDGS:
        return []
    
    try:
        # Try multiple search strategies
        queries = [
            f'site:admin.ch "{term}" {target_lang}',
            f'site:admin.ch {term} {target_lang}',
            f'admin.ch {term} {target_lang} translation',
        ]
        
        for idx, query in enumerate(queries, 1):
            logger.info(f"[admin.ch] Trying search query {idx}/{len(queries)}: {query}")
            try:
                # Suppress deprecation warnings from duckduckgo_search if used
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    with DDGS() as ddgs:
                        results = list(ddgs.text(query, max_results=5))
                        if results:
                            logger.info(f"[admin.ch] ✓ Found {len(results)} results with query {idx}")
                            return results
                        else:
                            logger.info(f"[admin.ch] Query {idx} returned no results, trying next query...")
            except Exception as e:
                error_msg = str(e)
                if "No results found" in error_msg:
                    logger.info(f"[admin.ch] Query {idx} returned no results, trying next query...")
                else:
                    logger.warning(f"[admin.ch] Query {idx} failed: {e}")
                continue
        
        logger.debug("No results found with any query")
        return []
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed: {e}")
        return []


def _fetch_and_parse_url(url: str, term: str, target_lang: str) -> str | None:
    """Fetch URL and extract translation."""
    if not requests:
        return None
    
    try:
        logger.debug(f"[admin.ch] Fetching URL: {url[:100]}...")
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; LegalTranslator/1.0; +https://example.com/bot)"
        }
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        logger.debug(f"[admin.ch] Fetched {len(response.text)} bytes, parsing HTML...")
        
        # Extract translation from HTML
        translation = _extract_translation_from_html(response.text, term, target_lang)
        if translation:
            logger.debug(f"[admin.ch] Found translation '{translation}' in {url[:80]}...")
            return translation
        else:
            logger.debug(f"[admin.ch] No translation found in HTML content")
        
    except Exception as e:
        # Handle different types of errors appropriately
        error_type = type(e).__name__
        if requests and isinstance(e, requests.exceptions.HTTPError):
            # 404s and other HTTP errors are common, log at debug level
            status_code = e.response.status_code if hasattr(e, 'response') and e.response else 'unknown'
            logger.debug(f"[admin.ch] HTTP {status_code} for {url[:80]}..., skipping")
        elif requests and isinstance(e, (requests.exceptions.RequestException, requests.exceptions.Timeout)):
            # Network errors, timeouts, etc. - log at debug level
            logger.debug(f"[admin.ch] Network error for {url[:80]}...: {e}")
        else:
            # Other unexpected errors - log as warning
            logger.warning(f"[admin.ch] Unexpected error fetching {url[:80]}...: {e}")
    
    return None


def search_admin_ch(term: str, source_lang: str, target_lang: str) -> str | None:
    """
    Search admin.ch (Swiss government website) for term translation.
    
    This function searches the official Swiss government website (admin.ch) for
    multilingual content that may contain translations of legal terms. The Swiss
    government website often provides content in multiple languages (French, German,
    Italian, English), making it a valuable source for legal terminology.
    
    Strategy:
    1. Search admin.ch using DuckDuckGo with site:admin.ch query
    2. Fetch top 3 search results
    3. Parse HTML content looking for:
       - Language switcher links
       - Translation tables/definition lists
       - Multilingual content sections (lang attributes)
       - Page titles and headings in target language
    4. Extract and return the translation if found
    
    Args:
        term: The term to translate (e.g., "contrat de bail")
        source_lang: Source language code (fr, de, en, it)
        target_lang: Target language code (fr, de, en, it)
    
    Returns:
        Translated term if found on admin.ch, None otherwise.
        Returns None if:
        - Search returns no results
        - HTML parsing doesn't find a translation
        - Network/parsing errors occur
    
    Example:
        >>> search_admin_ch("contrat de bail", "fr", "de")
        "Mietvertrag"  # If found on admin.ch
        
    Note:
        This is a best-effort search. Not all terms will be found, and the
        translation quality depends on admin.ch's content structure. The function
        gracefully handles failures and returns None, allowing the term source chain
        to fall back to the placeholder source.
    """
    if not DDGS:
        logger.warning("DuckDuckGo search not available. Install 'duckduckgo-search' package.")
        return None
    
    # Normalize language codes
    source_lang = LANG_MAP.get(source_lang.lower(), source_lang.lower())
    target_lang = LANG_MAP.get(target_lang.lower(), target_lang.lower())
    
    # Skip if same language
    if source_lang == target_lang:
        return None
    
    logger.info(f"[admin.ch] Searching for term: '{term}' ({source_lang} -> {target_lang})")
    
    # Search admin.ch
    results = _search_duckduckgo(term, target_lang)
    
    if not results:
        logger.info(f"[admin.ch] No search results found for '{term}'")
        return None
    
    logger.info(f"[admin.ch] Found {len(results)} search results, checking top 3 for translations...")
    
    # Try to extract translation from top results
    for idx, result in enumerate(results[:3], 1):  # Check top 3 results
        url = result.get("href", "")
        if not url or "admin.ch" not in url:
            logger.debug(f"[admin.ch] Skipping non-admin.ch URL: {url[:80]}")
            continue
        
        logger.info(f"[admin.ch] Checking result {idx}/3: {url[:100]}...")
        translation = _fetch_and_parse_url(url, term, target_lang)
        if translation:
            # Clean up translation (remove extra whitespace, normalize)
            translation = re.sub(r"\s+", " ", translation.strip())
            # If translation is too long, it's probably not just the term
            if len(translation) > len(term) * 3:
                # Try to extract just the term part
                words = translation.split()
                if len(words) > 5:
                    # Too long, skip
                    logger.debug(f"[admin.ch] Translation too long ({len(words)} words), skipping")
                    continue
            logger.info(f"[admin.ch] ✓ Found translation for '{term}': '{translation}'")
            return translation
        else:
            logger.debug(f"[admin.ch] No translation found in {url[:80]}...")
    
    logger.info(f"[admin.ch] ✗ Could not extract translation for '{term}' from admin.ch results")
    return None
