import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getGlossaryContent } from '../services/api';
import './EditableTranslatedText.css';

function EditableTranslatedText({ paragraphs, sourceLang, targetLang, glossaryName = 'glossary' }) {
  const [isEditing, setIsEditing] = useState(false);
  const [selectedText, setSelectedText] = useState('');
  const [alternatives, setAlternatives] = useState([]);
  const [showAlternatives, setShowAlternatives] = useState(false);
  const [alternativesPosition, setAlternativesPosition] = useState({ top: 0, left: 0 });
  const [glossaryEntries, setGlossaryEntries] = useState([]);
  const [editedParagraphs, setEditedParagraphs] = useState(paragraphs);
  const containerRef = useRef(null);
  const alternativesRef = useRef(null);
  const selectionRangeRef = useRef(null);

  // Load glossary entries
  useEffect(() => {
    const loadGlossary = async () => {
      try {
        const content = await getGlossaryContent(glossaryName);
        if (content.entries) {
          setGlossaryEntries(content.entries);
        }
      } catch (error) {
        console.error('Failed to load glossary:', error);
      }
    };
    loadGlossary();
  }, [glossaryName]);

  // Update edited paragraphs when paragraphs prop changes
  useEffect(() => {
    setEditedParagraphs(paragraphs);
  }, [paragraphs]);

  // Handle text selection
  const handleSelection = () => {
    if (!isEditing) return;

    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) {
      setShowAlternatives(false);
      selectionRangeRef.current = null;
      return;
    }

    const range = selection.getRangeAt(0);
    const selectedText = selection.toString().trim();
    
    if (!selectedText || selectedText.length < 2) {
      setShowAlternatives(false);
      selectionRangeRef.current = null;
      return;
    }

    // Store the range for later replacement
    selectionRangeRef.current = range.cloneRange();
    setSelectedText(selectedText);

    // Find alternatives from glossary
    const matchingEntries = glossaryEntries.filter(entry => {
      const translation = (entry.translation || '').toLowerCase();
      const term = (entry.term || '').toLowerCase();
      const selectedLower = selectedText.toLowerCase();
      
      // Check if selected text matches translation or term
      return translation.includes(selectedLower) || 
             selectedLower.includes(translation) ||
             term.includes(selectedLower) ||
             selectedLower.includes(term);
    });

    // Get unique alternatives (prioritize exact matches)
    const alternativesList = [];
    const seen = new Set();
    
    // First, add exact matches
    matchingEntries.forEach(entry => {
      if (entry.translation && !seen.has(entry.translation)) {
        const isExact = entry.translation.toLowerCase() === selectedText.toLowerCase();
        if (isExact) {
          alternativesList.unshift({
            text: entry.translation,
            term: entry.term,
            context: entry.context,
            isExact: true
          });
          seen.add(entry.translation);
        }
      }
    });

    // Then add other matches
    matchingEntries.forEach(entry => {
      if (entry.translation && !seen.has(entry.translation)) {
        alternativesList.push({
          text: entry.translation,
          term: entry.term,
          context: entry.context,
          isExact: false
        });
        seen.add(entry.translation);
      }
    });

    // Also add the source term translations if selected text matches a translation
    glossaryEntries.forEach(entry => {
      if (entry.translation && entry.translation.toLowerCase() === selectedText.toLowerCase()) {
        // This is already a translation, show the term as alternative
        if (entry.term && !seen.has(entry.term)) {
          alternativesList.push({
            text: entry.term,
            term: entry.translation,
            context: entry.context,
            isExact: false,
            isSourceTerm: true
          });
          seen.add(entry.term);
        }
      }
    });

    setAlternatives(alternativesList);

    // Calculate position for alternatives dropdown
    const rect = range.getBoundingClientRect();
    const containerRect = containerRef.current?.getBoundingClientRect();
    
    if (containerRect) {
      setAlternativesPosition({
        top: rect.bottom - containerRect.top + 5,
        left: rect.left - containerRect.left
      });
      setShowAlternatives(alternativesList.length > 0);
    }
  };


  // Handle replacement
  const handleReplace = (replacementText, event) => {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }

    if (!isEditing || !selectedText) return;

    // Use stored range for replacement
    const range = selectionRangeRef.current;
    if (!range) {
      console.warn('No selection range stored for replacement');
      setShowAlternatives(false);
      setSelectedText('');
      return;
    }

    // Ensure the range is still valid
    try {
      // Check if range is still in the document
      if (!range.commonAncestorContainer || !containerRef.current?.contains(range.commonAncestorContainer)) {
        console.warn('Selection range is no longer valid');
        setShowAlternatives(false);
        setSelectedText('');
        return;
      }

      // Replace selected text in DOM
      range.deleteContents();
      const textNode = document.createTextNode(replacementText);
      range.insertNode(textNode);
      
      // Find which paragraph was modified
      let paragraphIndex = -1;
      let paragraphElement = null;
      
      let node = textNode.parentNode;
      while (node && node !== containerRef.current) {
        if (node.nodeType === Node.ELEMENT_NODE && node.hasAttribute('data-paragraph-index')) {
          paragraphIndex = parseInt(node.getAttribute('data-paragraph-index'));
          paragraphElement = node;
          break;
        }
        node = node.parentNode;
      }
      
      if (paragraphIndex !== -1 && paragraphElement) {
        // Update the paragraph in state
        const updatedParagraphs = [...editedParagraphs];
        updatedParagraphs[paragraphIndex] = paragraphElement.textContent || updatedParagraphs[paragraphIndex];
        setEditedParagraphs(updatedParagraphs);
      }

      // Move cursor after the inserted text
      const selection = window.getSelection();
      if (selection) {
        const newRange = document.createRange();
        newRange.setStartAfter(textNode);
        newRange.collapse(true);
        selection.removeAllRanges();
        selection.addRange(newRange);
      }
    } catch (error) {
      console.error('Error replacing text:', error);
    }
    
    setShowAlternatives(false);
    setSelectedText('');
    selectionRangeRef.current = null;
  };

  // Close alternatives on click outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (alternativesRef.current && !alternativesRef.current.contains(event.target) &&
          containerRef.current && !containerRef.current.contains(event.target)) {
        setShowAlternatives(false);
      }
    };

    if (showAlternatives) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showAlternatives]);

  // Handle mouseup for selection
  useEffect(() => {
    if (!isEditing) return;

    const handleMouseUp = () => {
      setTimeout(handleSelection, 10);
    };

    document.addEventListener('mouseup', handleMouseUp);
    return () => document.removeEventListener('mouseup', handleMouseUp);
  }, [isEditing, glossaryEntries]);


  // Clean paragraphs for editing (remove tags)
  const cleanParagraphForEditing = (para) => {
    if (!para) return '';
    return para
      .replace(/<glossary>(.*?)<\/glossary>/g, '$1')
      .replace(/<memory>(.*?)<\/memory>/g, '$1');
  };

  // Handle content change - only update state when needed (not on every keystroke)
  const handleContentChange = () => {
    // Don't update state on every keystroke - this causes cursor to jump
    // State will be updated when user exits edit mode or on blur
  };

  // Update paragraphs when exiting edit mode
  const handleBlur = () => {
    if (!isEditing || !containerRef.current) return;
    
    const updatedParagraphs = [];
    const paragraphElements = containerRef.current.querySelectorAll('[data-paragraph-index]');
    
    paragraphElements.forEach((el) => {
      const idx = parseInt(el.getAttribute('data-paragraph-index'));
      updatedParagraphs[idx] = el.textContent || '';
    });
    
    // Fill in any missing paragraphs
    editedParagraphs.forEach((para, idx) => {
      if (updatedParagraphs[idx] === undefined) {
        updatedParagraphs[idx] = cleanParagraphForEditing(para);
      }
    });
    
    setEditedParagraphs(updatedParagraphs);
  };

  const handleToggleEdit = () => {
    if (isEditing) {
      // Exiting edit mode - save changes
      handleBlur();
    }
    setIsEditing(!isEditing);
    setShowAlternatives(false);
    setSelectedText('');
  };

  return (
    <div className="editable-translated-text-container">
      <div className="editable-text-header">
        <button
          className="edit-toggle-button"
          onClick={handleToggleEdit}
          title={isEditing ? 'Exit edit mode' : 'Enter edit mode'}
        >
          {isEditing ? '✓ Done Editing' : '✏️ Edit Translation'}
        </button>
        {isEditing && (
          <span className="edit-hint">Select a term to see glossary alternatives</span>
        )}
      </div>
      {isEditing ? (
        <div
          ref={containerRef}
          className="translated-text-content editable"
          contentEditable={true}
          suppressContentEditableWarning={true}
          onBlur={handleBlur}
        >
          {editedParagraphs.map((paragraph, idx) => {
            if (!paragraph) return null;
            const cleanText = cleanParagraphForEditing(paragraph);
            return (
              <div key={idx} className="paragraph-wrapper" data-paragraph-index={idx}>
                {cleanText || '\u00A0'}
              </div>
            );
          })}
        </div>
      ) : (
        <div ref={containerRef} className="translated-text-content">
          {editedParagraphs.map((paragraph, idx) => {
            if (!paragraph) return null;
            
            // Process paragraph to handle both glossary and memory tags
            const parts = paragraph.split(/(<glossary>.*?<\/glossary>|<memory>.*?<\/memory>)/g);
            
            return (
              <div key={idx} className="paragraph-wrapper" data-paragraph-index={idx}>
                {parts.map((part, partIdx) => {
                  // Handle glossary tags
                  if (part.startsWith('<glossary>') && part.endsWith('</glossary>')) {
                    const glossaryText = part.slice(10, -11);
                    return (
                      <ReactMarkdown 
                        key={partIdx} 
                        remarkPlugins={[remarkGfm]}
                        components={{
                          strong: ({node, ...props}) => (
                            <strong className="glossary-term" {...props} />
                          ),
                        }}
                      >
                        {`**${glossaryText}**`}
                      </ReactMarkdown>
                    );
                  }
                  
                  // Handle memory tags
                  if (part.startsWith('<memory>') && part.endsWith('</memory>')) {
                    const memoryText = part.slice(8, -9);
                    return (
                      <span key={partIdx} className="memory-term">
                        {memoryText}
                      </span>
                    );
                  }
                  
                  // Regular text
                  if (part.trim()) {
                    return (
                      <ReactMarkdown 
                        key={partIdx} 
                        remarkPlugins={[remarkGfm]}
                        components={{
                          strong: ({node, ...props}) => (
                            <strong className="glossary-term" {...props} />
                          ),
                        }}
                      >
                        {part}
                      </ReactMarkdown>
                    );
                  }
                  
                  return null;
                })}
              </div>
            );
          })}
        </div>
      )}
      
      {showAlternatives && alternatives.length > 0 && (
        <div
          ref={alternativesRef}
          className="alternatives-dropdown"
          style={{
            top: `${alternativesPosition.top}px`,
            left: `${alternativesPosition.left}px`
          }}
        >
          <div className="alternatives-header">
            Alternatives for "{selectedText}"
          </div>
          <div className="alternatives-list">
            {alternatives.map((alt, idx) => (
              <div
                key={idx}
                className="alternative-item"
                onMouseDown={(e) => {
                  e.preventDefault();
                  handleReplace(alt.text, e);
                }}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                }}
              >
                <div className="alternative-text">{alt.text}</div>
                {alt.term && (
                  <div className="alternative-term">
                    {alt.isSourceTerm ? 'Source: ' : 'Term: '}{alt.term}
                  </div>
                )}
                {alt.context && (
                  <div className="alternative-context">{alt.context}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default EditableTranslatedText;
