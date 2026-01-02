import { useState, useEffect } from 'react';
import './App.css';
import Login from './components/Login';
import TranslationForm from './components/TranslationForm';
import TranslationStatus from './components/TranslationStatus';
import StreamingTranslation from './components/StreamingTranslation';
import { getTranslationStatus } from './services/api';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentJob, setCurrentJob] = useState(null);
  const [status, setStatus] = useState(null);
  const [report, setReport] = useState(null);
  const [username, setUsername] = useState('');
  const [userRole, setUserRole] = useState('');
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('theme') || 'light';
  });
  const [streamingMode, setStreamingMode] = useState(false);
  const [streamingFile, setStreamingFile] = useState(null);
  const [streamingOptions, setStreamingOptions] = useState(null);

  // Apply theme to document
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  // Check authentication status on mount
  useEffect(() => {
    const authStatus = localStorage.getItem('isAuthenticated');
    if (authStatus === 'true') {
      setIsAuthenticated(true);
      // Ensure userRole is set - if missing, set default based on username
      const storedUsername = localStorage.getItem('username') || '';
      const storedUserRole = localStorage.getItem('userRole');
      if (!storedUserRole && storedUsername) {
        // Set role based on username pattern (for users who logged in before role system)
        const usernameLower = storedUsername.toLowerCase();
        const role = (usernameLower.includes('admin') || usernameLower.startsWith('admin_')) ? 'admin' : 'user';
        localStorage.setItem('userRole', role);
        setUserRole(role);
      } else {
        setUserRole(storedUserRole || '');
      }
      setUsername(storedUsername);
    }
  }, []);

  useEffect(() => {
    if (currentJob) {
      pollStatus();
    }
  }, [currentJob]);



  const pollStatus = async () => {
    if (!currentJob) return;

    try {
      const statusData = await getTranslationStatus(currentJob);
      setStatus(statusData);

      // Continue polling if in progress
      if (statusData.status === 'in_progress' || statusData.status === 'pending') {
        setTimeout(pollStatus, 2000); // Poll every 2 seconds
      } else if (statusData.status === 'completed') {
        // Translation completed - statusData should include translated_text
        console.log('[FRONTEND] Translation completed, translated_text available:', statusData.translated_text ? 'Yes' : 'No');
      }
    } catch (error) {
      console.error('Failed to get status:', error);
    }
  };

  const handleTranslationStart = (jobId) => {
    setCurrentJob(jobId);
    setStatus({ status: 'pending', job_id: jobId });
    setReport(null); // Reset report when starting new translation
  };

  const handleStreamingStart = (file, options) => {
    setStreamingMode(true);
    setStreamingFile(file);
    setStreamingOptions(options);
    setCurrentJob('streaming'); // Use placeholder job ID
  };

  const handleStreamingComplete = (translatedText) => {
    console.log('[FRONTEND] Streaming translation completed');
    // Could save translated text to state if needed
  };

  const handleReset = () => {
    setCurrentJob(null);
    setStatus(null);
    setReport(null);
    setStreamingMode(false);
    setStreamingFile(null);
    setStreamingOptions(null);
  };

  const handleReportUpdate = (reportData) => {
    setReport(reportData);
  };

  const handleLogin = () => {
    setIsAuthenticated(true);
    const storedUsername = localStorage.getItem('username') || '';
    const storedUserRole = localStorage.getItem('userRole') || '';
    setUsername(storedUsername);
    setUserRole(storedUserRole);
  };

  const handleLogout = () => {
    localStorage.removeItem('isAuthenticated');
    localStorage.removeItem('username');
    localStorage.removeItem('userRole');
    setIsAuthenticated(false);
    setCurrentJob(null);
    setStatus(null);
    setReport(null);
  };

  // Show login page if not authenticated
  if (!isAuthenticated) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="App">
      <nav className="App-nav">
        <div className="nav-container">
          <div className="nav-menu">
            {report && report.stats ? (
              <div className="nav-stats">
                <span className="nav-stat-item">
                  <span className="nav-stat-value">{report.stats?.paragraphs_total || 0}</span>
                  <span className="nav-stat-label">Paragraphs</span>
                </span>
                <span className="nav-stat-separator">•</span>
                <span className="nav-stat-item">
                  <span className="nav-stat-value">{report.stats?.model_calls || 0}</span>
                  <span className="nav-stat-label">API Calls</span>
                </span>
                <span className="nav-stat-separator">•</span>
                <span className="nav-stat-item">
                  <span className="nav-stat-value">{report.stats?.reused_from_memory || 0}</span>
                  <span className="nav-stat-label">Memory</span>
                </span>
                <span className="nav-stat-separator">•</span>
                <span className="nav-stat-item">
                  <span className="nav-stat-value">{report.stats?.glossary_matches || 0}</span>
                  <span className="nav-stat-label">Glossary</span>
                </span>
                {report.stats?.reference_doc_applied !== undefined && (
                  <>
                    <span className="nav-stat-separator">•</span>
                    <span className="nav-stat-item">
                      <span className="nav-stat-value">{report.stats?.reference_doc_applied || 0}</span>
                      <span className="nav-stat-label">Reference</span>
                    </span>
                  </>
                )}
                {report.duration_seconds && (
                  <>
                    <span className="nav-stat-separator">•</span>
                    <span className="nav-stat-item">
                      <span className="nav-stat-value">{report.duration_seconds.toFixed(1)}s</span>
                      <span className="nav-stat-label">Time</span>
                    </span>
                  </>
                )}
              </div>
            ) : null}
          </div>
          <div className="nav-actions">
            <div className="nav-user-info">
              <span className="nav-username">{username}</span>
              <span className="nav-user-role">{userRole}</span>
            </div>
            <button 
              className="nav-button nav-button-secondary theme-toggle"
              onClick={toggleTheme}
              title={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
            >
              {theme === 'light' ? '🌙' : '☀️'}
            </button>
            <button 
              className="nav-button nav-button-secondary"
              onClick={handleLogout}
            >
              Log out
            </button>
            {!currentJob && (
              <button 
                className="nav-button nav-button-secondary"
                onClick={() => {
                  if (window.translationFormToggleToolbar) {
                    window.translationFormToggleToolbar();
                  }
                }}
                title="Toggle settings toolbar"
              >
                ⚙️ Settings
              </button>
            )}
            <button 
              className="nav-button nav-button-primary"
              onClick={currentJob ? handleReset : undefined}
            >
              Translate Document
            </button>
          </div>
        </div>
      </nav>

      <main className="App-main">
        {!currentJob ? (
          <TranslationForm
            onTranslationStart={handleTranslationStart}
            onStreamingStart={handleStreamingStart}
            userRole={userRole}
          />
        ) : streamingMode ? (
          <StreamingTranslation
            file={streamingFile}
            options={streamingOptions}
            onComplete={handleStreamingComplete}
            onReset={handleReset}
          />
        ) : (
          <TranslationStatus
            jobId={currentJob}
            status={status}
            onReset={handleReset}
            onReportUpdate={handleReportUpdate}
          />
        )}
      </main>
    </div>
  );
}

export default App;

