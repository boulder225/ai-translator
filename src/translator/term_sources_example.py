"""
Example: How to add a custom term source.

This file demonstrates how to create a new pluggable term source
without modifying the core translation logic.
"""

from __future__ import annotations

from .term_sources import TermSource, TermTranslation


class CustomWebSource(TermSource):
    """
    Example custom source that searches a custom API.
    
    To use this source, simply add it to the source chain:
    
    ```python
    from translator.term_sources import (
        GlossarySource, MemorySource, AdminChSource, 
        PlaceholderSource, TermSourceChain
    )
    from translator.term_sources_example import CustomWebSource
    
    sources = [
        GlossarySource(glossary),
        MemorySource(memory),
        CustomWebSource(api_key="..."),  # Your custom source
        AdminChSource(enabled=True),
        PlaceholderSource(),
    ]
    chain = TermSourceChain(sources)
    ```
    """
    
    def __init__(self, api_key: str, enabled: bool = True) -> None:
        self.api_key = api_key
        self._enabled = enabled
    
    @property
    def source_id(self) -> str:
        return "custom_web"
    
    def is_enabled(self) -> bool:
        return self._enabled
    
    def lookup(self, term: str, source_lang: str, target_lang: str) -> TermTranslation | None:
        if not self.is_enabled():
            return None
        
        # Your custom lookup logic here
        # For example, call an API:
        # result = your_api_client.search(term, source_lang, target_lang, self.api_key)
        
        # If found, return TermTranslation
        # if result:
        #     return TermTranslation(
        #         source_term=term,
        #         translated_term=result.translation,
        #         source=self.source_id,
        #         confidence=0.8,
        #         metadata={"api_version": "1.0"},
        #     )
        
        # If not found, return None (chain will try next source)
        return None







