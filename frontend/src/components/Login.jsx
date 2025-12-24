import { useState } from 'react';
import './Login.css';
import logoLexDeep from '../assets/logos/logo-lexdeep-transparent.png';
import { getUserRole } from '../services/api';

function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // Simple validation - for MVP, accept any non-empty credentials
    if (!username.trim() || !password.trim()) {
      setError('Please enter both username and password');
      return;
    }

    try {
      // Get user role from backend
      const roleData = await getUserRole(username.trim());
      const userRole = roleData.role || 'user';

      // Store login state in localStorage
      localStorage.setItem('isAuthenticated', 'true');
      localStorage.setItem('username', username.trim());
      localStorage.setItem('userRole', userRole);
      
      // Call the onLogin callback
      onLogin();
    } catch (err) {
      console.error('Failed to get user role:', err);
      // Fallback to default role determination
      const usernameLower = username.trim().toLowerCase();
      let userRole = 'user';
      if (usernameLower.includes('admin') || usernameLower.startsWith('admin_')) {
        userRole = 'admin';
      }
      
      localStorage.setItem('isAuthenticated', 'true');
      localStorage.setItem('username', username.trim());
      localStorage.setItem('userRole', userRole);
      onLogin();
    }
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

