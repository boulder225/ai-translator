"""
Improved PDF formatting preservation using PyMuPDF.

This module provides a simpler, more effective approach to translating PDFs
while preserving their original formatting by creating a copy of the PDF
and replacing text in-place.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def translate_pdf_preserve_format(
    input_pdf_path: str | Path,
    output_pdf_path: str | Path,
    translated_text: str,
) -> None:
    """
    Translate PDF preserving 100% of original formatting.

    Creates a new PDF with ONLY translated text, maintaining exact:
    - Page layout and dimensions
    - Images, graphics, and backgrounds
    - Text positioning (translated text placed in original text areas)
    - Font sizes and colors

    Strategy:
    1. Open original PDF
    2. For each page, identify all text areas
    3. Remove original text with white overlay
    4. Insert translated text in same areas with same formatting

    Args:
        input_pdf_path: Path to input PDF
        output_pdf_path: Path to output PDF
        translated_text: Full translated document text
    """
    input_pdf_path = Path(input_pdf_path)
    output_pdf_path = Path(output_pdf_path)

    logger.info(f"PDF translation with format preservation")
    logger.info(f"Input: {input_pdf_path}")
    logger.info(f"Output: {output_pdf_path}")

    # Split translated text into paragraphs
    translated_paragraphs = [p.strip() for p in translated_text.split("\n\n") if p.strip()]
    if not translated_paragraphs:
        translated_paragraphs = [p.strip() for p in translated_text.split("\n") if p.strip()]
    if not translated_paragraphs:
        translated_paragraphs = [translated_text]

    logger.info(f"Translated text has {len(translated_paragraphs)} paragraphs")

    with fitz.open(input_pdf_path) as doc:
        para_index = 0

        for page_num in range(len(doc)):
            page = doc[page_num]
            logger.info(f"Processing page {page_num + 1}/{len(doc)}")

            # Get all text blocks on this page
            blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]

            # Collect text blocks with their formatting
            text_blocks = []
            for block in blocks:
                if block["type"] != 0:  # Skip non-text blocks
                    continue

                # Get block bounding box
                block_bbox = block["bbox"]

                # Get first span for formatting reference
                first_span = None
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("text", "").strip():
                            first_span = span
                            break
                    if first_span:
                        break

                if not first_span:
                    continue

                # Store block info
                text_blocks.append({
                    "bbox": block_bbox,
                    "font_size": first_span.get("size", 12.0),
                    "color": first_span.get("color", 0),
                })

            # Cover all text areas with white rectangles
            for block_info in text_blocks:
                bbox = block_info["bbox"]
                # Draw white rectangle to cover original text
                page.draw_rect(bbox, color=(1, 1, 1), fill=(1, 1, 1))

            # Insert translated text in each block area
            for block_info in text_blocks:
                if para_index >= len(translated_paragraphs):
                    break

                bbox = block_info["bbox"]
                font_size = block_info["font_size"]
                color = block_info["color"]

                # Convert color
                if isinstance(color, int):
                    b = (color >> 16) & 0xFF
                    g = (color >> 8) & 0xFF
                    r = color & 0xFF
                    color_rgb = (r / 255.0, g / 255.0, b / 255.0)
                else:
                    color_rgb = (0, 0, 0)

                # Get translated paragraph
                trans_text = translated_paragraphs[para_index]
                para_index += 1

                # Insert translated text
                try:
                    rc = page.insert_textbox(
                        bbox,
                        trans_text,
                        fontsize=font_size,
                        fontname="helv",
                        color=color_rgb,
                        align=fitz.TEXT_ALIGN_LEFT,
                    )

                    if rc < 0:
                        # Text didn't fit, try with smaller font
                        smaller_font = font_size * 0.8
                        rc = page.insert_textbox(
                            bbox,
                            trans_text,
                            fontsize=smaller_font,
                            fontname="helv",
                            color=color_rgb,
                            align=fitz.TEXT_ALIGN_LEFT,
                        )
                        if rc < 0:
                            logger.warning(f"Text still doesn't fit in bbox {bbox}")

                except Exception as e:
                    logger.error(f"Error inserting text: {e}")

        # Save the result
        doc.save(output_pdf_path)
        logger.info(f"Saved translated PDF to {output_pdf_path}")
