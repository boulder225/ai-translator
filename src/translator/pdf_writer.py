from __future__ import annotations

import html
from io import BytesIO
from pathlib import Path
from typing import Iterable

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def write_pdf(paragraphs: Iterable[str], output_path: str | Path) -> None:
    """Write paragraphs to a PDF file using ReportLab."""
    doc = SimpleDocTemplate(str(output_path), pagesize=A4, title=Path(output_path).name)
    styles = getSampleStyleSheet()
    body_style = styles["BodyText"]
    story = []
    
    for text in paragraphs:
        if not text:
            continue
            
        # Escape HTML entities and special characters
        # First escape HTML entities (like &, <, >)
        escaped_text = html.escape(text)
        
        # Convert newlines to ReportLab's line breaks
        clean_text = escaped_text.replace("\n", "<br/>")
        
        # Create paragraph with properly escaped text
        story.append(Paragraph(clean_text, body_style))
        story.append(Spacer(1, 12))
    
    doc.build(story)


def write_pdf_to_bytes(paragraphs: Iterable[str], title: str = "Translated Document") -> bytes:
    """Write paragraphs to PDF bytes in memory using ReportLab."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=title)
    styles = getSampleStyleSheet()
    body_style = styles["BodyText"]
    story = []
    
    for text in paragraphs:
        if not text:
            continue
            
        # Escape HTML entities and special characters
        escaped_text = html.escape(text)
        
        # Convert newlines to ReportLab's line breaks
        clean_text = escaped_text.replace("\n", "<br/>")
        
        # Create paragraph with properly escaped text
        story.append(Paragraph(clean_text, body_style))
        story.append(Spacer(1, 12))
    
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes







