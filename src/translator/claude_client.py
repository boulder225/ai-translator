from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
import os

from anthropic import Anthropic

from .terminology import GlossaryMatch, TranslationMemory, TranslationRecord

DEFAULT_PROMPT = """You are a senior Swiss legal translator.
Use formal legal tone, preserve numbering, respect capitalization, and never add commentary.

Source language: {source_lang}
Target language: {target_lang}

Glossary hints:
{glossary_section}

Previous translations:
{memory_section}

Paragraph to translate:
{paragraph}

Return ONLY the translated paragraph text.
"""


def _format_glossary(matches: Sequence[GlossaryMatch]) -> str:
    if not matches:
        return "- (none)"
    lines = []
    for match in matches:
        context = f" ({match.entry.context})" if match.entry.context else ""
        lines.append(f"- {match.entry.term} -> {match.entry.translation}{context}")
    return "\n".join(lines)


def _format_memory(records: Sequence[TranslationRecord]) -> str:
    if not records:
        return "- (none)"
    lines = []
    for record in records:
        lines.append(f"- {record.source_text} -> {record.translated_text}")
    return "\n".join(lines)


DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-sonnet-20240229")


@dataclass
class ClaudeTranslator:
    api_key: str
    model: str = DEFAULT_MODEL
    max_tokens: int = 512
    dry_run: bool = False

    def __post_init__(self) -> None:
        if not self.dry_run and not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required unless dry_run is enabled.")
        self._client = Anthropic(api_key=self.api_key) if not self.dry_run else None

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
        prompt = DEFAULT_PROMPT.format(
            source_lang=source_lang,
            target_lang=target_lang,
            glossary_section=_format_glossary(glossary_matches),
            memory_section=_format_memory(memory_hits),
            paragraph=paragraph.strip(),
        )
        if self.dry_run:
            return f"[{target_lang} draft] {paragraph}"
        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

