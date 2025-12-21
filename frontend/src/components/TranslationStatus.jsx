import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { downloadTranslation, getTranslationReport, cancelTranslation, downloadTranslatedText } from '../services/api';
import './TranslationStatus.css';

function TranslationStatus({ jobId, status, onReset, onReportUpdate }) {
  const [report, setReport] = useState(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadingText, setDownloadingText] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [fullscreenColumn, setFullscreenColumn] = useState(null); // 'original', 'translated', or null

  useEffect(() => {
    if (status?.status === 'completed' && !report) {
      loadReport();
    }
  }, [status]);

  const loadReport = async () => {
    try {
      const reportData = await getTranslationReport(jobId);
      setReport(reportData);
      // Notify parent component about the report
      if (onReportUpdate) {
        onReportUpdate(reportData);
      }
    } catch (error) {
      console.error('Failed to load report:', error);
    }
  };

  const handleDownload = async () => {
    setDownloading(true);
    try {
      await downloadTranslation(jobId);
    } catch (error) {
      console.error('Download failed:', error);
      alert('Failed to download translation');
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadText = async () => {
    setDownloadingText(true);
    try {
      await downloadTranslatedText(jobId);
    } catch (error) {
      console.error('Download text failed:', error);
      alert('Failed to download translated text');
    } finally {
      setDownloadingText(false);
    }
  };

  const handleCancel = async () => {
    if (!window.confirm('Are you sure you want to cancel this translation?')) {
      return;
    }
    
    setCancelling(true);
    try {
      await cancelTranslation(jobId);
      alert('Translation cancellation requested. The job will stop soon.');
    } catch (error) {
      console.error('Cancel failed:', error);
      alert(error.response?.data?.detail || 'Failed to cancel translation');
    } finally {
      setCancelling(false);
    }
  };

  const toggleFullscreen = (column) => {
    if (fullscreenColumn === column) {
      setFullscreenColumn(null);
    } else {
      setFullscreenColumn(column);
    }
  };

  // Close fullscreen on Escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && fullscreenColumn) {
        setFullscreenColumn(null);
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [fullscreenColumn]);

  if (!status) {
    return <div className="card">Loading status...</div>;
  }

  const getStatusMessage = () => {
    switch (status.status) {
      case 'pending':
        return { type: 'info', text: 'Translation queued...' };
      case 'in_progress':
        return { type: 'info', text: 'Translation in progress...' };
      case 'completed':
        return { type: 'success', text: '✅ Translation completed!' };
      case 'cancelled':
        return { type: 'error', text: '⏹️ Translation cancelled' };
      case 'failed':
        return { type: 'error', text: `❌ Translation failed: ${status.error || 'Unknown error'}` };
      default:
        return { type: 'info', text: 'Unknown status' };
    }
  };

  const statusMsg = getStatusMessage();

  return (
    <div className="card">
      {status.status !== 'completed' && (
      <div className={`status-message ${statusMsg.type}`}>
        {statusMsg.text}
      </div>
      )}

      {(status.status === 'in_progress' || status.status === 'pending') && (
        <>
          {status.total_paragraphs > 0 && (
            <>
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{ width: `${(status.progress || 0) * 100}%` }}
                >
                  {status.progress ? `${Math.round(status.progress * 100)}%` : ''}
                </div>
              </div>
              <p className="progress-text">
                Paragraph {status.current_paragraph || 0} of {status.total_paragraphs}
              </p>
            </>
          )}
          <div className="action-buttons">
            <button
              className="button button-danger"
              onClick={handleCancel}
              disabled={cancelling}
            >
              {cancelling ? 'Cancelling...' : '⏹️ Cancel Translation'}
            </button>
          </div>
        </>
      )}

      {status.status === 'completed' && (
        <>
          {/* Display original and translated text side-by-side */}
          {status.translated_text && status.translated_text.length > 0 ? (
            <div className="comparison-content">
              <div className="comparison-header">
                <div className="action-buttons">
                  <button
                    className="button"
                    onClick={handleDownload}
                    disabled={downloading}
                  >
                    {downloading ? 'Downloading...' : '📄 Download PDF'}
                  </button>
                  {status.translated_text && (
                    <button
                      className="button button-secondary"
                      onClick={handleDownloadText}
                      disabled={downloadingText}
                    >
                      {downloadingText ? 'Downloading...' : '📝 Download as Text'}
                    </button>
                  )}
                </div>
              </div>
              <div className={`comparison-container ${fullscreenColumn ? 'fullscreen-active' : ''}`}>
                <div className={`original-column ${fullscreenColumn === 'original' ? 'fullscreen' : ''} ${fullscreenColumn === 'translated' ? 'hidden' : ''}`}>
                  <div className="column-header">
                  <h4>Original ({status.report?.source_lang || 'Source'})</h4>
                    <button
                      className="fullscreen-toggle"
                      onClick={() => toggleFullscreen('original')}
                      title={fullscreenColumn === 'original' ? 'Exit fullscreen (Esc)' : 'Enter fullscreen'}
                      aria-label={fullscreenColumn === 'original' ? 'Exit fullscreen' : 'Enter fullscreen'}
                    >
                      {fullscreenColumn === 'original' ? '🗗' : '🗖'}
                    </button>
                  </div>
                  <div className="text-content original-text markdown-content">
                    {status.original_text && status.original_text.length > 0 ? (
                      status.original_text.map((paragraph, idx) => (
                        paragraph ? (
                          <div key={idx} className="paragraph-wrapper">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {paragraph}
                            </ReactMarkdown>
                          </div>
                        ) : null
                      ))
                    ) : (
                      <p className="placeholder">Original text not available</p>
                    )}
                  </div>
                </div>
                <div className={`translated-column ${fullscreenColumn === 'translated' ? 'fullscreen' : ''} ${fullscreenColumn === 'original' ? 'hidden' : ''}`}>
                  <div className="column-header">
                  <h4>Translated ({status.report?.target_lang || 'Target'})</h4>
                    <button
                      className="fullscreen-toggle"
                      onClick={() => toggleFullscreen('translated')}
                      title={fullscreenColumn === 'translated' ? 'Exit fullscreen (Esc)' : 'Enter fullscreen'}
                      aria-label={fullscreenColumn === 'translated' ? 'Exit fullscreen' : 'Enter fullscreen'}
                    >
                      {fullscreenColumn === 'translated' ? '🗗' : '🗖'}
                    </button>
                  </div>
                  <div className="text-content translated-text markdown-content">
                    {status.translated_text.map((paragraph, idx) => {
                      if (!paragraph) return null;
                      
                      // Process paragraph to handle both glossary and memory tags
                      // Split by both tag types and render appropriately
                      const parts = paragraph.split(/(<glossary>.*?<\/glossary>|<memory>.*?<\/memory>)/g);
                      
                      return (
                        <div key={idx} className="paragraph-wrapper">
                          {parts.map((part, partIdx) => {
                            // Handle glossary tags
                            if (part.startsWith('<glossary>') && part.endsWith('</glossary>')) {
                              const glossaryText = part.slice(10, -11); // Remove <glossary></glossary>
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
                              const memoryText = part.slice(8, -9); // Remove <memory></memory>
                              return (
                                <span key={partIdx} className="memory-term">
                                  {memoryText}
                                </span>
                              );
                            }
                            
                            // Regular text - render with markdown (but preserve any remaining tags)
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
                </div>
              </div>
            </div>
          ) : (
            <div className="status-message info">
              <p>Translation completed. Loading translated content...</p>
            </div>
          )}

        </>
      )}

      {(status.status === 'failed' || status.status === 'cancelled') && (
        <button
          className="button button-secondary"
          onClick={onReset}
        >
          {status.status === 'cancelled' ? 'Start New Translation' : 'Try Again'}
        </button>
      )}
    </div>
  );
}

export default TranslationStatus;

