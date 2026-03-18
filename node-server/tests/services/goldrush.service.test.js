import { jest } from '@jest/globals';

// Mock axios
const axiosGet = jest.fn();

await jest.unstable_mockModule('axios', () => ({
  default: { get: axiosGet }
}));

// Import AFTER mocking
const axios = (await import('axios')).default;
const { fetchGoldrushTxs } = await import('../../src/services/goldrush.service.js');

describe('Goldrush Service - fetchGoldrushTxs', () => {

  const OLD_ENV = process.env;

  beforeEach(() => {
    jest.clearAllMocks();
    process.env = { ...OLD_ENV, GOLDRUSH_API_KEY: 'test-goldrush-key' };
  });

  afterAll(() => {
    process.env = OLD_ENV;
  });

  // -----------------------------------
  // 1. Success case
  // -----------------------------------
  it('should fetch and parse transactions correctly', async () => {
    axios.get.mockResolvedValue({
      data: {
        data: {
          items: [
            {
              tx_hash: 'tx1',
              block_number: 123,
              block_signed_at: new Date().toISOString(),
              from_address: 'A',
              to_address: 'B',
              value: '100'
            }
          ]
        }
      }
    });

    const result = await fetchGoldrushTxs('0x123', 'eth-mainnet');

    expect(result.transactions.length).toBe(1);
    expect(result.transactions[0].txHash).toBe('tx1');

    expect(axios.get).toHaveBeenCalled();
  });

  // -----------------------------------
  // 2. Empty response
  // -----------------------------------
  it('should handle empty transaction list', async () => {
    axios.get.mockResolvedValue({
      data: {
        data: {
          items: []
        }
      }
    });

    const result = await fetchGoldrushTxs('0x123', 'eth-mainnet');

    expect(result.transactions).toEqual([]);
  });

  // -----------------------------------
  // 3. API failure
  // -----------------------------------
  it('should throw error on API failure', async () => {
    const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
    axiosGet.mockRejectedValue({
      message: 'API error',
      response: { status: 500 }
    });

    await expect(
      fetchGoldrushTxs('0x123', 'eth-mainnet')
    ).rejects.toThrow();
    spy.mockRestore();
  });

  // -----------------------------------
  // 4. Invalid response format
  // -----------------------------------
  it('should handle missing items as empty list', async () => {
    axios.get.mockResolvedValue({
      data: { invalid: true }
    });

    const result = await fetchGoldrushTxs('0x123', 'eth-mainnet');
    expect(result.transactions).toEqual([]);
  });

  // -----------------------------------
  // 5. Pagination / cursor handling
  // -----------------------------------
  it('should return next cursor if present', async () => {
    axios.get.mockResolvedValue({
      data: {
        data: {
          items: [],
          pagination: { next_cursor: 'abc123' }
        }
      }
    });

    const result = await fetchGoldrushTxs('0x123', 'eth-mainnet');

    expect(result.nextCursor).toBe('abc123');
  });

});
