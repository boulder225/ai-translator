from __future__ import annotations

import html
import json
import logging
import re
from io import BytesIO
from pathlib import Path
from typing import Iterable, Sequence

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, KeepTogether, PageBreak
from reportlab.lib import colors

logger = logging.getLogger(__name__)


def _parse_highlighting_tags(text: str) -> str:
    """
    Parse highlighting tags and convert them to ReportLab XML formatting.
    
    Converts:
    - <glossary>term</glossary> -> <font color="#0066cc"><b>term</b></font> (blue, bold)
    - <memory>term</memory> -> <font color="#00aa00"><b>term</b></font> (green, bold)
    - <reference_doc>term</reference_doc> -> <font color="#cc6600"><b>term</b></font> (orange, bold)
    
    Args:
        text: Text with highlighting tags
        
    Returns:
        Text with ReportLab XML formatting tags and HTML entities escaped
    """
    # CRITICAL FIX: Always remove ReportLab XML tags (<para>, </para>) unconditionally
    # These are ReportLab-specific tags and should NEVER appear in the source text
    # They can cause parsing errors if present. ReportLab adds these automatically.
    # ReportLab wraps Paragraph content in <para> tags internally, so any <para> tags
    # in the input text will conflict with ReportLab's internal structure.
    result = text
    # Remove ALL variations of para tags (unconditional, multiple passes for safety)
    # Use word boundaries and case-insensitive matching to catch all variations
    result = re.sub(r'</?para\s*>', '', result, flags=re.IGNORECASE)
    result = re.sub(r'</?para>', '', result, flags=re.IGNORECASE)
    # Extract and protect our custom tags before HTML escaping
    tag_replacements = []
    tag_counter = 0
    
    # Find all highlighting tags and replace with placeholders
    def replace_tag(match):
        nonlocal tag_counter
        tag_type = match.group(1)  # glossary, memory, or reference_doc
        content = match.group(2)
        # CRITICAL: Remove <para> tags from content inside highlighting tags
        # ReportLab wraps Paragraph content in <para> tags internally, so any <para> tags
        # in the content will conflict with ReportLab's internal structure
        content_cleaned = re.sub(r'</?para\s*>', '', content, flags=re.IGNORECASE)
        placeholder = f"__HIGHLIGHT_TAG_{tag_counter}__"
        tag_replacements.append((placeholder, tag_type, content_cleaned))
        tag_counter += 1
        return placeholder
    
    # Replace all highlighting tags with placeholders
    result = re.sub(
        r'<(glossary|memory|reference_doc)>(.*?)</\1>',
        replace_tag,
        result,
        flags=re.DOTALL | re.IGNORECASE
    )
    
    # Escape HTML entities
    result = html.escape(result)
    
    # Restore tags with ReportLab formatting
    color_map = {
        'glossary': '#0066cc',      # Blue
        'memory': '#00aa00',        # Green
        'reference_doc': '#cc6600', # Orange
    }
    
    for placeholder, tag_type, content in tag_replacements:
        color = color_map.get(tag_type.lower(), '#000000')
        # CRITICAL: Remove any <para> tags from content before inserting into XML
        # ReportLab will wrap content in <para> tags, so we must never have them in the content
        content_cleaned = re.sub(r'</?para\s*>', '', content, flags=re.IGNORECASE)
        # CRITICAL FIX: Escape the content before inserting it into XML tags
        content_escaped = html.escape(content_cleaned)
        formatted = f'<font color="{color}"><b>{content_escaped}</b></font>'
        result = result.replace(placeholder, formatted)
    
    return result


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


