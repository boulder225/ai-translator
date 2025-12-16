from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence

from .terminology import Glossary, TranslationMemory


@dataclass(slots=True)
class TermTranslation:
    source_term: str
    translated_term: str
    source: str  # Source identifier (e.g., "glossary", "memory", "admin_ch")
    confidence: float = 1.0
    metadata: dict[str, object] | None = None


class TermSource(ABC):
    """
    Abstract base class for term translation sources.
    
    This is a pluggable architecture that allows adding new term lookup sources
    without modifying the core translation logic. Each source implements:
    
    1. `source_id`: Unique identifier (e.g., "glossary", "memory", "admin_ch")
    2. `is_enabled()`: Whether this source is currently available
    3. `lookup()`: The actual lookup logic
    
    Sources are chained together in priority order. The first source that returns
    a non-None result wins. If all sources return None, the PlaceholderSource
    (which should always be last) will provide a fallback.
    
    Example:
        To add a new source, simply implement this interface and add it to the chain:
        
        ```python
        class MyCustomSource(TermSource):
            @property
            def source_id(self) -> str:
                return "my_custom"
            
            def is_enabled(self) -> bool:
                return True
            
            def lookup(self, term: str, source_lang: str, target_lang: str) -> TermTranslation | None:
                # Your lookup logic here
                if found:
                    return TermTranslation(...)
                return None
        
        # Then add to chain:
        chain = TermSourceChain([
            GlossarySource(glossary),
            MemorySource(memory),
            MyCustomSource(),  # Your new source
            PlaceholderSource(),
        ])
        ```
    """
    
    @property
    @abstractmethod
    def source_id(self) -> str:
        """Unique identifier for this source (e.g., 'glossary', 'memory')."""
        pass
    
    @abstractmethod
    def lookup(self, term: str, source_lang: str, target_lang: str) -> TermTranslation | None:
        """
        Look up a term translation.
        
        Args:
            term: The term to translate
            source_lang: Source language code
            target_lang: Target language code
        
        Returns:
            TermTranslation if found, None to continue to next source in chain
        """
        pass
    
    @abstractmethod
    def is_enabled(self) -> bool:
        """Check if this source is enabled/available."""
        pass


class GlossarySource(TermSource):
    """Term lookup from glossary (exact match)."""
    
    def __init__(self, glossary: Glossary | None) -> None:
        self.glossary = glossary
    
    @property
    def source_id(self) -> str:
        return "glossary"
    
    def is_enabled(self) -> bool:
        return self.glossary is not None
    
    def lookup(self, term: str, source_lang: str, target_lang: str) -> TermTranslation | None:
        if not self.is_enabled():
            return None
        
        matches = self.glossary.exact_matches(term)
        if matches:
            entry = matches[0]
            return TermTranslation(
                source_term=term,
                translated_term=entry.translation,
                source=self.source_id,
                confidence=1.0,
                metadata={"glossary_entry": entry.term},
            )
        return None


class MemorySource(TermSource):
    """Term lookup from translation memory (similarity search)."""
    
    def __init__(self, memory: TranslationMemory, threshold: float = 85.0) -> None:
        self.memory = memory
        self.threshold = threshold
    
    @property
    def source_id(self) -> str:
        return "memory"
    
    def is_enabled(self) -> bool:
        return True  # Memory is always available
    
    def lookup(self, term: str, source_lang: str, target_lang: str) -> TermTranslation | None:
        similar = self.memory.similar(term, source_lang, target_lang, limit=1, threshold=self.threshold)
        if similar:
            record = similar[0]
            return TermTranslation(
                source_term=term,
                translated_term=record.translated_text,
                source=self.source_id,
                confidence=self.threshold / 100.0,
                metadata={"similarity_score": self.threshold},
            )
        return None


