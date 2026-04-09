/**
 * test_python_service.test.js
 *
 * CI test suite for python.service.js — specifically guards against the
 * "env not loaded at module time" regression where PYTHON_SERVER_URL would
 * silently fall back to the Docker hostname (http://python-server:8000)
 * when running locally, causing EAI_AGAIN / ENOTFOUND errors.
 *
 * Run with:  npm test  (or jest directly)
 * CI:        included in GitHub Actions Node.js job
 */

import { jest } from '@jest/globals';

// ─── helpers ────────────────────────────────────────────────────────────────

/**
 * Re-imports python.service.js in a fresh module registry so that
 * process.env changes made BEFORE calling this function are visible
 * to the module (simulates dotenv loading before the module is required).
 */
async function freshImport() {
  // Jest module registry isolation — clear cache so the module re-evaluates
  jest.resetModules();
  return import('../../src/services/python.service.js');
}

// ─── 1. ENV RESOLUTION TESTS (the regression guard) ─────────────────────────

describe('python.service – PYTHON_SERVER_URL resolution', () => {

  afterEach(() => {
    // Clean up any env mutations between tests
    delete process.env.PYTHON_SERVER_URL;
    delete process.env.PYTHON_TIMEOUT_MS;
    jest.resetModules();
    jest.restoreAllMocks();
  });

  test('uses PYTHON_SERVER_URL from process.env when set (simulates dotenv load)', async () => {
    // Simulate dotenv.config() having already run with a local dev value
    process.env.PYTHON_SERVER_URL = 'http://localhost:8000';

    // Mock axios so no real HTTP call is made
    jest.unstable_mockModule('axios', () => ({
      default: {
        post: jest.fn().mockResolvedValue({
          data: { score: 42, tier: 'LOW', hhi: 0.1, gini: 0.2, temporal: {} },
        }),
      },
    }));

    const { analyzeWallet } = await freshImport();
    const result = await analyzeWallet('0xABC123', 'eth-mainnet');

    // Verify the mocked axios.post was called with the correct (localhost) URL
    const axiosMod = await import('axios');
    const postSpy = axiosMod.default.post;

    expect(postSpy).toHaveBeenCalledWith(
      'http://localhost:8000/analyze/0xABC123',
      { chain: 'eth-mainnet' },
      expect.objectContaining({ headers: { 'Content-Type': 'application/json' } })
    );
    expect(result.score).toBe(42);
  });

  test('falls back to http://localhost:8000 (NOT docker hostname) when env is unset', async () => {
    // Ensure env var is absent — simulates missing .env on CI with no Docker
    delete process.env.PYTHON_SERVER_URL;

    jest.unstable_mockModule('axios', () => ({
      default: {
        post: jest.fn().mockResolvedValue({
          data: { score: 10, tier: 'LOW', hhi: 0.05, gini: 0.1, temporal: {} },
        }),
      },
    }));

    const { analyzeWallet } = await freshImport();
    await analyzeWallet('0xDEF456', 'polygon-mainnet');

    const axiosMod = await import('axios');
    const postSpy = axiosMod.default.post;

    // Must NOT fall back to the Docker hostname — that causes EAI_AGAIN locally
    const calledUrl = postSpy.mock.calls[0][0];
    expect(calledUrl).not.toContain('python-server:8000');
    expect(calledUrl).toContain('localhost:8000');
  });

  test('REGRESSION: module loaded BEFORE dotenv still picks up env (lazy read)', async () => {
    // Simulate the old bug: module is imported BEFORE env is set
    jest.unstable_mockModule('axios', () => ({
      default: { post: jest.fn().mockResolvedValue({ data: { score: 55 } }) },
    }));

    // Import module first (env not yet set — old bug would freeze Docker URL here)
    const serviceModule = await freshImport();

    // Now set the env (simulates dotenv loading after module import)
    process.env.PYTHON_SERVER_URL = 'http://localhost:8000';

    // Call the function — with lazy read it should pick up the new env value
    await serviceModule.analyzeWallet('0xGHI789', 'eth-mainnet');

    const axiosMod = await import('axios');
    const calledUrl = axiosMod.default.post.mock.calls[0][0];

    // With the fix, this must be localhost — not the Docker hostname
    expect(calledUrl).toContain('localhost:8000');
    expect(calledUrl).not.toContain('python-server:8000');
  });

});

