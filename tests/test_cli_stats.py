from __future__ import annotations

from pathlib import Path

from translator.processing import _translate_paragraphs
from translator.terminology.glossary import Glossary, GlossaryEntry
from translator.terminology.memory import TranslationMemory


class DummyTranslator:
    def __init__(self) -> None:
        self.calls = 0

    def translate_paragraph(self, paragraph: str, **_: str) -> str:
        self.calls += 1
        return f"translated::{paragraph}"


def test_translate_paragraphs_collects_stats(tmp_path: Path) -> None:
    memory = TranslationMemory(tmp_path / "memory.json")
    translator = DummyTranslator()
    glossary = Glossary(
        entries=[GlossaryEntry(term="contrat", translation="contract")],
        source_lang="fr",
        target_lang="en",
    )
    memory.record("Existing paragraph", "Existing translation", "fr", "en")

    paragraphs = ["Nouveau contrat", "Existing paragraph", ""]
    translated, stats = _translate_paragraphs(
        paragraphs,
        translator=translator,
        glossary=glossary,
        memory=memory,
        source_lang="fr",
        target_lang="en",
    )

    assert translated[1] == "Existing translation"
    assert translated[2] == ""
    assert stats.paragraphs_total == 3
    assert stats.empty_paragraphs == 1
    assert stats.reused_from_memory == 1
    assert stats.model_calls == 1
    assert stats.glossary_matches >= 1
    assert translator.calls == 1
    assert len(stats.paragraph_logs) == 3
    assert stats.paragraph_logs[1]["used_memory"] is True
    assert stats.paragraph_logs[0]["model_called"] is True