class AdminChSource(TermSource):
    """Term lookup from admin.ch web search."""
    
    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled
    
    @property
    def source_id(self) -> str:
        return "admin_ch"
    
    def is_enabled(self) -> bool:
        return self._enabled
    
    def lookup(self, term: str, source_lang: str, target_lang: str) -> TermTranslation | None:
        if not self.is_enabled():
            return None
        
        try:
            from .admin_ch_search import search_admin_ch
            
            result = search_admin_ch(term, source_lang, target_lang)
            if result:
                return TermTranslation(
                    source_term=term,
                    translated_term=result,
                    source=self.source_id,
                    confidence=0.7,
                    metadata={"search_query": f"site:admin.ch {term}"},
                )
        except ImportError:
            pass
        
        return None


class ReferenceDocSource(TermSource):
    """Term lookup from reference document (highest priority)."""
    
    def __init__(self, translation_pairs: dict[str, str] | None) -> None:
        """
        Initialize reference document source.
        
        Args:
            translation_pairs: Dictionary mapping source terms (lowercase) to target translations
        """
        self.translation_pairs = translation_pairs or {}
        # Normalize keys to lowercase for case-insensitive lookup
        self._normalized_pairs = {k.lower().strip(): v for k, v in self.translation_pairs.items()}
    
    @property
    def source_id(self) -> str:
        return "reference_doc"
    
    def is_enabled(self) -> bool:
        return len(self._normalized_pairs) > 0
    
    def lookup(self, term: str, source_lang: str, target_lang: str) -> TermTranslation | None:
        if not self.is_enabled():
            return None
        
        # Case-insensitive lookup
        normalized_term = term.lower().strip()
        if normalized_term in self._normalized_pairs:
            return TermTranslation(
                source_term=term,
                translated_term=self._normalized_pairs[normalized_term],
                source=self.source_id,
                confidence=1.0,
                metadata={"reference_doc": True},
            )
        return None


class PlaceholderSource(TermSource):
    """Fallback source that creates placeholders for unfound terms."""
    
    @property
    def source_id(self) -> str:
        return "placeholder"
    
    def is_enabled(self) -> bool:
        return True  # Always enabled as fallback
    
    def lookup(self, term: str, source_lang: str, target_lang: str) -> TermTranslation | None:
        # Placeholder source always returns a result (it's the fallback)
        return TermTranslation(
            source_term=term,
            translated_term=f"[{term.upper()}]",
            source=self.source_id,
            confidence=0.0,
            metadata={"reason": "term_not_found"},
        )


class TermSourceChain:
    """
    Manages a chain of term sources in priority order.
    
    This implements the Chain of Responsibility pattern. Sources are checked
    in the order they are provided. The first source that returns a non-None
    result wins. Disabled sources are automatically skipped.
    
    The PlaceholderSource should always be last in the chain to ensure
    every term gets a translation (even if it's just a placeholder).
    
    Example:
        ```python
        chain = TermSourceChain([
            GlossarySource(glossary),      # Checked first
            MemorySource(memory),         # Checked second
            AdminChSource(enabled=True),  # Checked third
            PlaceholderSource(),          # Always returns a result
        ])
        
        result = chain.lookup("contrat", "fr", "en")
        # Returns TermTranslation from first source that finds it
        ```
    """
    
    def __init__(self, sources: Sequence[TermSource]) -> None:
        """
        Initialize the source chain.
        
        Args:
            sources: Ordered list of term sources. PlaceholderSource should be last.
        """
        self.sources = sources
    
    def lookup(self, term: str, source_lang: str, target_lang: str) -> TermTranslation:
        """
        Look up term through source chain, returning first match or placeholder.
        
        Sources are checked in order. Disabled sources are skipped.
        The PlaceholderSource (if present) will always return a result.
        
        Args:
            term: The term to translate
            source_lang: Source language code
            target_lang: Target language code
        
        Returns:
            TermTranslation from the first source that finds it
        
        Raises:
            RuntimeError: If no source returns a result (shouldn't happen if
                         PlaceholderSource is in chain)
        """
        for source in self.sources:
            if not source.is_enabled():
                continue
            
            result = source.lookup(term, source_lang, target_lang)
            if result is not None:
                return result
        
        # Should never reach here if PlaceholderSource is in chain
        raise RuntimeError("No placeholder source found in chain")

