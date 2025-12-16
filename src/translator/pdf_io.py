from __future__ import annotations

from pathlib import Path

import pdfplumber


def read_paragraphs_from_pdf(path: str | Path) -> list[str]:
    import hashlib
    import logging
    
    logger = logging.getLogger(__name__)
    path_obj = Path(path)
    
    logger.info(f"[read_paragraphs_from_pdf] Reading PDF: {path_obj}")
    logger.info(f"[read_paragraphs_from_pdf] Absolute path: {path_obj.resolve()}")
    
    # Verify file hash before reading
    with open(path_obj, 'rb') as f:
        file_content = f.read()
        file_hash = hashlib.md5(file_content).hexdigest()
    logger.info(f"[read_paragraphs_from_pdf] File hash: {file_hash}")
    logger.info(f"[read_paragraphs_from_pdf] File size: {len(file_content):,} bytes")
    
    paragraphs: list[str] = []
    with pdfplumber.open(path_obj) as pdf:
        logger.info(f"[read_paragraphs_from_pdf] PDF opened, pages: {len(pdf.pages)}")
        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if not text.strip():
                continue
            chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
            if not chunks:
                chunks = [line.strip() for line in text.splitlines() if line.strip()]
            paragraphs.extend(chunks)
            if page_idx == 0 and chunks:
                logger.info(f"[read_paragraphs_from_pdf] First page first chunk: {chunks[0][:100]}...")
    
    logger.info(f"[read_paragraphs_from_pdf] Extracted {len(paragraphs)} paragraphs")
    return paragraphs


def read_paragraphs_from_txt(path: str | Path) -> list[str]:
    """Read paragraphs from a plain text file."""
    import hashlib
    import logging
    
    logger = logging.getLogger(__name__)
    path_obj = Path(path)
    
    logger.info(f"[read_paragraphs_from_txt] Reading TXT: {path_obj}")
    logger.info(f"[read_paragraphs_from_txt] Absolute path: {path_obj.resolve()}")
    
    # Verify file hash before reading
    with open(path_obj, 'rb') as f:
        file_content = f.read()
        file_hash = hashlib.md5(file_content).hexdigest()
    logger.info(f"[read_paragraphs_from_txt] File hash: {file_hash}")
    logger.info(f"[read_paragraphs_from_txt] File size: {len(file_content):,} bytes")
    
    with open(path_obj, "r", encoding="utf-8") as f:
        text = f.read()
    
    if not text.strip():
        logger.info(f"[read_paragraphs_from_txt] File is empty")
        return []
    
    # Split by double newlines (paragraph breaks)
    paragraphs = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
    
    # If no double newlines, split by single newlines
    if not paragraphs:
        paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
    
    # If still empty, treat entire file as one paragraph
    if not paragraphs:
        paragraphs = [text.strip()]
    
    logger.info(f"[read_paragraphs_from_txt] Extracted {len(paragraphs)} paragraphs")
    if paragraphs:
        logger.info(f"[read_paragraphs_from_txt] First paragraph: {paragraphs[0][:100]}...")
    
    return paragraphs








