import { useState, useEffect } from 'react';
import './App.css';
import TranslationForm from './components/TranslationForm';
import TranslationStatus from './components/TranslationStatus';
import { getTranslationStatus } from './services/api';
import logoLexDeep from './assets/logos/logo-lexdeep-transparent.png';

function App() {
  const [currentJob, setCurrentJob] = useState(null);
  const [status, setStatus] = useState(null);

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
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/c9cfb42e-68cf-4957-89f2-8cb5ca71e323',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.jsx:38',message:'New translation started',data:{newJobId:jobId,previousJobId:currentJob},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    setCurrentJob(jobId);
    setStatus({ status: 'pending', job_id: jobId });
  };

  const handleReset = () => {
    setCurrentJob(null);
    setStatus(null);
  };

  return (
    <div className="App">
      <nav className="App-nav">
        <div className="nav-container">
          <div className="nav-logo">
            <img src={logoLexDeep} alt="LexDeep" className="nav-logo-image" />
          </div>
          <div className="nav-menu">
            <a href="#" className="nav-link">Products</a>
            <a href="#" className="nav-link">Features</a>
            <a href="#" className="nav-link">Solutions</a>
            <a href="#" className="nav-link">Resources</a>
            <a href="#" className="nav-link">Pricing</a>
          </div>
          <div className="nav-actions">
            <button className="nav-button nav-button-secondary">Log in</button>
            <button className="nav-button nav-button-primary">Get Started</button>
          </div>
        </div>
      </nav>

      <header className="App-header">
        <p>Translate legal documents using controlled AI with glossary and translation memory support</p>
      </header>

      <main className="App-main">
        {!currentJob ? (
          <TranslationForm
            onTranslationStart={handleTranslationStart}
          />
        ) : (
          <TranslationStatus
            jobId={currentJob}
            status={status}
            onReset={handleReset}
          />
        )}
      </main>
    </div>
  );
}

export default App;

