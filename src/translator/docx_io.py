from __future__ import annotations

from pathlib import Path
from typing import Iterable

from docx import Document


def read_paragraphs(path: str | Path) -> list[str]:
    document = Document(path)
    return [para.text for para in document.paragraphs]


def write_paragraphs(source_path: str | Path, translations: Iterable[str], output_path: str | Path) -> None:
    document = Document(source_path)
    for para, translated in zip(document.paragraphs, translations, strict=False):
        para.text = translated
    document.save(output_path)

