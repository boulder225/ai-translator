import { useState, useEffect } from 'react';
import { startTranslation, getPrompt, detectLanguage, getGlossaryContent } from '../services/api';
import './TranslationForm.css';

function TranslationForm({ onTranslationStart, userRole }) {
  const [file, setFile] = useState(null);
  const [referenceDoc, setReferenceDoc] = useState(null);
  const [sourceLang, setSourceLang] = useState('fr');
  const [targetLang, setTargetLang] = useState('it');
  const [useGlossary, setUseGlossary] = useState(true);
  const [useMemory, setUseMemory] = useState(true);
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
  
  const handleToggleToolbar = () => {
    setShowToolbar(!showToolbar);
  };
  
  const handleViewGlossary = async () => {
    setLoadingGlossary(true);
    setShowGlossaryModal(true);
    setGlossarySearchQuery(''); // Reset search when opening modal
    try {
      const content = await getGlossaryContent('glossary');
      setGlossaryContent(content);
    } catch (error) {
      console.error('Failed to load glossary:', error);
      setGlossaryContent({ error: error.message || 'Failed to load glossary' });
    } finally {
      setLoadingGlossary(false);
    }
  };

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

    console.log(`[FRONTEND] Starting translation with source_lang: ${sourceLang}, target_lang: ${targetLang}`);

    try {
      const result = await startTranslation(file, {
        source_lang: sourceLang,
        target_lang: targetLang,
        use_glossary: useGlossary,
        skip_memory: !useMemory,
        custom_prompt: customPrompt || null,
        reference_doc: referenceDoc || null,
      });

      console.log(`[FRONTEND] Translation started, job_id: ${result.job_id}`);
      onTranslationStart(result.job_id);
    } catch (err) {
      console.error('[FRONTEND] Translation error:', err);
      setError(err.response?.data?.detail || err.message || 'Translation failed');
    } finally {
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
                    />
                  </div>
                  <div className="glossary-info">
                    <p>
                      {filteredGlossaryEntries.length} of {glossaryContent.total} entries
                      {glossarySearchQuery.length >= 3 && ` (filtered)`}
                    </p>
                  </div>
                  <div className="glossary-table-container">
                    <table className="glossary-table">
                      <thead>
                        <tr>
                          <th>Term</th>
                          <th>Translation</th>
                          {glossaryContent.entries.some(e => e.context) && <th>Context</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {filteredGlossaryEntries.length > 0 ? (
                          filteredGlossaryEntries.map((entry, index) => (
                            <tr key={index}>
                              <td className="glossary-term">{entry.term}</td>
                              <td className="glossary-translation">{entry.translation}</td>
                              {glossaryContent.entries.some(e => e.context) && (
                                <td className="glossary-context">{entry.context || '-'}</td>
                              )}
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={glossaryContent.entries.some(e => e.context) ? 3 : 2} className="glossary-no-results">
                              No entries found matching "{glossarySearchQuery}"
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default TranslationForm;

