import { useState, useEffect } from 'react';
import { startTranslation, getPrompt } from '../services/api';
import './TranslationForm.css';

function TranslationForm({ onTranslationStart }) {
  const [file, setFile] = useState(null);
  const [sourceLang, setSourceLang] = useState('fr');
  const [targetLang, setTargetLang] = useState('it');
  const [useGlossary, setUseGlossary] = useState(true);
  const [skipMemory, setSkipMemory] = useState(true);
  const [customPrompt, setCustomPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [loadingPrompt, setLoadingPrompt] = useState(true);

  // Load default prompt on component mount
  useEffect(() => {
    const loadDefaultPrompt = async () => {
      try {
        setLoadingPrompt(true);
        const data = await getPrompt();
        if (data.prompt) {
          setCustomPrompt(data.prompt);
        }
      } catch (err) {
        console.error('Failed to load default prompt:', err);
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

    try {
      const result = await startTranslation(file, {
        source_lang: sourceLang,
        target_lang: targetLang,
        use_glossary: useGlossary,
        skip_memory: skipMemory,
        custom_prompt: customPrompt || null,
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
    <div className="card">
      {error && (
        <div className="status-message error">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="file">Choose a DOCX, PDF, or TXT file</label>
          <input
            type="file"
            id="file"
            accept=".docx,.pdf,.txt"
            onChange={(e) => setFile(e.target.files[0])}
            required
            disabled={loading}
          />
          {file && (
            <p className="file-info">Selected: {file.name} ({(file.size / 1024).toFixed(2)} KB)</p>
          )}
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="source_lang">Source Language</label>
            <select
              id="source_lang"
              value={sourceLang}
              onChange={(e) => setSourceLang(e.target.value)}
              disabled={loading}
            >
              <option value="fr">French</option>
              <option value="de">German</option>
              <option value="it">Italian</option>
              <option value="en">English</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="target_lang">Target Language</label>
            <select
              id="target_lang"
              value={targetLang}
              onChange={(e) => setTargetLang(e.target.value)}
              disabled={loading}
            >
              <option value="it">Italian</option>
              <option value="en">English</option>
              <option value="de">German</option>
              <option value="fr">French</option>
            </select>
          </div>
        </div>

        <div className="form-group checkbox-group-container">
          <div className="checkbox-group">
            <input
              type="checkbox"
              id="use_glossary"
              checked={useGlossary}
              onChange={(e) => setUseGlossary(e.target.checked)}
              disabled={loading}
            />
            <label htmlFor="use_glossary">Use Glossary</label>
          </div>
          <div className="checkbox-group">
            <input
              type="checkbox"
              id="skip_memory"
              checked={skipMemory}
              onChange={(e) => setSkipMemory(e.target.checked)}
              disabled={loading}
            />
            <label htmlFor="skip_memory">Skip Translation Memory</label>
          </div>
          <p className="help-text" style={{ marginTop: '0.5rem' }}>
            Glossary: Ensures consistent terminology. Memory: Uses approved translations when available.
          </p>
        </div>

        <div className="form-group">
          <label htmlFor="custom_prompt">
            Translation Prompt
            {loadingPrompt && <span className="loading-indicator"> (Loading...)</span>}
          </label>
          <textarea
            id="custom_prompt"
            value={customPrompt}
            onChange={(e) => setCustomPrompt(e.target.value)}
            placeholder={loadingPrompt ? "Loading default prompt..." : "Enter custom prompt for translation..."}
            disabled={loading || loadingPrompt}
            rows={15}
            style={{
              fontFamily: 'monospace',
              fontSize: '0.875rem',
              lineHeight: '1.5',
            }}
          />
          <p className="help-text">
            Default prompt is preloaded. You can modify it to customize the translation behavior.
          </p>
        </div>


        <button
          type="submit"
          className="button"
          disabled={loading || !file}
        >
          {loading ? 'Starting Translation...' : '🚀 Translate Document'}
        </button>
      </form>
    </div>
  );
}

export default TranslationForm;

