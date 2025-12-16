"""Tests for PDF writer functionality."""
from __future__ import annotations

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from translator.pdf_writer import _parse_highlighting_tags
import html


def test_parse_highlighting_tags_with_markdown_table():
    """Test that highlighting tags with markdown table content are properly escaped."""
    # This is the problematic content from the error message
    text_with_markdown_table = (
        '<memory>| Originale | Traduzione | Spiegazione | Fonte |\n'
        '|-----------|------------|-------------|-------|\n'
        '| OBJET DU BAIL | OGGETTO DELLA LOCAZIONE | Terminologia standard del diritto svizzero della locazione. "Oggetto della locazione" è la formula consolidata per indicare il bene locato nei contratti di locazione. Alternativa possibile ma meno tecnica: "Oggetto del contratto". | Codice delle obbligazioni (CO), art. 253 e segg.; admin.ch; prassi contrattuale svizzera |</memory>'
    )
    
    result = _parse_highlighting_tags(text_with_markdown_table)
    
    # Verify the result doesn't contain unescaped HTML/XML tags
    assert '</para>' not in result, "Should not contain unescaped </para> tag"
    assert '<b>' in result, "Should contain bold tag"
    assert '</b>' in result, "Should contain closing bold tag"
    
    # Verify special characters are escaped
    assert '&lt;' in result or '<' not in result[result.find('<b>')+3:result.find('</b>')], "Special characters should be escaped"
    
    # Verify the content is preserved (escaped)
    assert 'OBJET DU BAIL' in result or 'OBJET' in result, "Content should be preserved"


def test_parse_highlighting_tags_with_special_characters():
    """Test that special characters in highlighting tags are properly escaped."""
    text_with_special_chars = '<glossary>Test & <special> chars</glossary>'
    
    result = _parse_highlighting_tags(text_with_special_chars)
    
    # Verify HTML entities are escaped
    assert '&amp;' in result or '&lt;' in result, "Special characters should be escaped"
    assert '</b>' in result, "Should have closing bold tag"


def test_parse_highlighting_tags_multiple_tags():
    """Test parsing multiple highlighting tags."""
    text = (
        '<glossary>glossary term</glossary> '
        '<memory>memory term</memory> '
        '<reference_doc>reference term</reference_doc>'
    )
    
    result = _parse_highlighting_tags(text)
    
    # Verify all tags are converted
    assert '<font color="#0066cc">' in result, "Should have glossary color"
    assert '<font color="#00aa00">' in result, "Should have memory color"
    assert '<font color="#cc6600">' in result, "Should have reference_doc color"
    assert '<b>' in result, "Should have bold tags"


def test_parse_highlighting_tags_no_tags():
    """Test parsing text without highlighting tags."""
    text = "Plain text without any tags"
    
    result = _parse_highlighting_tags(text)
    
    # Should just escape HTML entities
    assert text == result or html.escape(text) == result, "Plain text should be unchanged or escaped"


if __name__ == '__main__':
    print("Testing _parse_highlighting_tags with markdown table...")
    test_parse_highlighting_tags_with_markdown_table()
    print("✓ Test 1 passed")
    
    print("Testing _parse_highlighting_tags with special characters...")
    test_parse_highlighting_tags_with_special_characters()
    print("✓ Test 2 passed")
    
    print("Testing _parse_highlighting_tags with multiple tags...")
    test_parse_highlighting_tags_multiple_tags()
    print("✓ Test 3 passed")
    
    print("Testing _parse_highlighting_tags with no tags...")
    test_parse_highlighting_tags_no_tags()
    print("✓ Test 4 passed")
    
    print("\nAll tests passed!")
