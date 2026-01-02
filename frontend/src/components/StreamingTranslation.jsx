import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { startTranslationStreaming } from '../services/api';
import EditableTranslatedText from './EditableTranslatedText';
import './TranslationStatus.css';

function StreamingTranslation({ file, options, onComplete, onReset }) {
  const [translatedText, setTranslatedText] = useState('');
  const [status, setStatus] = useState('streaming'); // 'streaming', 'completed', 'error'
  const [error, setError] = useState(null);
  const [stats, setStats] = useState({
    characters: 0,
    words: 0,
    duration: 0,
    speed: 0,
  });
  const [translationStats, setTranslationStats] = useState({
    used_memory: false,
    glossary_matches: 0,
    memory_hits: 0,
    source_lang: '',
    target_lang: '',
  });
  const outputRef = useRef(null);
  const statsIntervalRef = useRef(null);
  const startTimeRef = useRef(null);
  const translatedTextRef = useRef('');

  useEffect(() => {
    startTimeRef.current = Date.now();
    startStreaming();

    // Update stats periodically while streaming
    statsIntervalRef.current = setInterval(() => {
      if (status === 'streaming' && startTimeRef.current) {
        updateStats(translatedTextRef.current);
      }
    }, 100);

    return () => {
      if (statsIntervalRef.current) {
        clearInterval(statsIntervalRef.current);
      }
    };
  }, []);

  useEffect(() => {
    // Auto-scroll to bottom as new content arrives
    if (outputRef.current && status === 'streaming') {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [translatedText, status]);

  const updateStats = (text = null) => {
    const textToMeasure = text !== null ? text : translatedText;
    const elapsed = startTimeRef.current ? (Date.now() - startTimeRef.current) / 1000 : 0;
    const chars = textToMeasure.length;
    const words = textToMeasure.trim().split(/\s+/).filter(w => w).length;
    const speed = elapsed > 0 ? Math.round(chars / elapsed) : 0;

    setStats({
      characters: chars,
      words: words,
      duration: elapsed.toFixed(1),
      speed: speed,
    });
  };

  const startStreaming = async () => {
    try {
      await startTranslationStreaming(
        file,
        options,
        // onChunk callback
        (chunk) => {
          setTranslatedText(prev => {
            const newText = prev + chunk;
            translatedTextRef.current = newText; // Update ref for real-time stats
            return newText;
          });
        },
        // onComplete callback
        (fullText, message, apiStats) => {
          setTranslatedText(fullText);
          translatedTextRef.current = fullText; // Update ref
          setStatus('completed');
          updateStats(fullText); // Pass fullText directly to avoid stale state
          if (apiStats) {
            setTranslationStats(apiStats);
          }
          if (statsIntervalRef.current) {
            clearInterval(statsIntervalRef.current);
          }
          if (onComplete) {
            onComplete(fullText);
          }
        },
        // onError callback
        (err) => {
          setError(err.message || 'Streaming failed');
          setStatus('error');
          if (statsIntervalRef.current) {
            clearInterval(statsIntervalRef.current);
          }
        }
      );
    } catch (err) {
      setError(err.message || 'Failed to start streaming');
      setStatus('error');
      if (statsIntervalRef.current) {
        clearInterval(statsIntervalRef.current);
      }
    }
  };

  return (
    <div className="card">
      <div className={`status-message ${status === 'completed' ? 'success' : status === 'error' ? 'error' : 'info'}`}>
        {status === 'streaming' && '⚡ Streaming translation in real-time...'}
        {status === 'completed' && '✅ Translation completed!'}
        {status === 'error' && `❌ Error: ${error}`}
      </div>

      {status === 'streaming' && (
        <div className="streaming-stats">
          <div className="stat">
            <strong>Characters:</strong> <span>{stats.characters}</span>
          </div>
          <div className="stat">
            <strong>Words:</strong> <span>{stats.words}</span>
          </div>
          <div className="stat">
            <strong>Duration:</strong> <span>{stats.duration}s</span>
          </div>
          <div className="stat">
            <strong>Speed:</strong> <span>{stats.speed} chars/s</span>
          </div>
        </div>
      )}

      <div className="comparison-content">
        <div className="comparison-header">
          <h3>Translated Text ({options.target_lang?.toUpperCase() || 'Target'})</h3>
        </div>

        <div
          ref={outputRef}
          className={`streaming-output-box ${status === 'streaming' ? 'streaming' : ''}`}
        >
          {translatedText ? (
            status === 'streaming' ? (
              // During streaming: show raw text to avoid broken markdown rendering
              <>
                {translatedText}
                <span className="cursor-blink" style={{
                  display: 'inline-block',
                  width: '8px',
                  height: '16px',
                  backgroundColor: '#667eea',
                  marginLeft: '2px',
                  animation: 'blink 1s step-start infinite',
                }} />
              </>
            ) : (
              // After completion: render with editable text component
              <EditableTranslatedText
                paragraphs={[translatedText]}
                sourceLang={translationStats.source_lang || options.source_lang}
                targetLang={translationStats.target_lang || options.target_lang}
                glossaryName="glossary"
              />
            )
          ) : (
            <p style={{ color: 'var(--text-tertiary)' }}>Waiting for translation to start...</p>
          )}
        </div>

        {status === 'completed' && (
          <>
            <div className="stats" style={{ marginTop: '1rem' }}>
              <div className="stat">
                <strong>Total Characters:</strong> {stats.characters}
              </div>
              <div className="stat">
                <strong>Total Words:</strong> {stats.words}
              </div>
              <div className="stat">
                <strong>Total Duration:</strong> {stats.duration}s
              </div>
              <div className="stat">
                <strong>Average Speed:</strong> {stats.speed} chars/s
              </div>
            </div>

            {translationStats && (
              <div className="stats" style={{ marginTop: '1rem', borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
                <div className="stat">
                  <strong>Source:</strong> {translationStats.used_memory ? '💾 Memory (cached)' : '🤖 Claude API'}
                </div>
                {translationStats.glossary_matches > 0 && (
                  <div className="stat">
                    <strong>Glossary Matches:</strong> {translationStats.glossary_matches}
                  </div>
                )}
                {translationStats.memory_hits > 0 && (
                  <div className="stat">
                    <strong>Similar in Memory:</strong> {translationStats.memory_hits}
                  </div>
                )}
                <div className="stat">
                  <strong>Languages:</strong> {translationStats.source_lang?.toUpperCase()} → {translationStats.target_lang?.toUpperCase()}
                </div>
              </div>
            )}
          </>
        )}

        {(status === 'completed' || status === 'error') && (
          <div className="action-buttons" style={{ marginTop: '1rem' }}>
            <button className="button button-secondary" onClick={onReset}>
              {status === 'error' ? 'Try Again' : 'Translate Another Document'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default StreamingTranslation;
