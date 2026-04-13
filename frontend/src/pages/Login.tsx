import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore, DEMO_CREDENTIALS } from '../store/authStore';
import './Login.css';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const login = useAuthStore((s) => s.login);
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim()) {
      setError('Username cannot be empty.');
      return;
    }
    if (password.length < 4) {
      setError('Password must be at least 4 characters.');
      return;
    }
    const success = login(username, password);
    if (success) {
      navigate('/dashboard');
    } else {
      setError('Authentication failed. Invalid credentials.');
    }
  };

  const fillDemo = () => {
    setUsername(DEMO_CREDENTIALS.username);
    setPassword(DEMO_CREDENTIALS.password);
    setError('');
  };

  return (
    <div className="login-root">
      <div className="login-panel">
        {/* macOS window chrome */}
        <div className="login-mac-bar">
          <div className="login-mac-dot close" />
          <div className="login-mac-dot minimize" />
          <div className="login-mac-dot maximize" />
        </div>

        {/* Logo */}
        <div className="login-logo-row">
          <div className="login-logo-icon">🔐</div>
          <div className="login-logo-text">
            VAULT<span>OS</span>
          </div>
        </div>
        <div className="login-subtitle">root@vault:~ $ sudo vault --authenticate</div>

        {/* Demo hint */}
        <button className="login-demo-btn" type="button" onClick={fillDemo} id="vault-demo-fill-btn">
          Use demo credentials
        </button>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <div className="login-field">
            <label className="login-label" htmlFor="vault-username">Username</label>
            <input
              id="vault-username"
              type="text"
              className="login-input"
              placeholder="e.g. vault"
              value={username}
              onChange={(e) => { setUsername(e.target.value); setError(''); }}
              autoComplete="off"
              spellCheck={false}
            />
          </div>

          <div className="login-field">
            <label className="login-label" htmlFor="vault-password">Vault Password</label>
            <input
              id="vault-password"
              type="password"
              className="login-input"
              placeholder="Enter vault master key"
              value={password}
              onChange={(e) => { setPassword(e.target.value); setError(''); }}
              autoComplete="new-password"
            />
          </div>

          {error && <div className="login-error">⚠ {error}</div>}

          <button type="submit" className="login-btn" id="vault-login-btn">
            ⟶ &nbsp; Authenticate &amp; Enter
          </button>
        </form>

        <div className="login-footer">
          VAULT v1.0.0 — ENCRYPTED SESSION — UNAUTHORIZED ACCESS PROHIBITED
        </div>
      </div>
    </div>
  );
}
