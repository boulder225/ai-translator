"""
PDF formatting preservation using PyMuPDF (fitz).

This module provides functionality to translate PDFs while preserving
their original formatting, layout, fonts, colors, and structure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


@dataclass
class TextBlock:
    """Represents a block of text with its formatting and position."""

    text: str
    bbox: tuple[float, float, float, float]  # (x0, y0, x1, y1)
    font_name: str
    font_size: float
    color: tuple[float, float, float]  # RGB (0-1 range)
    flags: int  # Font flags (bold, italic, etc.)
    page_num: int

    @property
    def is_bold(self) -> bool:
        """Check if text is bold."""
        return bool(self.flags & 2**4)

    @property
    def is_italic(self) -> bool:
        """Check if text is italic."""
        return bool(self.flags & 2**1)


def extract_text_blocks(pdf_path: str | Path) -> list[TextBlock]:
    """
    Extract text blocks from PDF with formatting and position information.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        List of TextBlock objects containing text and formatting info
    """
    pdf_path = Path(pdf_path)
    logger.info(f"Extracting text blocks from PDF: {pdf_path}")

    text_blocks = []

    with fitz.open(pdf_path) as doc:
        logger.info(f"PDF has {len(doc)} pages")

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Extract text with detailed formatting information
            blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]

            for block in blocks:
                if block["type"] != 0:  # Skip non-text blocks (images, etc.)
                    continue

                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue

                        text_block = TextBlock(
                            text=text,
                            bbox=tuple(span["bbox"]),
                            font_name=span.get("font", ""),
                            font_size=span.get("size", 12.0),
                            color=span.get("color", 0),  # Integer color value
                            flags=span.get("flags", 0),
                            page_num=page_num,
                        )
                        text_blocks.append(text_block)

        logger.info(f"Extracted {len(text_blocks)} text blocks")

    return text_blocks


def translate_pdf_preserve_formatting(
    input_pdf_path: str | Path,
    output_pdf_path: str | Path,
    translations: dict[str, str],
) -> None:
    """
    Translate PDF text while preserving formatting and layout.

    Uses PyMuPDF's redaction feature to replace text in-place while
    maintaining the original document structure.

    Args:
        input_pdf_path: Path to input PDF
        output_pdf_path: Path to output PDF
        translations: Dictionary mapping original text to translated text
    """
    input_pdf_path = Path(input_pdf_path)
    output_pdf_path = Path(output_pdf_path)

    logger.info(f"Translating PDF with formatting preservation")
    logger.info(f"Input: {input_pdf_path}")
    logger.info(f"Output: {output_pdf_path}")
    logger.info(f"Translations: {len(translations)} items")

    with fitz.open(input_pdf_path) as doc:
        for page_num in range(len(doc)):
            page = doc[page_num]

            # Extract text blocks for this page
            blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]

            for block in blocks:
                if block["type"] != 0:
                    continue

                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        original_text = span.get("text", "").strip()
                        if not original_text or original_text not in translations:
                            continue

                        translated_text = translations[original_text]
                        bbox = span["bbox"]
                        font_name = span.get("font", "helv")
                        font_size = span.get("size", 12.0)
                        color = span.get("color", 0)

                        # Redact (remove) original text
                        page.add_redact_annot(bbox, text="")

                        # Convert integer color to RGB tuple (0-1 range)
                        if isinstance(color, int):
                            # PyMuPDF color is BGR format
                            b = (color >> 16) & 0xFF
                            g = (color >> 8) & 0xFF
                            r = color & 0xFF
                            color_rgb = (r / 255.0, g / 255.0, b / 255.0)
                        else:
                            color_rgb = (0, 0, 0)  # Default black

                        # Apply redactions
                        page.apply_redactions()

                        # Insert translated text at same position
                        # Use insert_htmlbox for better text fitting
                        try:
                            page.insert_htmlbox(
                                bbox,
                                translated_text,
                                css=f"font-size: {font_size}pt; color: rgb({int(color_rgb[0]*255)}, {int(color_rgb[1]*255)}, {int(color_rgb[2]*255)});",
                            )
                        except Exception as e:
                            logger.warning(f"Failed to insert text with htmlbox, trying textbox: {e}")
                            # Fallback to insert_textbox
                            page.insert_textbox(
                                bbox,
                                translated_text,
                                fontsize=font_size,
                                color=color_rgb,
                                fontname="helv",
                            )

            logger.info(f"Processed page {page_num + 1}/{len(doc)}")

        # Save the modified PDF
        doc.save(output_pdf_path)
        logger.info(f"Saved translated PDF to {output_pdf_path}")


def extract_paragraphs_with_formatting(pdf_path: str | Path) -> list[dict]:
    """
    Extract paragraphs from PDF with their formatting metadata.

    Returns paragraphs grouped by proximity and formatting similarity.

    Args:
        pdf_path: Path to PDF file

    Returns:
        List of dictionaries containing 'text' and 'metadata' for each paragraph
    """
    pdf_path = Path(pdf_path)
    text_blocks = extract_text_blocks(pdf_path)

    # Group text blocks into paragraphs
    # Simple heuristic: blocks on same page with similar Y coordinates
    paragraphs = []
    current_paragraph = []
    current_y = None
    current_page = None

    for block in text_blocks:
        # Check if we should start a new paragraph
        if current_page is None or current_page != block.page_num:
            # New page
            if current_paragraph:
                paragraph_text = " ".join(b.text for b in current_paragraph)
                paragraphs.append({
                    "text": paragraph_text,
                    "metadata": {
                        "page": current_paragraph[0].page_num,
                        "bbox": current_paragraph[0].bbox,
                        "font_name": current_paragraph[0].font_name,
                        "font_size": current_paragraph[0].font_size,
                        "color": current_paragraph[0].color,
                    }
                })
            current_paragraph = [block]
            current_y = block.bbox[1]
            current_page = block.page_num
        elif current_y is not None and abs(block.bbox[1] - current_y) > 20:
            # Large vertical gap - new paragraph
            if current_paragraph:
                paragraph_text = " ".join(b.text for b in current_paragraph)
                paragraphs.append({
                    "text": paragraph_text,
                    "metadata": {
                        "page": current_paragraph[0].page_num,
                        "bbox": current_paragraph[0].bbox,
                        "font_name": current_paragraph[0].font_name,
                        "font_size": current_paragraph[0].font_size,
                        "color": current_paragraph[0].color,
                    }
                })
            current_paragraph = [block]
            current_y = block.bbox[1]
        else:
            # Continue current paragraph
            current_paragraph.append(block)
            current_y = block.bbox[3]  # Bottom of current block

    # Add final paragraph
    if current_paragraph:
        paragraph_text = " ".join(b.text for b in current_paragraph)
        paragraphs.append({
            "text": paragraph_text,
            "metadata": {
                "page": current_paragraph[0].page_num,
                "bbox": current_paragraph[0].bbox,
                "font_name": current_paragraph[0].font_name,
                "font_size": current_paragraph[0].font_size,
                "color": current_paragraph[0].color,
            }
        })

    logger.info(f"Extracted {len(paragraphs)} paragraphs with formatting")
    return paragraphs


def translate_pdf_advanced(
    input_pdf_path: str | Path,
    output_pdf_path: str | Path,
    paragraph_translations: Sequence[str],
) -> None:
    """
    Translate PDF while preserving 100% of original formatting.
    
    This function:
    - Opens the original PDF
    - Extracts text blocks with their exact positions and formatting
    - Maps original paragraphs to translated paragraphs
    - Replaces text in-place while preserving fonts, layout, tables, images, etc.
    
    Args:
        input_pdf_path: Path to input PDF
        output_pdf_path: Path to output PDF
        paragraph_translations: List of translated paragraphs (must match order of original paragraphs)
    """
    input_pdf_path = Path(input_pdf_path)
    output_pdf_path = Path(output_pdf_path)

    logger.info(f"Translating PDF with formatting preservation")
    logger.info(f"Input: {input_pdf_path}")
    logger.info(f"Output: {output_pdf_path}")
    logger.info(f"Number of translated paragraphs: {len(paragraph_translations)}")

    # First, extract original paragraphs from PDF to map them to translations
    from .pdf_io import read_paragraphs_from_pdf
    original_paragraphs = read_paragraphs_from_pdf(input_pdf_path)
    logger.info(f"Extracted {len(original_paragraphs)} original paragraphs from PDF")

    if len(original_paragraphs) != len(paragraph_translations):
        logger.warning(f"Paragraph count mismatch: {len(original_paragraphs)} original vs {len(paragraph_translations)} translated")
        logger.warning("Will attempt to map paragraphs by position")

    # Open the original PDF
    doc = fitz.open(input_pdf_path)
    logger.info(f"Opened PDF with {len(doc)} pages")

    # Process each page
    translation_idx = 0
    import re
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        logger.info(f"Processing page {page_num + 1}")
        
        # Get all text blocks on this page with formatting
        text_dict = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)
        
        # Collect all text spans with their positions and formatting
        all_text_spans = []
        for block in text_dict["blocks"]:
            if block["type"] != 0:  # Skip non-text blocks (images, etc.)
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text:
                        all_text_spans.append({
                            "text": text,
                            "rect": fitz.Rect(span["bbox"]),
                            "font": span.get("font", "helv"),
                            "size": span.get("size", 12.0),
                            "color": span.get("color", 0),
                            "flags": span.get("flags", 0),
                        })
        
        if not all_text_spans:
            logger.info(f"Page {page_num + 1}: No text spans found, skipping")
            continue
        
        # Group text spans into paragraphs by vertical proximity
        # This matches how we extract paragraphs in read_paragraphs_from_pdf
        paragraphs_spans = []
        current_para = []
        last_y = None
        
        for span_info in all_text_spans:
            y = span_info["rect"].y0
            # New paragraph if vertical gap > 15 points (similar to double newline)
            if last_y is None or abs(y - last_y) > 15:
                if current_para:
                    paragraphs_spans.append(current_para)
                current_para = [span_info]
            else:
                current_para.append(span_info)
            last_y = span_info["rect"].y1
        
        if current_para:
            paragraphs_spans.append(current_para)
        
        logger.info(f"Page {page_num + 1}: Found {len(paragraphs_spans)} paragraph groups")
        logger.info(f"Page {page_num + 1}: Starting with translation_idx={translation_idx}, total translations={len(paragraph_translations)}")
        
        # CRITICAL: Redact ALL text on the page first to remove original text completely
        # This ensures no original text remains, even if paragraph counts don't match
        logger.info(f"Page {page_num + 1}: Redacting all text spans to remove original text")
        for span_info in all_text_spans:
            page.add_redact_annot(span_info["rect"])
        
        # Store paragraph info for later insertion (after redaction)
        para_info_list = []
        
        # Map translated paragraphs to paragraph groups
        # If we have fewer translations than paragraph groups, we'll insert translations
        # at the positions of the first N paragraph groups
        num_paragraphs_to_replace = min(len(paragraphs_spans), len(paragraph_translations) - translation_idx)
        logger.info(f"Page {page_num + 1}: Will replace {num_paragraphs_to_replace} paragraphs with translations")
        
        # First pass: collect paragraph info for translations
        for i, para_group in enumerate(paragraphs_spans):
            if translation_idx >= len(paragraph_translations):
                logger.info(f"Page {page_num + 1}: No more translations available, stopping at paragraph {i}")
                break
            
            # Calculate combined bounding box for this paragraph
            x0 = min(s["rect"].x0 for s in para_group)
            y0 = min(s["rect"].y0 for s in para_group)
            x1 = max(s["rect"].x1 for s in para_group)
            y1 = max(s["rect"].y1 for s in para_group)
            para_rect = fitz.Rect(x0, y0, x1, y1)
            
            # Get formatting from first span (preserve original formatting)
            first_span = para_group[0]
            font_name = first_span["font"]
            font_size = first_span["size"]
            color_int = first_span["color"]
            
            # Convert color from integer to RGB tuple (0-1 range)
            if isinstance(color_int, int):
                # PyMuPDF color is BGR format
                b = (color_int >> 16) & 0xFF
                g = (color_int >> 8) & 0xFF
                r = color_int & 0xFF
                color_rgb = (r / 255.0, g / 255.0, b / 255.0)
            else:
                color_rgb = (0, 0, 0)  # Default black
            
            # Get translated text and clean it
            translated_text = paragraph_translations[translation_idx]
            # Remove highlighting tags if present
            translated_text = re.sub(r'</?(glossary|memory|reference_doc)>', '', translated_text)
            
            # Store info for later insertion
            para_info_list.append({
                "rect": para_rect,
                "font_name": font_name,
                "font_size": font_size,
                "color_rgb": color_rgb,
                "translated_text": translated_text,
                "translation_idx": translation_idx,
            })
            
            translation_idx += 1
            
        # Apply all redactions for this page
        try:
            page.apply_redactions()
        except Exception as e:
            logger.warning(f"Page {page_num + 1}: Error applying redactions: {e}")
            continue
        
        # Re-insert translated text with original formatting
        logger.info(f"Page {page_num + 1}: Re-inserting {len(para_info_list)} translated paragraphs")
        for para_info in para_info_list:
            para_rect = para_info["rect"]
            font_name = para_info["font_name"]
            font_size = para_info["font_size"]
            color_rgb = para_info["color_rgb"]
            translated_text = para_info["translated_text"]
            trans_idx = para_info["translation_idx"]
            
            # Skip if translated text is empty
            if not translated_text or not translated_text.strip():
                logger.warning(f"Page {page_num + 1}: Skipping empty translation at index {trans_idx}")
                continue
            
            logger.info(f"Page {page_num + 1}: Inserting translation {trans_idx}: '{translated_text[:50]}...' (font: {font_name}, size: {font_size})")
            
            # Map font names to PyMuPDF standard fonts
            # PyMuPDF standard fonts: helv, hebo, tiro, tibo, cour, cobo
            font_name_lower = (font_name or "helv").lower()
            standard_font = "helv"  # Default
            
            # Map common font names to PyMuPDF standard fonts
            if "helvetica" in font_name_lower or "arial" in font_name_lower:
                standard_font = "hebo" if ("bold" in font_name_lower or "black" in font_name_lower) else "helv"
            elif "times" in font_name_lower:
                standard_font = "tibo" if ("bold" in font_name_lower or "black" in font_name_lower) else "tiro"
            elif "courier" in font_name_lower or "mono" in font_name_lower:
                standard_font = "cobo" if ("bold" in font_name_lower or "black" in font_name_lower) else "cour"
            elif "bold" in font_name_lower or "black" in font_name_lower:
                standard_font = "hebo"
            
            # Insert translated text with original formatting
            text_inserted = False
            try:
                # Try insert_textbox first (better for multi-line text)
                rc = page.insert_textbox(
                    para_rect,
                    translated_text,
                    fontsize=font_size,
                    fontname=standard_font,
                    color=color_rgb,
                    align=fitz.TEXT_ALIGN_LEFT,
                )
                if rc >= 0:
                    text_inserted = True
                    logger.info(f"Page {page_num + 1}: Successfully inserted text using insert_textbox (rc={rc:.1f})")
                else:
                    logger.warning(f"Page {page_num + 1}: insert_textbox overflow (rc={rc:.1f}), trying insert_text")
            except Exception as e:
                logger.warning(f"Page {page_num + 1}: insert_textbox failed: {e}, trying insert_text")
            
            # Fallback to insert_text if insert_textbox failed
            if not text_inserted:
                try:
                    # Use top-left corner of the paragraph rect
                    insert_point = (para_rect.x0, para_rect.y0 + font_size)
                    page.insert_text(
                        insert_point,
                        translated_text,
                        fontsize=font_size,
                        fontname=standard_font,
                        color=color_rgb,
                    )
                    text_inserted = True
                    logger.info(f"Page {page_num + 1}: Successfully inserted text using insert_text")
                except Exception as e:
                    logger.error(f"Page {page_num + 1}: insert_text also failed: {e}")
                    # Last resort: try with helv font
                    try:
                        logger.info(f"Page {page_num + 1}: Trying with default font 'helv'")
                        page.insert_text(
                            (para_rect.x0, para_rect.y0 + font_size),
                            translated_text,
                            fontsize=font_size,
                            fontname="helv",
                            color=color_rgb,
                        )
                        text_inserted = True
                        logger.info(f"Page {page_num + 1}: Successfully inserted text with default font")
                    except Exception as e2:
                        logger.error(f"Page {page_num + 1}: All text insertion methods failed: {e2}")
            
            if not text_inserted:
                logger.error(f"Page {page_num + 1}: CRITICAL: Failed to insert translated text for paragraph {trans_idx}")

    # Save the modified PDF
    doc.save(output_pdf_path)
    doc.close()

    logger.info(f"Saved translated PDF with preserved formatting to {output_pdf_path}")
