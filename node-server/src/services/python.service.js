import axios from 'axios';
import { logInfo, logError } from '../utils/logger.js';

const PYTHON_SERVER_URL = process.env.PYTHON_SERVER_URL || 'http://python-server:8000';
const PYTHON_TIMEOUT_MS = parseInt(process.env.PYTHON_TIMEOUT_MS || '30000', 10);

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
  logInfo(`[python.service] Sending analyze request for ${walletAddress} on ${chain}`);

  try {
    const response = await axios.post(
      `${PYTHON_SERVER_URL}/analyze/${walletAddress}`,
      { chain },
      {
        timeout: PYTHON_TIMEOUT_MS,
        headers: { 'Content-Type': 'application/json' },
      }
    );

    logInfo(`[python.service] Risk score received for ${walletAddress}: ${response.data?.score}`);
    return response.data;
  } catch (err) {
    const status = err?.response?.status;
    const detail = err?.response?.data?.detail || err.message;
    logError(`[python.service] analyzeWallet failed for ${walletAddress}: ${detail} (status ${status})`);

    const wrapped = new Error(
      `Python risk engine error${status ? ` (status ${status})` : ''}: ${detail}`
    );
    wrapped.response = err?.response;
    throw wrapped;
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