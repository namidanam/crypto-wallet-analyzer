import { jest } from '@jest/globals';

// In Jest ESM, `jest.mock()` does not get hoisted ahead of static imports.
// Use `unstable_mockModule` and dynamic imports instead.
const axiosGet = jest.fn();
await jest.unstable_mockModule('axios', () => ({
  default: { get: axiosGet }
}));

await jest.unstable_mockModule('../../src/utils/rateLimiter.js', () => ({
  rateLimit: jest.fn(() => Promise.resolve())
}));

const axios = (await import('axios')).default;
const { fetchTatumTxs } = await import('../../src/services/tatum.service.js');

describe('Tatum Service - fetchTatumTxs', () => {

  const OLD_ENV = process.env;

  beforeEach(() => {
    jest.clearAllMocks();
    process.env = { ...OLD_ENV, TATUM_API_KEY: 'test-api-key' };
  });

  afterAll(() => {
    process.env = OLD_ENV;
  });

  // 1. Invalid chain
  it('should throw error for unsupported chain', async () => {
    await expect(
      fetchTatumTxs('0x123', 'invalid-chain')
    ).rejects.toThrow('not supported');
  });

  // 2. Missing API key
  it('should throw error if API key is missing', async () => {
    delete process.env.TATUM_API_KEY;

    await expect(
      fetchTatumTxs('0x123', 'ethereum-mainnet')
    ).rejects.toThrow('TATUM_API_KEY is not set');
  });

  // 3. EVM success
  it('should fetch and parse EVM transactions correctly', async () => {
    axios.get.mockResolvedValue({
      data: {
        result: [
          {
            hash: 'tx1',
            blockNumber: 123,
            created: Date.now(),
            from: 'A',
            to: 'B',
            value: '100'
          }
        ]
      }
    });

    const result = await fetchTatumTxs('0x123', 'ethereum-mainnet');

    expect(result.transactions.length).toBe(1);
    expect(result.transactions[0].txHash).toBe('tx1');

    expect(axios.get).toHaveBeenCalledWith(
      expect.stringContaining('/ledger/transaction/address/'),
      expect.objectContaining({
        headers: { 'x-api-key': 'test-api-key' }
      })
    );
  });

  // 4. UTXO success
  it('should fetch and parse UTXO transactions correctly', async () => {
    axios.get.mockResolvedValue({
      data: [
        {
          txid: 'utxo1',
          blockTime: Date.now(),
          value: '50'
        }
      ]
    });

    const result = await fetchTatumTxs('addr1', 'btc-mainnet');

    expect(result.transactions.length).toBe(1);
    expect(result.transactions[0].txHash).toBe('utxo1');
  });

  // 5. API failure
  it('should throw wrapped error on API failure', async () => {
    axios.get.mockRejectedValue({
      message: 'API down',
      response: { status: 500, data: { error: 'server error' } }
    });

    await expect(
      fetchTatumTxs('0x123', 'ethereum-mainnet')
    ).rejects.toThrow('Failed to fetch transactions');
  });

  // 6. Invalid response
  it('should throw error for invalid response format', async () => {
    axios.get.mockResolvedValue({
      data: { result: "not-an-array" }
    });

    await expect(
      fetchTatumTxs('0x123', 'ethereum-mainnet')
    ).rejects.toThrow('Invalid transactions format');
  });

});
