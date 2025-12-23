import { useState, useEffect } from 'react';
import './App.css';
import Login from './components/Login';
import TranslationForm from './components/TranslationForm';
import TranslationStatus from './components/TranslationStatus';
import { getTranslationStatus } from './services/api';
import logoLexDeep from './assets/logos/logo-lexdeep-transparent.png';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [currentJob, setCurrentJob] = useState(null);
  const [status, setStatus] = useState(null);
  const [report, setReport] = useState(null);

  // Check for existing authentication on mount
  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    const userData = localStorage.getItem('user');
    
    if (token && userData) {
      try {
        const parsedUser = JSON.parse(userData);
        setUser(parsedUser);
        setIsAuthenticated(true);
        // Update API service with token
        updateApiToken(token);
      } catch (err) {
        console.error('Failed to parse user data:', err);
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user');
      }
    }
  }, []);

  const updateApiToken = (token) => {
    // Token is handled by axios interceptors in api.js
    // No need to manually set headers here
  };

  const handleLogin = (userData, token) => {
    setUser(userData);
    setIsAuthenticated(true);
    updateApiToken(token);
  };

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user');
    setUser(null);
    setIsAuthenticated(false);
    setCurrentJob(null);
    setStatus(null);
    setReport(null);
    // Clear API token
    const api = require('./services/api').default;
    if (api && api.defaults) {
      delete api.defaults.headers.common['Authorization'];
    }
  };

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

  const handleReset = () => {
    setCurrentJob(null);
    setStatus(null);
    setReport(null);
  };

  const handleReportUpdate = (reportData) => {
    setReport(reportData);
  };

  // Show login page if not authenticated
  if (!isAuthenticated) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="App">
      <nav className="App-nav">
        <div className="nav-container">
          <div className="nav-logo">
            <img src={logoLexDeep} alt="LexDeep" className="nav-logo-image" />
          </div>
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
            ) : (
              <p className="nav-tagline">Translate legal documents using controlled AI with glossary and memory support</p>
            )}
          </div>
          <div className="nav-actions">
            <div className="nav-user-info">
              <span className="nav-username">{user?.username}</span>
              {user?.roles && user.roles.length > 0 && (
                <span className="nav-roles">{user.roles.join(', ')}</span>
              )}
            </div>
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
            user={user}
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

