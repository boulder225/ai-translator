import { useState } from 'react';
import './Login.css';
import logoLexDeep from '../assets/logos/logo-lexdeep-transparent.png';

function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');

    // Simple validation - for MVP, accept any non-empty credentials
    if (!username.trim() || !password.trim()) {
      setError('Please enter both username and password');
      return;
    }

    // Determine user role based on username
    // For MVP: check if username contains "admin" or matches admin pattern
    const usernameLower = username.trim().toLowerCase();
    let userRole = 'user'; // default role
    
    // Check if username indicates admin (contains "admin" or matches admin pattern)
    if (usernameLower.includes('admin') || usernameLower.startsWith('admin_')) {
      userRole = 'admin';
    }

    // Store login state in localStorage
    localStorage.setItem('isAuthenticated', 'true');
    localStorage.setItem('username', username.trim());
    localStorage.setItem('userRole', userRole);
    
    // Call the onLogin callback
    onLogin();
  };

  return (
    <div className="Login">
      <div className="Login-container">
        <div className="Login-header">
          <img src={logoLexDeep} alt="LexDeep" className="Login-logo" />
          <h1 className="Login-title">Welcome to LexDeep</h1>
          <p className="Login-subtitle">Legal Document Translation Platform</p>
        </div>
        
        <form className="Login-form" onSubmit={handleSubmit}>
          {error && (
            <div className="Login-error">
              {error}
            </div>
          )}
          
          <div className="Login-form-group">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your username"
              autoFocus
            />
          </div>
          
          <div className="Login-form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
            />
          </div>
          
          <button type="submit" className="Login-button">
            Log In
          </button>
        </form>
      </div>
    </div>
  );
}

export default Login;