def write_pdf_to_bytes(
    translated_paragraphs: Iterable[str], 
    title: str = "Translated Document",
    source_paragraphs: Sequence[str] | None = None,
    source_lang: str | None = None,
    target_lang: str | None = None,
) -> bytes:
    """Write paragraphs to PDF bytes in memory using ReportLab.
    
    If source_paragraphs is provided, creates a two-column layout with source on left and translation on right.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4, 
        title=title, 
        leftMargin=0.5*inch, 
        rightMargin=0.5*inch,
        topMargin=0.75*inch, 
        bottomMargin=0.75*inch,
        allowSplitting=1,  # Allow content to split across pages
    )
    styles = getSampleStyleSheet()
    
    # Create custom styles
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Heading3'],
        fontSize=11,
        textColor=colors.HexColor('#1a1a1a'),
        fontName='Helvetica-Bold',
        spaceAfter=6,
    )
    
    source_style = ParagraphStyle(
        'SourceStyle',
        parent=styles['BodyText'],
        fontSize=10,
        textColor=colors.HexColor('#333333'),
        leftIndent=0,
        rightIndent=6,
    )
    
    translated_style = ParagraphStyle(
        'TranslatedStyle',
        parent=styles['BodyText'],
        fontSize=10,
        textColor=colors.HexColor('#000000'),
        leftIndent=6,
        rightIndent=0,
    )
    
    story = []
    
    # Convert paragraphs to lists for easier handling
    translated_list = list(translated_paragraphs)
    source_list = list(source_paragraphs) if source_paragraphs else None
    
    if source_list and len(source_list) > 0:
        # Two-column layout: source on left, translation on right
        logger.info(f"[write_pdf_to_bytes] Creating two-column layout with {len(source_list)} source paragraphs and {len(translated_list)} translated paragraphs")
        
        # Add column headers
        source_header = source_lang.upper() if source_lang else "SOURCE"
        target_header = target_lang.upper() if target_lang else "TRANSLATION"
        
        header_table = Table(
            [[Paragraph(source_header, header_style), Paragraph(target_header, header_style)]],
            colWidths=[3*inch, 3*inch]
        )
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#f5f5f5')),
            ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#f5f5f5')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMBORDER', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 6))
        
        # Determine max length for pairing paragraphs
        max_len = max(len(source_list), len(translated_list))
        
        # Maximum height for a cell in points (leave room for margins and spacing)
        # Page height ~842pt, minus margins ~150pt, minus header ~50pt = ~640pt usable
        # Use 350pt as very safe maximum to ensure it fits (well below the 721pt frame)
        max_cell_height_pts = 350
        
        # Estimate: 10pt font size + 2pt line spacing = ~12pt per line
        # ~60 characters per line at 10pt font (but can vary with formatting)
        # So max_chars = (max_height / 12) * 60 = (350/12) * 60 ≈ 1750 chars
        # But be very conservative: use 1000 chars to account for formatting overhead,
        # long words, HTML tags, etc.
        max_chars_per_cell = 1000  # Very conservative estimate to prevent overflow
        
        for i in range(max_len):
            source_text = source_list[i] if i < len(source_list) else ""
            translated_text = translated_list[i] if i < len(translated_list) else ""
            
            # Skip if both are empty
            if not source_text.strip() and not translated_text.strip():
                continue
            
            # Parse highlighting tags and escape HTML entities
            source_escaped = html.escape(source_text) if source_text else ""
            translated_escaped = _parse_highlighting_tags(translated_text) if translated_text else ""
            
            # Convert newlines to line breaks
            source_clean = source_escaped.replace("\n", "<br/>") if source_escaped else ""
            translated_clean = translated_escaped.replace("\n", "<br/>") if translated_escaped else ""
            
            # Helper function to ensure XML tags are properly closed in a chunk
            def ensure_xml_tags_closed(chunk_text):
                """Ensure all XML tags in a chunk are properly closed.
                
                Only adds closing tags if there are actually opening tags in the chunk.
                Also removes closing tags from chunks that don't have matching opening tags.
                This prevents malformed XML when chunks are split in the middle of tags.
                """
                if not chunk_text or '<' not in chunk_text:
                    return chunk_text
                
                # Track open tags (LIFO stack) and find all tags
                open_tags = []
                has_opening_tags = False
                all_tags = []  # Track all tags and their positions
                i = 0
                while i < len(chunk_text):
                    if chunk_text[i] == '<':
                        # Find the end of the tag
                        tag_end = chunk_text.find('>', i)
                        if tag_end == -1:
                            break
                        tag = chunk_text[i:tag_end+1]
                        all_tags.append((i, tag_end + 1, tag))
                        
                        # Check if it's a closing tag
                        if tag.startswith('</'):
                            # Extract tag name (e.g., '</font>' -> 'font')
                            tag_name = tag[2:-1].split()[0].split('>')[0]
                            # Remove matching open tag from stack
                            if open_tags and open_tags[-1] == tag_name:
                                open_tags.pop()
                        elif not tag.endswith('/>') and not tag.startswith('<!'):  # Not self-closing or comment
                            # Extract tag name (e.g., '<font color="...">' -> 'font')
                            tag_name = tag[1:-1].split()[0].split('>')[0]
                            # Only track non-para tags (ReportLab adds <para> internally)
                            if tag_name.lower() != 'para':
                                open_tags.append(tag_name)
                                has_opening_tags = True
                        i = tag_end + 1
                    else:
                        i += 1
                
                # If chunk has opening tags, ensure they're closed
                if has_opening_tags and open_tags:
                    closing_tags = ''.join(f'</{tag}>' for tag in reversed(open_tags))
                    return chunk_text + closing_tags
                
                # If chunk doesn't have opening tags but has closing tags, remove them
                # This handles continuation chunks that were split in the middle of XML tags
                if not has_opening_tags:
                    # Build new string without closing tags
                    result_parts = []
                    last_end = 0
                    for start, end, tag in all_tags:
                        if tag.startswith('</'):
                            tag_name = tag[2:-1].split()[0].split('>')[0]
                            # Only remove font/b/br tags (ReportLab tags), not para (ReportLab adds those)
                            if tag_name.lower() in ('font', 'b', 'br'):
                                # Add text before this closing tag
                                result_parts.append(chunk_text[last_end:start])
                                last_end = end
                            else:
                                # Keep non-font/b/br closing tags (like </para>)
                                result_parts.append(chunk_text[last_end:end])
                                last_end = end
                        else:
                            # Keep opening tags and other tags
                            result_parts.append(chunk_text[last_end:end])
                            last_end = end
                    # Add remaining text
                    result_parts.append(chunk_text[last_end:])
                    return ''.join(result_parts)
                
                return chunk_text
            
            # Helper function to split text into chunks that fit within max_chars
            def split_text_into_chunks(text, max_chars):
                """Split text into chunks that won't exceed max_chars, ensuring XML tags are properly closed."""
                if len(text) <= max_chars:
                    return [ensure_xml_tags_closed(text)]
                
                chunks = []
                # First try splitting by double line breaks (paragraph breaks)
                if "<br/><br/>" in text:
                    parts = text.split("<br/><br/>")
                    current_chunk = []
                    current_length = 0
                    
                    for part in parts:
                        part_length = len(part) + 10  # +10 for "<br/><br/>"
                        # If a single part is too long, split it further
                        if part_length > max_chars:
                            # Split this part by single line breaks
                            lines = part.split("<br/>")
                            sub_chunk = []
                            sub_length = 0
                            for line in lines:
                                line_length = len(line) + 5  # +5 for "<br/>"
                                if sub_length + line_length > max_chars and sub_chunk:
                                    if current_chunk:
                                        chunk_text = "<br/><br/>".join(current_chunk)
                                        chunks.append(ensure_xml_tags_closed(chunk_text))
                                        current_chunk = []
                                    chunk_text = "<br/>".join(sub_chunk)
                                    chunks.append(ensure_xml_tags_closed(chunk_text))
                                    sub_chunk = [line]
                                    sub_length = line_length
                                else:
                                    sub_chunk.append(line)
                                    sub_length += line_length
                            if sub_chunk:
                                if current_chunk:
                                    chunk_text = "<br/><br/>".join(current_chunk)
                                    chunks.append(ensure_xml_tags_closed(chunk_text))
                                    current_chunk = []
                                chunk_text = "<br/>".join(sub_chunk)
                                chunks.append(ensure_xml_tags_closed(chunk_text))
                        elif current_length + part_length > max_chars and current_chunk:
                            chunk_text = "<br/><br/>".join(current_chunk)
                            chunks.append(ensure_xml_tags_closed(chunk_text))
                            current_chunk = [part]
                            current_length = part_length
                        else:
                            current_chunk.append(part)
                            current_length += part_length
                    
                    if current_chunk:
                        chunk_text = "<br/><br/>".join(current_chunk)
                        chunks.append(ensure_xml_tags_closed(chunk_text))
                else:
                    # Split by single line breaks
                    lines = text.split("<br/>")
                    current_chunk = []
                    current_length = 0
                    
                    for line in lines:
                        line_length = len(line) + 5  # +5 for "<br/>"
                        # If a single line is too long, split it by words
                        if line_length > max_chars:
                            # Split long line by spaces
                            words = line.split(" ")
                            word_chunk = []
                            word_length = 0
                            for word in words:
                                word_len = len(word) + 1  # +1 for space
                                if word_length + word_len > max_chars and word_chunk:
                                    if current_chunk:
                                        chunk_text = "<br/>".join(current_chunk)
                                        chunks.append(ensure_xml_tags_closed(chunk_text))
                                        current_chunk = []
                                    chunk_text = " ".join(word_chunk)
                                    chunks.append(ensure_xml_tags_closed(chunk_text))
                                    word_chunk = [word]
                                    word_length = word_len
                                else:
                                    word_chunk.append(word)
                                    word_length += word_len
                            if word_chunk:
                                current_chunk.append(" ".join(word_chunk))
                                current_length += word_length + 5
                        elif current_length + line_length > max_chars and current_chunk:
                            chunk_text = "<br/>".join(current_chunk)
                            chunks.append(ensure_xml_tags_closed(chunk_text))
                            current_chunk = [line]
                            current_length = line_length
                        else:
                            current_chunk.append(line)
                            current_length += line_length
                    
                    if current_chunk:
                        chunk_text = "<br/>".join(current_chunk)
                        chunks.append(ensure_xml_tags_closed(chunk_text))
                
                return chunks if chunks else [ensure_xml_tags_closed(text)]
            
            # Always split content to ensure it fits (even if under limit, split if close)
            # This ensures no cell exceeds the height limit
            source_chunks = split_text_into_chunks(source_clean, max_chars_per_cell)
            translated_chunks = split_text_into_chunks(translated_clean, max_chars_per_cell)
            
            # Ensure matching number of chunks (pad with empty strings)
            max_chunks = max(len(source_chunks), len(translated_chunks))
            for chunk_idx in range(max_chunks):
                source_chunk = source_chunks[chunk_idx] if chunk_idx < len(source_chunks) else ""
                translated_chunk = translated_chunks[chunk_idx] if chunk_idx < len(translated_chunks) else ""
                
                # Skip if both chunks are empty
                if not source_chunk.strip() and not translated_chunk.strip():
                    continue
                
                # CRITICAL FIX: Always remove <para> tags before creating Paragraph (unconditional)
                # ReportLab adds these automatically, so they should never be in the input text
                # Use multiple passes to catch all variations
                if translated_chunk:
                    # Remove opening and closing para tags (case-insensitive, multiple passes)
                    translated_chunk = re.sub(r'<para\s*>', '', translated_chunk, flags=re.IGNORECASE)
                    translated_chunk = re.sub(r'</para\s*>', '', translated_chunk, flags=re.IGNORECASE)
                    translated_chunk = re.sub(r'<para>', '', translated_chunk, flags=re.IGNORECASE)
                    translated_chunk = re.sub(r'</para>', '', translated_chunk, flags=re.IGNORECASE)
                if source_chunk:
                    source_chunk = re.sub(r'<para\s*>', '', source_chunk, flags=re.IGNORECASE)
                    source_chunk = re.sub(r'</para\s*>', '', source_chunk, flags=re.IGNORECASE)
                    source_chunk = re.sub(r'<para>', '', source_chunk, flags=re.IGNORECASE)
                    source_chunk = re.sub(r'</para>', '', source_chunk, flags=re.IGNORECASE)
                
                # FINAL SAFETY CHECK: ReportLab wraps Paragraph content in <para> tags internally
                # Any <para> tags in our text will conflict. Remove them one more time as absolute safety.
                # Also ensure tags are properly closed (ReportLab's parser is strict about XML structure)
                if translated_chunk:
                    # Remove para tags one final time
                    translated_chunk = re.sub(r'</?para\s*>', '', translated_chunk, flags=re.IGNORECASE)
                    # Ensure no unclosed tags by checking basic XML structure
                    # Count opening and closing font/b tags to ensure they match
                    font_open = translated_chunk.count('<font')
                    font_close = translated_chunk.count('</font>')
                    b_open = translated_chunk.count('<b>')
                    b_close = translated_chunk.count('</b>')
                    if font_open != font_close or b_open != b_close:
                        logger.warning(f"[write_pdf_to_bytes] XML structure warning: font tags {font_open}/{font_close}, b tags {b_open}/{b_close}")
                
                if source_chunk:
                    source_chunk = re.sub(r'</?para\s*>', '', source_chunk, flags=re.IGNORECASE)
                
                source_para = Paragraph(source_chunk, source_style) if source_chunk else Paragraph("", source_style)
                translated_para = Paragraph(translated_chunk, translated_style) if translated_chunk else Paragraph("", translated_style)
                
                table_data = [[source_para, translated_para]]
                table = Table(
                    table_data, 
                    colWidths=[3*inch, 3*inch], 
                    rowHeights=None,
                    repeatRows=0,
                    splitByRow=1,
                    splitInRow=0
                )
                table.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (0, -1), 0),
                    ('RIGHTPADDING', (0, 0), (0, -1), 6),
                    ('LEFTPADDING', (1, 0), (1, -1), 6),
                    ('RIGHTPADDING', (1, 0), (1, -1), 0),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                ]))
                
                # Don't use KeepTogether - let it split across pages if needed
                story.append(table)
                if chunk_idx < max_chunks - 1:
                    story.append(Spacer(1, 6))  # Smaller spacer between chunks
            
            story.append(Spacer(1, 12))
    else:
        # Single column: translation only
        for text in translated_list:
            if not text:
                continue
                
            # Parse highlighting tags
            parsed_text = _parse_highlighting_tags(text)
            clean_text = parsed_text.replace("\n", "<br/>")
        
            # CRITICAL FIX: Always remove <para> tags before creating Paragraph (unconditional)
            clean_text = re.sub(r'</?para>', '', clean_text, flags=re.IGNORECASE)
        
            story.append(Paragraph(clean_text, styles["BodyText"]))
            story.append(Spacer(1, 12))
    
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes







