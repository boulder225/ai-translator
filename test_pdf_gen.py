#!/usr/bin/env python3
"""Test script to verify PyMuPDF PDF generation works correctly."""

import fitz  # PyMuPDF
from pathlib import Path

def test_simple_pdf_creation():
    """Create a simple PDF with text to verify PyMuPDF works."""

    # Create a new PDF
    doc = fitz.open()

    # Add a page (A4 size)
    page = doc.new_page(width=595, height=842)

    # Define content area
    rect = fitz.Rect(50, 50, 545, 792)

    # Sample translated text
    text = """Questo è un testo di prova tradotto in italiano.

Questo paragrafo contiene più frasi per testare il flusso del testo. La formattazione dovrebbe essere preservata correttamente nel documento PDF finale.

Un altro paragrafo per verificare che tutto funzioni come previsto."""

    # Insert text - BLACK color (0, 0, 0)
    rc = page.insert_textbox(
        rect,
        text,
        fontsize=12,
        fontname="helv",
        color=(0, 0, 0),  # BLACK
        align=fitz.TEXT_ALIGN_LEFT,
    )

    print(f"insert_textbox returned: {rc}")

    # Save
    output_path = Path("/Users/enrico/workspace/translator/test_output.pdf")
    doc.save(output_path)
    doc.close()

    print(f"Saved test PDF to: {output_path}")
    print(f"File size: {output_path.stat().st_size} bytes")

    return output_path


def test_pdf_with_original(input_pdf_path: str):
    """Test modifying an existing PDF."""

    input_path = Path(input_pdf_path)
    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return

    print(f"Opening: {input_path}")

    doc = fitz.open(input_path)

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Get page size
        rect = page.rect
        print(f"Page {page_num + 1} size: {rect.width} x {rect.height}")

        # Get text blocks
        blocks = page.get_text("dict")["blocks"]
        text_blocks = [b for b in blocks if b.get("type") == 0]
        print(f"Found {len(text_blocks)} text blocks")

        # Cover ALL text with white rectangles
        for block in text_blocks:
            bbox = fitz.Rect(block["bbox"])
            # Use draw_rect with shape
            shape = page.new_shape()
            shape.draw_rect(bbox)
            shape.finish(color=(1, 1, 1), fill=(1, 1, 1))
            shape.commit()

        # Define content area (full page with margins)
        content_rect = fitz.Rect(50, 50, rect.width - 50, rect.height - 50)

        # Sample translated text
        translated_text = """TESTO TRADOTTO DI TEST

Questo documento è stato tradotto automaticamente. Il testo originale è stato sostituito con questa traduzione di prova.

Paragrafo aggiuntivo per verificare che il testo venga visualizzato correttamente in nero su sfondo bianco."""

        # Insert translated text in BLACK
        rc = page.insert_textbox(
            content_rect,
            translated_text,
            fontsize=11,
            fontname="helv",
            color=(0, 0, 0),  # BLACK - this is critical!
            align=fitz.TEXT_ALIGN_LEFT,
        )

        print(f"insert_textbox returned: {rc}")

    # Save to new file
    output_path = Path("/Users/enrico/workspace/translator/test_modified.pdf")
    doc.save(output_path)
    doc.close()

    print(f"Saved modified PDF to: {output_path}")
    print(f"File size: {output_path.stat().st_size} bytes")


if __name__ == "__main__":
    print("=== Test 1: Create simple PDF ===")
    test_simple_pdf_creation()

    print("\n=== Test 2: Modify existing PDF ===")
    # Use a test PDF if available
    test_pdf = "/Users/enrico/workspace/translator/tests/docs/test-admin-ch-output.pdf"
    test_pdf_with_original(test_pdf)
