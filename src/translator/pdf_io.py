from __future__ import annotations

from pathlib import Path

import pdfplumber


def read_paragraphs_from_pdf(path: str | Path) -> list[str]:
    paragraphs: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if not text.strip():
                continue
            chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
            if not chunks:
                chunks = [line.strip() for line in text.splitlines() if line.strip()]
            paragraphs.extend(chunks)
    return paragraphs

