from __future__ import annotations

from pathlib import Path

from docx import Document

from translator.batch_runner import run_batch
from translator.processing import DOCX_SUFFIX, PDF_SUFFIX
from translator.terminology.memory import TranslationMemory


class DummyTranslator:
    def translate_paragraph(self, paragraph: str, **_: str) -> str:
        return f"translated::{paragraph}"


def _make_docx(path: Path, paragraphs: list[str]) -> None:
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    doc.save(path)


def test_run_batch_creates_manifest(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    doc1 = input_dir / "doc1.docx"
    doc2 = input_dir / "doc2.docx"
    _make_docx(doc1, ["Paragraph one", "Paragraph two"])
    _make_docx(doc2, ["Another paragraph"])

    memory = TranslationMemory(tmp_path / "memory.json")
    translator = DummyTranslator()
    output_dir = tmp_path / "output"

    manifest_path, manifest = run_batch(
        [doc1, doc2],
        output_dir=output_dir,
        glossary=None,
        memory=memory,
        translator=translator,
        source_lang="fr",
        target_lang="en",
    )

    assert manifest["summary"]["documents_success"] == 2
    assert manifest["summary"]["documents_failed"] == 0
    assert manifest_path.exists()
    for entry in manifest["files"]:
        assert Path(entry["output_file"]).exists()
        assert entry["output_file"].endswith(f".en{PDF_SUFFIX}")
        assert Path(entry["report_file"]).exists()


