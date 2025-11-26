from pathlib import Path

from translator.terminology.glossary import Glossary
from translator.terminology.memory import TranslationMemory

FIXTURES = Path(__file__).parent / "fixtures"


def test_glossary_exact_and_fuzzy():
    glossary = Glossary.from_csv(FIXTURES / "glossary_sample.csv", source_lang="fr", target_lang="en")
    exact = glossary.exact_matches("contrat")
    assert len(exact) == 1
    assert exact[0].translation == "contract"

    fuzzy = glossary.fuzzy_matches("Assemblee Generale", threshold=40)
    assert fuzzy, "Should return fuzzy matches"
    assert fuzzy[0].entry.translation == "General meeting"

    text_matches = glossary.matches_in_text("L'Assemblée générale de la société a lieu demain.")
    assert any(match.entry.translation == "General meeting" for match in text_matches)


def test_translation_memory_roundtrip(tmp_path):
    memory_path = tmp_path / "memory.json"
    fixture_path = FIXTURES / "memory_sample.json"
    memory_path.write_text(fixture_path.read_text(encoding="utf-8"), encoding="utf-8")

    memory = TranslationMemory(memory_path)
    record = memory.get("Le contrat entre les parties est valide.", "fr", "en")
    assert record is not None
    assert record.translated_text.endswith("valid.")

    new = memory.record("Nouveau texte", "New text", "fr", "en")
    assert memory.get("Nouveau texte", "fr", "en") == new

    similar = memory.similar("Le contrat entre les parties est valide.", "fr", "en", threshold=50)
    assert similar, "Should find at least one similar translation"

