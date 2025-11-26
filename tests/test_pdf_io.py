from __future__ import annotations

from pathlib import Path
from typing import List

import translator.pdf_io as pdf_io


class DummyPage:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class DummyPDF:
    def __init__(self, pages: List[DummyPage]) -> None:
        self.pages = pages

    def __enter__(self) -> "DummyPDF":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_read_paragraphs_from_pdf(monkeypatch, tmp_path: Path) -> None:
    dummy_pdf = DummyPDF([DummyPage("First paragraph.\n\nSecond paragraph."), DummyPage("")])

    def fake_open(path: str | Path) -> DummyPDF:  # pragma: no cover - simple monkeypatch stub
        return dummy_pdf

    monkeypatch.setattr(pdf_io, "pdfplumber", type("PlumberModule", (), {"open": staticmethod(fake_open)}))

    paragraphs = pdf_io.read_paragraphs_from_pdf(tmp_path / "file.pdf")
    assert paragraphs == ["First paragraph.", "Second paragraph."]