// ─── 2. SUCCESS PATH ─────────────────────────────────────────────────────────

describe('python.service – analyzeWallet success', () => {

  beforeEach(() => {
    process.env.PYTHON_SERVER_URL = 'http://localhost:8000';
    process.env.PYTHON_TIMEOUT_MS = '5000';
  });

  afterEach(() => {
    delete process.env.PYTHON_SERVER_URL;
    delete process.env.PYTHON_TIMEOUT_MS;
    jest.resetModules();
    jest.restoreAllMocks();
  });

  test('returns full risk object from Python server', async () => {
    const mockData = {
      score: 62,
      tier: 'HIGH',
      hhi: 0.644137,
      gini: 0.974293,
      temporal: {
        anomaly_score: 0.066667,
        anomalous_days: ['2026-02-09', '2026-03-09'],
        mean_daily_tx: 3.3333,
        std_daily_tx: 3.3045,
        z_threshold: 2,
      },
      tx_count: 100,
      total_volume: 1263.60948336,
    };

    jest.unstable_mockModule('axios', () => ({
      default: {
        post: jest.fn().mockResolvedValue({ data: mockData }),
      },
    }));

    const { analyzeWallet } = await freshImport();
    const result = await analyzeWallet(
      '0x1234567890123456789012345678901234567890',
      'polygon-mainnet'
    );

    expect(result.score).toBe(62);
    expect(result.tier).toBe('HIGH');
    expect(result.hhi).toBeCloseTo(0.644137, 4);
    expect(result.gini).toBeCloseTo(0.974293, 4);
    expect(result.temporal.anomaly_score).toBeCloseTo(0.066667, 4);
  });

  test('uses custom PYTHON_TIMEOUT_MS from env', async () => {
    process.env.PYTHON_TIMEOUT_MS = '10000';

    jest.unstable_mockModule('axios', () => ({
      default: {
        post: jest.fn().mockResolvedValue({ data: { score: 1 } }),
      },
    }));

    const { analyzeWallet } = await freshImport();
    await analyzeWallet('0xABC', 'eth-mainnet');

    const axiosMod = await import('axios');
    const callOptions = axiosMod.default.post.mock.calls[0][2];
    expect(callOptions.timeout).toBe(10000);
  });

});

// ─── 3. ERROR PATH ───────────────────────────────────────────────────────────

describe('python.service – analyzeWallet error handling', () => {

  beforeEach(() => {
    process.env.PYTHON_SERVER_URL = 'http://localhost:8000';
  });

  afterEach(() => {
    delete process.env.PYTHON_SERVER_URL;
    jest.resetModules();
    jest.restoreAllMocks();
  });

  test('throws with clear message on EAI_AGAIN (DNS failure = wrong hostname)', async () => {
    const dnsError = new Error('getaddrinfo EAI_AGAIN python-server');
    dnsError.code = 'EAI_AGAIN';

    jest.unstable_mockModule('axios', () => ({
      default: { post: jest.fn().mockRejectedValue(dnsError) },
    }));

    const { analyzeWallet } = await freshImport();

    await expect(analyzeWallet('0xBAD', 'eth-mainnet')).rejects.toThrow(
      'Python risk engine error: getaddrinfo EAI_AGAIN python-server'
    );
  });

  test('throws with Python error detail on 4xx/5xx response', async () => {
    const axiosError = {
      message: 'Request failed with status code 422',
      response: { data: { detail: 'Invalid wallet address format' } },
    };

    jest.unstable_mockModule('axios', () => ({
      default: { post: jest.fn().mockRejectedValue(axiosError) },
    }));

    const { analyzeWallet } = await freshImport();

    await expect(analyzeWallet('not-a-wallet', 'eth-mainnet')).rejects.toThrow(
      'Python risk engine error: Invalid wallet address format'
    );
  });

  test('throws on timeout', async () => {
    const timeoutError = new Error('timeout of 30000ms exceeded');
    timeoutError.code = 'ECONNABORTED';

    jest.unstable_mockModule('axios', () => ({
      default: { post: jest.fn().mockRejectedValue(timeoutError) },
    }));

    const { analyzeWallet } = await freshImport();

    await expect(analyzeWallet('0xABC', 'eth-mainnet')).rejects.toThrow(
      'timeout of 30000ms exceeded'
    );
  });

});