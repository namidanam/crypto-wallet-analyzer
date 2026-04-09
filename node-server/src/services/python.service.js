import axios from 'axios';
import { logInfo, logError } from '../utils/logger.js';

/**
 * Returns the Python server base URL, resolved at call-time (not module load).
 * Local dev:  PYTHON_SERVER_URL=http://localhost:8000  (set in .env)
 * Docker:     PYTHON_SERVER_URL=http://python-server:8000  (set in docker-compose env)
 * Fallback:   http://localhost:8000  (safe default for local dev without .env)
 */
function getPythonServerUrl() {
  return process.env.PYTHON_SERVER_URL || 'http://localhost:8000';
}

/**
 * Calls the Python /analyze/{wallet} endpoint.
 * This triggers the full normalize → aggregate → risk_score pipeline
 * and returns the risk result to the Node.js controller.
 *
 * @param {string} walletAddress - The wallet address to analyze.
 * @param {string} chain         - The chain identifier (e.g. 'eth-mainnet').
 * @returns {Promise<{score: number, tier: string, hhi: number, gini: number, temporal: object, tx_count: number, total_volume: number}>}
 * @throws {Error} If the Python server returns a non-2xx response.
 */
async function analyzeWallet(walletAddress, chain) {
  const PYTHON_SERVER_URL = getPythonServerUrl();
  const PYTHON_TIMEOUT_MS = parseInt(process.env.PYTHON_TIMEOUT_MS || '30000', 10);
  const url = `${PYTHON_SERVER_URL}/analyze/${walletAddress}`;

  logInfo(`[python.service] Sending analyze request for ${walletAddress} on ${chain}`);
  logInfo(`[python.service] Target URL: ${url}`);

  try {
    const response = await axios.post(
      url,
      { chain },
      {
        timeout: PYTHON_TIMEOUT_MS,
        headers: { 'Content-Type': 'application/json' },
      }
    );

    logInfo(`[python.service] Risk score received for ${walletAddress}: ${response.data?.score}`);
    return response.data;
  } catch (error) {
    const message = error.response?.data?.detail || error.message;
    logError(`[python.service] analyzeWallet failed for ${walletAddress}: ${message}`);
    throw new Error(`Python risk engine error: ${message}`);
  }
}

/**
 * Calls the Python /normalize/{wallet} endpoint only (no risk scoring).
 * Used if you want to pre-normalize without triggering risk analysis.
 *
 * @param {string} walletAddress
 * @returns {Promise<{wallet: string, normalized_count: number}>}
 */
async function normalizeWallet(walletAddress) {
  const PYTHON_SERVER_URL = getPythonServerUrl();
  const PYTHON_TIMEOUT_MS = parseInt(process.env.PYTHON_TIMEOUT_MS || '30000', 10);

  logInfo(`[python.service] Sending normalize request for ${walletAddress}`);

  try {
    const response = await axios.post(
      `${PYTHON_SERVER_URL}/normalize/${walletAddress}`,
      {},
      {
        timeout: PYTHON_TIMEOUT_MS,
        headers: { 'Content-Type': 'application/json' },
      }
    );
    return response.data;
  } catch (err) {
    const status = err?.response?.status;
    const detail = err?.response?.data?.detail || err.message;
    logError(`[python.service] normalizeWallet failed for ${walletAddress}: ${detail}`);
    throw new Error(`Python normalize error${status ? ` (status ${status})` : ''}: ${detail}`);
  }
}

export { analyzeWallet, normalizeWallet };