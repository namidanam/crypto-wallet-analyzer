import { useNavigate } from 'react-router-dom';
import { GoogleLogin, CredentialResponse } from '@react-oauth/google';
import { useAuthStore } from '../store/authStore';
import axios from 'axios';
import { useState } from 'react';
import './Login.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001';

export default function Login() {
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const loginWithGoogle = useAuthStore((s) => s.loginWithGoogle);
  const navigate = useNavigate();

  const handleGoogleSuccess = async (credentialResponse: CredentialResponse) => {
    if (!credentialResponse.credential) {
      setError('Google sign-in failed. No credential returned.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      // Verify the Google token with our backend
      const { data } = await axios.post(`${API_URL}/api/auth/google`, {
        credential: credentialResponse.credential,
      });

      loginWithGoogle(data.token, data.user);
      navigate('/dashboard');
    } catch (err: any) {
      const msg = err.response?.data?.message || 'Authentication failed. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleError = () => {
    setError('Google sign-in was cancelled or failed. Please try again.');
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

        {/* Google Sign-In */}
        <div className="login-google-section">
          <p className="login-google-label">Sign in with your Google account to continue</p>

          <div className="login-google-btn-wrapper" id="vault-google-login">
            <GoogleLogin
              onSuccess={handleGoogleSuccess}
              onError={handleGoogleError}
              theme="filled_black"
              size="large"
              width="380"
              text="signin_with"
              shape="rectangular"
            />
          </div>
        </div>

        {loading && <div className="login-loading">🔄 Verifying credentials...</div>}
        {error && <div className="login-error">⚠ {error}</div>}

        <div className="login-footer">
          VAULT v1.0.0 — GOOGLE OAUTH 2.0 — UNAUTHORIZED ACCESS PROHIBITED
        </div>
      </div>
    </div>
  );
}
