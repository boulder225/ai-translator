"""Terminology utilities: glossary handling + translation memory."""

from .glossary import Glossary, GlossaryEntry, GlossaryMatch  # noqa: F401
from .memory import TranslationMemory, TranslationRecord  # noqa: F401

__all__ = [
    "Glossary",
    "GlossaryEntry",
    "GlossaryMatch",
    "TranslationMemory",
    "TranslationRecord",
]

