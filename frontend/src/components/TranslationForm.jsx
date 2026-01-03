import { useState, useEffect } from 'react';
import { startTranslation, getPrompt, detectLanguage, getGlossaryContent, updateGlossaryContent, getMemoryContent, updateMemoryContent, deleteAllMemoryContent } from '../services/api';
import './TranslationForm.css';

function TranslationForm({ onTranslationStart, onStreamingStart, userRole }) {
  const [file, setFile] = useState(null);
  const [referenceDoc, setReferenceDoc] = useState(null);
  const [sourceLang, setSourceLang] = useState('fr');
  const [targetLang, setTargetLang] = useState('it');
  const [useGlossary, setUseGlossary] = useState(true);
  const [useMemory, setUseMemory] = useState(true);
  const [useStreaming, setUseStreaming] = useState(true);
  const [preserveFormatting, setPreserveFormatting] = useState(false);
  const [customPrompt, setCustomPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [loadingPrompt, setLoadingPrompt] = useState(true);
  const [detectingLanguage, setDetectingLanguage] = useState(false);
  const [showToolbar, setShowToolbar] = useState(false);
  const [showGlossaryModal, setShowGlossaryModal] = useState(false);
  const [glossaryContent, setGlossaryContent] = useState(null);
  const [loadingGlossary, setLoadingGlossary] = useState(false);
  const [glossarySearchQuery, setGlossarySearchQuery] = useState('');
  const [editingGlossaryEntry, setEditingGlossaryEntry] = useState(null);
  const [editedGlossaryEntries, setEditedGlossaryEntries] = useState(null);
  const [savingGlossary, setSavingGlossary] = useState(false);
  const [showMemoryModal, setShowMemoryModal] = useState(false);
  const [memoryContent, setMemoryContent] = useState(null);
  const [loadingMemory, setLoadingMemory] = useState(false);
  const [memorySearchQuery, setMemorySearchQuery] = useState('');
  const [editingMemoryEntry, setEditingMemoryEntry] = useState(null);
  const [editedMemoryEntries, setEditedMemoryEntries] = useState(null);
  const [savingMemory, setSavingMemory] = useState(false);
  const [fullscreenText, setFullscreenText] = useState(null); // { entryIndex, field, value, isEditing }
  
  const handleToggleToolbar = () => {
    setShowToolbar(!showToolbar);
  };
  
  const handleViewGlossary = async () => {
    setLoadingGlossary(true);
    setShowGlossaryModal(true);
    setGlossarySearchQuery(''); // Reset search when opening modal
    setEditingGlossaryEntry(null);
    setEditedGlossaryEntries(null);
    try {
      const content = await getGlossaryContent('glossary');
      setGlossaryContent(content);
      // Initialize edited entries with a copy of original entries
      setEditedGlossaryEntries(content.entries ? [...content.entries] : []);
    } catch (error) {
      console.error('Failed to load glossary:', error);
      setGlossaryContent({ error: error.message || 'Failed to load glossary' });
    } finally {
      setLoadingGlossary(false);
    }
  };

  const handleEditGlossaryEntry = (index, field, value) => {
    if (!editedGlossaryEntries) return;
    
    const updated = [...editedGlossaryEntries];
    updated[index] = {
      ...updated[index],
      [field]: value
    };
    setEditedGlossaryEntries(updated);
  };

  const handleSaveGlossary = async () => {
    if (!editedGlossaryEntries || !glossaryContent) return;
    
    setSavingGlossary(true);
    try {
      const updated = await updateGlossaryContent(glossaryContent.name, editedGlossaryEntries);
      setGlossaryContent(updated);
      setEditingGlossaryEntry(null);
    } catch (error) {
      console.error('Failed to save glossary:', error);
      alert(`Failed to save glossary: ${error.response?.data?.detail || error.message}`);
    } finally {
      setSavingGlossary(false);
    }
  };

  const handleCancelEditGlossary = () => {
    // Reset to original entries
    if (glossaryContent?.entries) {
      setEditedGlossaryEntries([...glossaryContent.entries]);
    }
    setEditingGlossaryEntry(null);
  };

  const handleAddGlossaryEntry = () => {
    if (!editedGlossaryEntries) return;
    
    // Add a new empty entry at the beginning
    const newEntry = { term: '', translation: '', context: '' };
    setEditedGlossaryEntries([newEntry, ...editedGlossaryEntries]);
  };

  const handleDeleteGlossaryEntry = (index) => {
    if (!editedGlossaryEntries) return;
    
    // Remove entry at the specified index
    const updated = editedGlossaryEntries.filter((_, i) => i !== index);
    setEditedGlossaryEntries(updated);
  };

  const handleViewMemory = async () => {
    setLoadingMemory(true);
    setShowMemoryModal(true);
    setMemorySearchQuery(''); // Reset search when opening modal
    setEditingMemoryEntry(null);
    setEditedMemoryEntries(null);
    try {
      const content = await getMemoryContent();
      setMemoryContent(content);
      // Initialize edited entries with a copy of original entries
      setEditedMemoryEntries(content.entries ? [...content.entries] : []);
    } catch (error) {
      console.error('Failed to load memory:', error);
      setMemoryContent({ error: error.message || 'Failed to load memory' });
    } finally {
      setLoadingMemory(false);
    }
  };

  const handleEditMemoryEntry = (index, field, value) => {
    if (!editedMemoryEntries) return;
    
    const updated = [...editedMemoryEntries];
    updated[index] = {
      ...updated[index],
      [field]: value
    };
    setEditedMemoryEntries(updated);
  };

  const handleSaveMemory = async () => {
    if (!editedMemoryEntries || !memoryContent) return;
    
    setSavingMemory(true);
    try {
      const updated = await updateMemoryContent(editedMemoryEntries);
      setMemoryContent(updated);
      setEditingMemoryEntry(null);
    } catch (error) {
      console.error('Failed to save memory:', error);
      alert(`Failed to save memory: ${error.response?.data?.detail || error.message}`);
    } finally {
      setSavingMemory(false);
    }
  };

  const handleCancelEditMemory = () => {
    // Reset to original entries
    if (memoryContent?.entries) {
      setEditedMemoryEntries([...memoryContent.entries]);
    }
    setEditingMemoryEntry(null);
  };

  const handleAddMemoryEntry = () => {
    if (!editedMemoryEntries) return;
    
    // Add a new empty entry at the beginning
    const newEntry = { source_text: '', translated_text: '', source_lang: '', target_lang: '' };
    setEditedMemoryEntries([newEntry, ...editedMemoryEntries]);
  };

  const handleDeleteMemoryEntry = (index) => {
    if (!editedMemoryEntries) return;
    
    // Remove entry at the specified index
    const updated = editedMemoryEntries.filter((_, i) => i !== index);
    setEditedMemoryEntries(updated);
  };

  const handleDeleteAllMemory = async () => {
    if (!window.confirm('Are you sure you want to delete ALL memory entries? This action cannot be undone.')) {
      return;
    }
    
    setSavingMemory(true);
    try {
      const result = await deleteAllMemoryContent();
      // Reload memory content to reflect empty state
      const content = await getMemoryContent();
      setMemoryContent(content);
      setEditedMemoryEntries(content.entries ? [...content.entries] : []);
      // Exit edit mode if active
      setEditingMemoryEntry(null);
    } catch (error) {
      console.error('Failed to delete all memory:', error);
      alert(`Failed to delete all memory: ${error.response?.data?.detail || error.message}`);
    } finally {
      setSavingMemory(false);
    }
  };

  const handleOpenFullscreen = (entryIndex, field, isEditing) => {
    if (!editedMemoryEntries && !memoryContent?.entries) return;
    // When opening fullscreen, always allow editing if we're in edit mode
    // Otherwise, allow viewing only
    const entries = editedMemoryEntries || memoryContent.entries;
    const entry = entries[entryIndex];
    if (!entry) return;
    
    // Always allow editing in fullscreen (user can edit even in view mode)
    setFullscreenText({
      entryIndex,
      field,
      value: entry[field] || '',
      isEditing: isEditing || editingMemoryEntry !== null
    });
  };

  const handleCloseFullscreen = () => {
    setFullscreenText(null);
  };

  const handleFullscreenTextChange = (value) => {
    if (!fullscreenText) return;
    setFullscreenText({
      ...fullscreenText,
      value
    });
  };

  const handleSaveFullscreenText = () => {
    if (!fullscreenText) return;
    
    // Get current entries (either edited or original)
    const currentEntries = editedMemoryEntries || memoryContent?.entries || [];
    
    // Create updated entries array
    const updated = [...currentEntries];
    updated[fullscreenText.entryIndex] = {
      ...updated[fullscreenText.entryIndex],
      [fullscreenText.field]: fullscreenText.value
    };
    
    // Update editedMemoryEntries (will be created if it doesn't exist)
    setEditedMemoryEntries(updated);
    
    // If not already in edit mode, enter edit mode to reflect the change
    if (editingMemoryEntry === null) {
      setEditingMemoryEntry({});
    }
    
    setFullscreenText(null);
  };

  // Close fullscreen on Escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && fullscreenText) {
        handleCloseFullscreen();
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [fullscreenText]);

  // Filter glossary entries based on search query (starting from first 3 characters)
  const filteredGlossaryEntries = glossaryContent?.entries?.filter((entry) => {
    if (!glossarySearchQuery || glossarySearchQuery.length < 3) {
      return true; // Show all entries if search query is less than 3 characters
    }
    const query = glossarySearchQuery.toLowerCase();
    return (
      entry.term.toLowerCase().startsWith(query) ||
      entry.translation.toLowerCase().startsWith(query) ||
      (entry.context && entry.context.toLowerCase().startsWith(query))
    );
  }) || [];
  
  // Expose toggle function to parent via window object
  useEffect(() => {
    window.translationFormToggleToolbar = handleToggleToolbar;
    return () => {
      delete window.translationFormToggleToolbar;
    };
  }, [showToolbar]);

  // Load default prompt on component mount (role-specific)
  useEffect(() => {
    const loadDefaultPrompt = async () => {
      try {
        setLoadingPrompt(true);
        // GetPrompt will return role-specific prompt for admin users
        // Non-admin users get 403 but prompt is loaded in background by backend
        const data = await getPrompt();
        if (data.prompt) {
          setCustomPrompt(data.prompt);
        }
      } catch (err) {
        // If user is not admin (403), prompt is loaded in background but not shown
        // This is expected behavior - non-admin users can still use custom prompts
        // The backend will use the role-specific prompt automatically
        if (err.response?.status === 403) {
          console.log('Prompt access restricted to admin users. Role-specific prompt will be used automatically by backend.');
          setCustomPrompt(''); // Clear for non-admin users
        } else {
          console.error('Failed to load default prompt:', err);
          setCustomPrompt('');
        }
      } finally {
        setLoadingPrompt(false);
      }
    };
    loadDefaultPrompt();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!file) {
      setError('Please select a file');
      return;
    }

    // Prevent double submission
    if (submitting || loading) {
      console.warn('Translation already in progress, ignoring duplicate submit');
      return;
    }

    setSubmitting(true);
    setLoading(true);
    setError(null);

    console.log(`[FRONTEND] Starting translation for file: ${file.name}, size: ${file.size} bytes`);
    console.log(`[FRONTEND] Translation mode: ${useStreaming ? 'STREAMING' : 'TRADITIONAL'}`);
    console.log(`[FRONTEND] Starting translation with source_lang: ${sourceLang}, target_lang: ${targetLang}`);

    try {
      const options = {
        source_lang: sourceLang,
        target_lang: targetLang,
        use_glossary: useGlossary,
        skip_memory: !useMemory,
        preserve_formatting: preserveFormatting,
        custom_prompt: customPrompt || null,
        reference_doc: referenceDoc || null,
      };

      if (useStreaming) {
        // Use streaming mode
        console.log('[FRONTEND] Using streaming translation');
        onStreamingStart(file, options);
      } else {
        // Use traditional job-based translation
        console.log('[FRONTEND] Using traditional job-based translation');
        const result = await startTranslation(file, options);
        console.log(`[FRONTEND] Translation started, job_id: ${result.job_id}`);
        onTranslationStart(result.job_id);
      }
    } catch (err) {
      console.error('[FRONTEND] Translation error:', err);
      setError(err.response?.data?.detail || err.message || 'Translation failed');
      setLoading(false);
      setSubmitting(false);
    }
  };

  return (
    <div className="translation-form-container">
      {error && (
        <div className="status-message error">
          {error}
        </div>
      )}

      <div className="translation-form-layout">
        <div className="translation-form-main">
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="file">Choose a DOCX, PDF, or TXT file</label>
          <input
            type="file"
            id="file"
            accept=".docx,.pdf,.txt"
              onChange={async (e) => {
                const selectedFile = e.target.files[0];
                if (selectedFile) {
                  setFile(selectedFile);
                  setDetectingLanguage(true);
                  try {
                    const result = await detectLanguage(selectedFile);
                    if (result.detected_language) {
                      setSourceLang(result.detected_language);
                    }
                  } catch (err) {
                    console.error('Language detection failed:', err);
                    // Keep default language on error
                  } finally {
                    setDetectingLanguage(false);
                  }
                }
              }}
            required
            disabled={loading}
          />
          {file && (
              <p className="file-info">
                Selected: {file.name} ({(file.size / 1024).toFixed(2)} KB)
                {detectingLanguage && <span className="detecting-language-text" style={{ marginLeft: '0.5rem' }}>Detecting language...</span>}
              </p>
          )}
              <p className="help-text" style={{ marginTop: '0.25rem', fontSize: '0.875rem' }}>
                Document to translate. Source language will be auto-detected.
              </p>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="source_lang">Source Language</label>
            {detectingLanguage ? (
              <div className="language-display">
                Detecting language...
              </div>
            ) : file ? (
              <div className="language-display">
                {sourceLang === 'fr' ? 'French' : sourceLang === 'de' ? 'German' : sourceLang === 'it' ? 'Italian' : sourceLang === 'en' ? 'English' : sourceLang}
                <span className="auto-detected-label">(Auto-detected)</span>
              </div>
            ) : (
              <div className="language-display language-display-placeholder">
                Will be detected from document
              </div>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="target_lang">Target Language</label>
            <select
              id="target_lang"
              value={targetLang}
              onChange={(e) => {
                const newTargetLang = e.target.value;
                console.log('[FRONTEND] Target language changed:', newTargetLang);
                setTargetLang(newTargetLang);
              }}
              disabled={loading}
            >
              <option value="it">Italian</option>
              <option value="en">English</option>
              <option value="de">German</option>
              <option value="fr">French</option>
            </select>
          </div>
        </div>

        {userRole === 'admin' && (
          <div className="form-group">
            <label htmlFor="custom_prompt">
              Translation Prompt
              {loadingPrompt && <span className="loading-indicator"> (Loading...)</span>}
            </label>
            <div className="textarea-wrapper">
              <textarea
                id="custom_prompt"
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                placeholder={loadingPrompt ? "Loading default prompt..." : "Enter custom prompt for translation..."}
                disabled={loading || loadingPrompt}
                rows={15}
                className="prompt-textarea"
                style={{
                  fontFamily: "'TX-02 Berkeley Mono', 'Berkeley Mono', monospace",
                  fontSize: '0.875rem',
                  lineHeight: '1.5',
                }}
              />
            </div>
            <p className="help-text">
              Default prompt is preloaded. You can modify it to customize the translation behavior.
            </p>
          </div>
        )}

        <button
          type="submit"
          className="button"
          disabled={loading || !file}
        >
          {loading ? 'Starting Translation...' : '🚀 Translate Document'}
        </button>
      </form>
    </div>

        {showToolbar && (
          <div className="translation-form-toolbar">
            <div className="toolbar-section">
              <div className="toolbar-header">
                <h3 className="toolbar-title">Settings</h3>
                <button
                  type="button"
                  className="toolbar-close"
                  onClick={handleToggleToolbar}
                  aria-label="Close toolbar"
                >
                  ×
                </button>
              </div>
            
            <div className="toolbar-item">
              <label htmlFor="reference_doc" className="toolbar-label">
                Reference Document
              </label>
              <input
                type="file"
                id="reference_doc"
                accept=".docx,.pdf,.txt"
                onChange={(e) => setReferenceDoc(e.target.files[0] || null)}
                disabled={loading}
                className="toolbar-file-input"
              />
              {referenceDoc && (
                <p className="toolbar-file-info">
                  {referenceDoc.name} ({(referenceDoc.size / 1024).toFixed(2)} KB)
                </p>
              )}
              <p className="toolbar-help-text">
                Defines translation guidelines with highest priority
              </p>
            </div>

            <div className="toolbar-item">
              <div className="toolbar-toggle">
                <label htmlFor="use_glossary" className="toolbar-toggle-label">
                  <input
                    type="checkbox"
                    id="use_glossary"
                    checked={useGlossary}
                    onChange={(e) => setUseGlossary(e.target.checked)}
                    disabled={loading}
                    className="toolbar-toggle-input"
                  />
                  <span className="toolbar-toggle-slider"></span>
                  <span className="toolbar-toggle-text">Glossary</span>
                </label>
              </div>
              <p className="toolbar-help-text">
                Ensures consistent terminology across translations
              </p>
              <button
                type="button"
                className="toolbar-view-button"
                onClick={handleViewGlossary}
                disabled={loading}
              >
                <svg className="toolbar-view-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M3 2h10v12H3V2zm1 1v10h8V3H4z" stroke="currentColor" strokeWidth="1.5" fill="none"/>
                  <path d="M5 5.5h6M5 7.5h4" stroke="currentColor" strokeWidth="1" strokeLinecap="round"/>
                  <path d="M11 9l2-2m0 0l1 1m-1-1l-1 1" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
                </svg>
                View glossary
              </button>
            </div>

            <div className="toolbar-item">
              <div className="toolbar-toggle">
                <label htmlFor="use_memory" className="toolbar-toggle-label">
                  <input
                    type="checkbox"
                    id="use_memory"
                    checked={useMemory}
                    onChange={(e) => setUseMemory(e.target.checked)}
                    disabled={loading}
                    className="toolbar-toggle-input"
                  />
                  <span className="toolbar-toggle-slider"></span>
                  <span className="toolbar-toggle-text">Use Translation Memory</span>
                </label>
              </div>
              <p className="toolbar-help-text">
                Uses approved translations from memory when available
              </p>
              <button
                type="button"
                className="toolbar-view-button"
                onClick={handleViewMemory}
                disabled={loading}
              >
                <svg className="toolbar-view-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M3 2h10v12H3V2zm1 1v10h8V3H4z" stroke="currentColor" strokeWidth="1.5" fill="none"/>
                  <path d="M5 5.5h6M5 7.5h4" stroke="currentColor" strokeWidth="1" strokeLinecap="round"/>
                  <path d="M11 9l2-2m0 0l1 1m-1-1l-1 1" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
                </svg>
                View memory
              </button>
            </div>

            <div className="toolbar-item">
              <div className="toolbar-toggle">
                <label htmlFor="preserve_formatting" className="toolbar-toggle-label">
                  <input
                    type="checkbox"
                    id="preserve_formatting"
                    checked={preserveFormatting}
                    onChange={(e) => setPreserveFormatting(e.target.checked)}
                    disabled={loading}
                    className="toolbar-toggle-input"
                  />
                  <span className="toolbar-toggle-slider"></span>
                  <span className="toolbar-toggle-text">Preserve PDF Formatting</span>
                </label>
              </div>
              <p className="toolbar-help-text">
                Preserves original fonts, colors, and layout in PDF files
              </p>
            </div>
          </div>
        </div>
        )}
      </div>

      {/* Glossary Modal */}
      {showGlossaryModal && (
        <div className="glossary-modal-overlay" onClick={() => setShowGlossaryModal(false)}>
          <div className="glossary-modal" onClick={(e) => e.stopPropagation()}>
            <div className="glossary-modal-header">
              <h2 className="glossary-modal-title">Glossary</h2>
              <button
                type="button"
                className="glossary-modal-close"
                onClick={() => setShowGlossaryModal(false)}
                aria-label="Close glossary"
              >
                ×
              </button>
            </div>
            <div className="glossary-modal-content">
              {loadingGlossary ? (
                <div className="glossary-loading">Loading glossary...</div>
              ) : glossaryContent?.error ? (
                <div className="glossary-error">Error: {glossaryContent.error}</div>
              ) : glossaryContent ? (
                <>
                  <div className="glossary-search-container">
                    <input
                      type="text"
                      className="glossary-search-input"
                      placeholder="Search glossary (min 3 characters)..."
                      value={glossarySearchQuery}
                      onChange={(e) => setGlossarySearchQuery(e.target.value)}
                      disabled={savingGlossary}
                    />
                  </div>
                  <div className="glossary-info">
                    <p>
                      {(() => {
                        const entriesToCount = editedGlossaryEntries || glossaryContent.entries;
                        const filteredCount = glossarySearchQuery.length >= 3 
                          ? entriesToCount.filter((entry) => {
                              const query = glossarySearchQuery.toLowerCase();
                              return (
                                (entry.term || '').toLowerCase().startsWith(query) ||
                                (entry.translation || '').toLowerCase().startsWith(query) ||
                                (entry.context && entry.context.toLowerCase().startsWith(query))
                              );
                            }).length
                          : entriesToCount.length;
                        const totalCount = entriesToCount.length;
                        const originalTotal = glossaryContent.total;
                        return `${filteredCount} of ${totalCount}${totalCount !== originalTotal ? ` (${totalCount - originalTotal > 0 ? '+' : ''}${totalCount - originalTotal} new)` : ''} entries${glossarySearchQuery.length >= 3 ? ' (filtered)' : ''}`;
                      })()}
                    </p>
                    <div className="glossary-actions">
                      <button
                        type="button"
                        className="glossary-edit-button"
                        onClick={() => setEditingGlossaryEntry({})}
                        disabled={savingGlossary || editingGlossaryEntry !== null}
                      >
                        Edit
                      </button>
                      {editingGlossaryEntry !== null && (
                        <>
                          <button
                            type="button"
                            className="glossary-add-button"
                            onClick={handleAddGlossaryEntry}
                            disabled={savingGlossary}
                          >
                            Add Entry
                          </button>
                          <button
                            type="button"
                            className="glossary-save-button"
                            onClick={handleSaveGlossary}
                            disabled={savingGlossary}
                          >
                            {savingGlossary ? 'Saving...' : 'Save'}
                          </button>
                          <button
                            type="button"
                            className="glossary-cancel-button"
                            onClick={handleCancelEditGlossary}
                            disabled={savingGlossary}
                          >
                            Cancel
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="glossary-table-container">
                    <table className="glossary-table">
                      <thead>
                        <tr>
                          <th>Term</th>
                          <th>Translation</th>
                          {glossaryContent.entries.some(e => e.context) && <th>Context</th>}
                          {editingGlossaryEntry !== null && <th>Actions</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {(() => {
                          const entriesToShow = editedGlossaryEntries || glossaryContent.entries;
                          const filtered = entriesToShow.filter((entry) => {
                            // Don't filter out empty new entries when editing
                            if (editingGlossaryEntry !== null && (!entry.term || !entry.translation)) {
                              return true;
                            }
                            if (!glossarySearchQuery || glossarySearchQuery.length < 3) {
                              return true;
                            }
                            const query = glossarySearchQuery.toLowerCase();
                            const term = (entry.term || '').toLowerCase();
                            const translation = (entry.translation || '').toLowerCase();
                            const context = (entry.context || '').toLowerCase();
                            return (
                              term.startsWith(query) ||
                              translation.startsWith(query) ||
                              (context && context.startsWith(query))
                            );
                          });
                          
                          if (filtered.length === 0 && (!editingGlossaryEntry || glossarySearchQuery.length >= 3)) {
                            return (
                              <tr>
                                <td colSpan={glossaryContent.entries.some(e => e.context) ? 3 : 2} className="glossary-no-results">
                                  No entries found matching "{glossarySearchQuery}"
                                </td>
                              </tr>
                            );
                          }
                          
                          const isEditing = editingGlossaryEntry !== null;
                          
                          return filtered.map((entry, displayIndex) => {
                            // Find the actual index in editedGlossaryEntries
                            const actualIndex = editedGlossaryEntries 
                              ? editedGlossaryEntries.findIndex((e, idx) => {
                                  // For new empty entries, match by index if term/translation are empty
                                  if (!entry.term && !entry.translation && !e.term && !e.translation) {
                                    return idx === displayIndex;
                                  }
                                  return e.term === entry.term && 
                                         e.translation === entry.translation &&
                                         (e.context || '') === (entry.context || '');
                                })
                              : displayIndex;
                            
                            const entryIndex = actualIndex >= 0 ? actualIndex : displayIndex;
                            
                            return (
                              <tr key={`entry-${entryIndex}`}>
                                <td className="glossary-term">
                                  {isEditing ? (
                                    <input
                                      type="text"
                                      className="glossary-edit-input"
                                      value={entry.term || ''}
                                      onChange={(e) => handleEditGlossaryEntry(entryIndex, 'term', e.target.value)}
                                      placeholder="Term"
                                    />
                                  ) : (
                                    entry.term || '-'
                                  )}
                                </td>
                                <td className="glossary-translation">
                                  {isEditing ? (
                                    <input
                                      type="text"
                                      className="glossary-edit-input"
                                      value={entry.translation || ''}
                                      onChange={(e) => handleEditGlossaryEntry(entryIndex, 'translation', e.target.value)}
                                      placeholder="Translation"
                                    />
                                  ) : (
                                    entry.translation || '-'
                                  )}
                                </td>
                                {glossaryContent.entries.some(e => e.context) && (
                                  <td className="glossary-context">
                                    {isEditing ? (
                                      <input
                                        type="text"
                                        className="glossary-edit-input"
                                        value={entry.context || ''}
                                        onChange={(e) => handleEditGlossaryEntry(entryIndex, 'context', e.target.value)}
                                        placeholder="Context (optional)"
                                      />
                                    ) : (
                                      entry.context || '-'
                                    )}
                                  </td>
                                )}
                                {isEditing && (
                                  <td className="glossary-actions-cell">
                                    <button
                                      type="button"
                                      className="glossary-delete-button"
                                      onClick={() => handleDeleteGlossaryEntry(entryIndex)}
                                      disabled={savingGlossary}
                                      aria-label="Delete entry"
                                    >
                                      ×
                                    </button>
                                  </td>
                                )}
                              </tr>
                            );
                          });
                        })()}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {/* Memory Modal */}
      {showMemoryModal && (
        <div className="glossary-modal-overlay" onClick={() => setShowMemoryModal(false)}>
          <div className="glossary-modal" onClick={(e) => e.stopPropagation()}>
            <div className="glossary-modal-header">
              <h2 className="glossary-modal-title">Translation Memory</h2>
              <button
                type="button"
                className="glossary-modal-close"
                onClick={() => setShowMemoryModal(false)}
                aria-label="Close memory"
              >
                ×
              </button>
            </div>
            <div className="glossary-modal-content">
              {loadingMemory ? (
                <div className="glossary-loading">Loading memory...</div>
              ) : memoryContent?.error ? (
                <div className="glossary-error">Error: {memoryContent.error}</div>
              ) : memoryContent ? (
                <>
                  <div className="glossary-search-container">
                    <input
                      type="text"
                      className="glossary-search-input"
                      placeholder="Search memory (min 3 characters)..."
                      value={memorySearchQuery}
                      onChange={(e) => setMemorySearchQuery(e.target.value)}
                      disabled={savingMemory}
                    />
                  </div>
                  <div className="glossary-info">
                    <p>
                      {(() => {
                        const entriesToCount = editedMemoryEntries || memoryContent.entries;
                        const filteredCount = memorySearchQuery.length >= 3 
                          ? entriesToCount.filter((entry) => {
                              const query = memorySearchQuery.toLowerCase();
                              return (
                                (entry.source_text || '').toLowerCase().includes(query) ||
                                (entry.translated_text || '').toLowerCase().includes(query) ||
                                (entry.source_lang || '').toLowerCase().includes(query) ||
                                (entry.target_lang || '').toLowerCase().includes(query)
                              );
                            }).length
                          : entriesToCount.length;
                        const totalCount = entriesToCount.length;
                        const originalTotal = memoryContent.total;
                        return `${filteredCount} of ${totalCount}${totalCount !== originalTotal ? ` (${totalCount - originalTotal > 0 ? '+' : ''}${totalCount - originalTotal} new)` : ''} entries${memorySearchQuery.length >= 3 ? ' (filtered)' : ''}`;
                      })()}
                    </p>
                    <div className="glossary-actions">
                      <button
                        type="button"
                        className="glossary-edit-button"
                        onClick={() => setEditingMemoryEntry({})}
                        disabled={savingMemory || editingMemoryEntry !== null}
                      >
                        Edit
                      </button>
                      {editingMemoryEntry !== null && (
                        <>
                          <button
                            type="button"
                            className="glossary-add-button"
                            onClick={handleAddMemoryEntry}
                            disabled={savingMemory}
                          >
                            Add Entry
                          </button>
                          <button
                            type="button"
                            className="glossary-save-button"
                            onClick={handleSaveMemory}
                            disabled={savingMemory}
                          >
                            {savingMemory ? 'Saving...' : 'Save'}
                          </button>
                          <button
                            type="button"
                            className="glossary-cancel-button"
                            onClick={handleCancelEditMemory}
                            disabled={savingMemory}
                          >
                            Cancel
                          </button>
                        </>
                      )}
                      <button
                        type="button"
                        className="glossary-delete-all-button"
                        onClick={handleDeleteAllMemory}
                        disabled={savingMemory || loadingMemory || !memoryContent || memoryContent.total === 0}
                        title="Delete all memory entries"
                      >
                        Delete All
                      </button>
                    </div>
                  </div>
                  <div className="glossary-table-container">
                    <table className="glossary-table memory-table">
                      <thead>
                        <tr>
                          <th className="memory-lang-col">Source Language</th>
                          <th className="memory-lang-col">Target Language</th>
                          <th>Source Text</th>
                          <th>Translated Text</th>
                          {editingMemoryEntry !== null && <th>Actions</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {(() => {
                          const entriesToShow = editedMemoryEntries || memoryContent.entries;
                          const filtered = entriesToShow.filter((entry) => {
                            // Don't filter out empty new entries when editing
                            if (editingMemoryEntry !== null && (!entry.source_text || !entry.translated_text)) {
                              return true;
                            }
                            if (!memorySearchQuery || memorySearchQuery.length < 3) {
                              return true;
                            }
                            const query = memorySearchQuery.toLowerCase();
                            return (
                              (entry.source_text || '').toLowerCase().includes(query) ||
                              (entry.translated_text || '').toLowerCase().includes(query) ||
                              (entry.source_lang || '').toLowerCase().includes(query) ||
                              (entry.target_lang || '').toLowerCase().includes(query)
                            );
                          });
                          
                          if (filtered.length === 0 && (!editingMemoryEntry || memorySearchQuery.length >= 3)) {
                            return (
                              <tr>
                                <td colSpan={editingMemoryEntry !== null ? 5 : 4} className="glossary-no-results">
                                  No entries found matching "{memorySearchQuery}"
                                </td>
                              </tr>
                            );
                          }
                          
                          const isEditing = editingMemoryEntry !== null;
                          
                          return filtered.map((entry, displayIndex) => {
                            // Find the actual index in entriesToShow (which is editedMemoryEntries when editing)
                            // Since filtered entries are references to entriesToShow entries, we can find the index directly
                            const entryIndex = entriesToShow.findIndex((e) => {
                              // Match by key if available (most reliable)
                              if (entry.key && e.key) {
                                return e.key === entry.key;
                              }
                              // For entries without keys (new entries), match by object reference
                              return e === entry;
                            });
                            
                            // Fallback to displayIndex if not found (shouldn't happen, but safer)
                            const actualIndex = entryIndex !== -1 ? entryIndex : displayIndex;
                            
                            return (
                              <tr key={entry.key || `entry-${actualIndex}`}>
                                <td className="memory-lang-col">
                                  {isEditing ? (
                                    <input
                                      type="text"
                                      className="glossary-edit-input"
                                      value={entry.source_lang || ''}
                                      onChange={(e) => handleEditMemoryEntry(actualIndex, 'source_lang', e.target.value)}
                                      placeholder="Source lang"
                                    />
                                  ) : (
                                    entry.source_lang || '-'
                                  )}
                                </td>
                                <td className="memory-lang-col">
                                  {isEditing ? (
                                    <input
                                      type="text"
                                      className="glossary-edit-input"
                                      value={entry.target_lang || ''}
                                      onChange={(e) => handleEditMemoryEntry(actualIndex, 'target_lang', e.target.value)}
                                      placeholder="Target lang"
                                    />
                                  ) : (
                                    entry.target_lang || '-'
                                  )}
                                </td>
                                <td className="memory-text-cell">
                                  <div className="memory-text-cell-wrapper">
                                    {isEditing ? (
                                      <textarea
                                        className="glossary-edit-input memory-edit-textarea"
                                        value={entry.source_text || ''}
                                        onChange={(e) => handleEditMemoryEntry(actualIndex, 'source_text', e.target.value)}
                                        placeholder="Source text"
                                        rows={3}
                                      />
                                    ) : (
                                      <div className="memory-text-content">{entry.source_text || '-'}</div>
                                    )}
                                    <button
                                      type="button"
                                      className="memory-fullscreen-toggle"
                                      onClick={() => handleOpenFullscreen(actualIndex, 'source_text', isEditing)}
                                      title="Open in fullscreen"
                                      aria-label="Open in fullscreen"
                                    >
                                      🗖
                                    </button>
                                  </div>
                                </td>
                                <td className="memory-text-cell">
                                  <div className="memory-text-cell-wrapper">
                                    {isEditing ? (
                                      <textarea
                                        className="glossary-edit-input memory-edit-textarea"
                                        value={entry.translated_text || ''}
                                        onChange={(e) => handleEditMemoryEntry(actualIndex, 'translated_text', e.target.value)}
                                        placeholder="Translated text"
                                        rows={3}
                                      />
                                    ) : (
                                      <div className="memory-text-content">{entry.translated_text || '-'}</div>
                                    )}
                                    <button
                                      type="button"
                                      className="memory-fullscreen-toggle"
                                      onClick={() => handleOpenFullscreen(actualIndex, 'translated_text', isEditing)}
                                      title="Open in fullscreen"
                                      aria-label="Open in fullscreen"
                                    >
                                      🗖
                                    </button>
                                  </div>
                                </td>
                                {isEditing && (
                                  <td className="glossary-actions-cell">
                                    <button
                                      type="button"
                                      className="glossary-delete-button"
                                      onClick={() => handleDeleteMemoryEntry(actualIndex)}
                                      disabled={savingMemory}
                                      aria-label="Delete entry"
                                    >
                                      ×
                                    </button>
                                  </td>
                                )}
                              </tr>
                            );
                          });
                        })()}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {/* Fullscreen Text Modal */}
      {fullscreenText && (
        <div className="memory-fullscreen-overlay" onClick={handleCloseFullscreen}>
          <div className="memory-fullscreen-modal" onClick={(e) => e.stopPropagation()}>
            <div className="memory-fullscreen-header">
              <h2 className="memory-fullscreen-title">
                {fullscreenText.field === 'source_text' ? 'Source Text' : 'Translated Text'}
              </h2>
              <button
                type="button"
                className="memory-fullscreen-close"
                onClick={handleCloseFullscreen}
                aria-label="Close fullscreen"
              >
                ×
              </button>
            </div>
            <div className="memory-fullscreen-content">
              {fullscreenText.isEditing ? (
                <textarea
                  className="memory-fullscreen-textarea"
                  value={fullscreenText.value}
                  onChange={(e) => handleFullscreenTextChange(e.target.value)}
                  placeholder={fullscreenText.field === 'source_text' ? 'Source text' : 'Translated text'}
                  autoFocus
                />
              ) : (
                <div className="memory-fullscreen-text">
                  {fullscreenText.value || '-'}
                </div>
              )}
            </div>
            {fullscreenText.isEditing && (
              <div className="memory-fullscreen-actions">
                <button
                  type="button"
                  className="glossary-save-button"
                  onClick={handleSaveFullscreenText}
                >
                  Save
                </button>
                <button
                  type="button"
                  className="glossary-cancel-button"
                  onClick={handleCloseFullscreen}
                >
                  Cancel
                </button>
              </div>
            )}
            {!fullscreenText.isEditing && (
              <div className="memory-fullscreen-actions">
                <button
                  type="button"
                  className="glossary-edit-button"
                  onClick={() => setFullscreenText({...fullscreenText, isEditing: true})}
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="glossary-cancel-button"
                  onClick={handleCloseFullscreen}
                >
                  Close
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default TranslationForm;

