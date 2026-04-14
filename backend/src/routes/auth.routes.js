import { Router } from 'express';
import { OAuth2Client } from 'google-auth-library';
import jwt from 'jsonwebtoken';
import { logInfo, logError } from '../utils/logger.js';

const router = Router();

const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID;
const JWT_SECRET = process.env.JWT_SECRET || 'dev-secret-change-me';

/**
 * POST /api/auth/google
 * Verifies the Google ID token and returns a session JWT.
 */
router.post('/google', async (req, res) => {
  try {
    const { credential } = req.body;
    if (!credential) {
      return res.status(400).json({ message: 'Google credential is required.' });
    }

    if (!GOOGLE_CLIENT_ID) {
      logError('[auth] GOOGLE_CLIENT_ID is not configured on the server.');
      return res.status(500).json({ message: 'Google OAuth is not configured on this server.' });
    }

    // Verify the Google ID token
    const client = new OAuth2Client(GOOGLE_CLIENT_ID);
    const ticket = await client.verifyIdToken({
      idToken: credential,
      audience: GOOGLE_CLIENT_ID,
    });

    const payload = ticket.getPayload();
    if (!payload) {
      return res.status(401).json({ message: 'Invalid Google token.' });
    }

    const user = {
      googleId: payload.sub,
      email: payload.email,
      name: payload.name,
      picture: payload.picture,
    };

    logInfo(`[auth] Google login successful for ${user.email}`);

    // Issue a session JWT (valid for 24 hours)
    const token = jwt.sign(user, JWT_SECRET, { expiresIn: '24h' });

    return res.json({ token, user });
  } catch (err) {
    logError(`[auth] Google token verification failed: ${err.message}`);
    return res.status(401).json({ message: 'Google authentication failed. Please try again.' });
  }
});

/**
 * GET /api/auth/me
 * Returns the current user from the JWT.
 */
router.get('/me', (req, res) => {
  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith('Bearer ')) {
    return res.status(401).json({ message: 'Not authenticated.' });
  }

  try {
    const token = authHeader.slice(7);
    const user = jwt.verify(token, JWT_SECRET);
    return res.json({ user });
  } catch {
    return res.status(401).json({ message: 'Token expired or invalid.' });
  }
});

export default router;
