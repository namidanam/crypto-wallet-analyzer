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
    expect(result.transactions[0].assetType).toBe('NATIVE');

    expect(axios.get).toHaveBeenCalled();
  });

  it('should extract ERC20 Transfer from log_events (value=0 tx)', async () => {
    axios.get.mockResolvedValue({
      data: {
        data: {
          items: [
            {
              tx_hash: 'tx2',
              block_number: 456,
              block_signed_at: new Date().toISOString(),
              from_address: '0x123',
              to_address: '0xTokenContract',
              value: '0',
              log_events: [
                {
                  log_offset: 7,
                  sender_contract_address: '0xTokenContract',
                  sender_contract_ticker_symbol: 'USDT',
                  sender_contract_decimals: 6,
                  decoded: {
                    name: 'Transfer',
                    params: [
                      { name: 'from', value: '0x123' },
                      { name: 'to', value: '0x456' },
                      { name: 'value', value: '1000000' }
                    ]
                  }
                }
              ]
            }
          ]
        }
      }
    });

    const result = await fetchGoldrushTxs('0x123', 'bsc-mainnet');
    expect(result.transactions.length).toBe(1);

    const tx = result.transactions[0];
    expect(tx.txHash).toBe('tx2');
    expect(tx.assetType).toBe('ERC20');
    expect(tx.nativeValue).toBe('0');
    expect(tx.value).toBe('1000000');
    expect(tx.from).toBe('0x123');
    expect(tx.to).toBe('0x456');
    expect(tx.tokenAddress).toBe('0xTokenContract');
    expect(tx.tokenSymbol).toBe('USDT');
    expect(tx.tokenDecimals).toBe(6);
    expect(tx.tokenTransfers).toEqual([
      expect.objectContaining({
        tokenAddress: '0xTokenContract',
        tokenSymbol: 'USDT',
        tokenDecimals: 6,
        from: '0x123',
        to: '0x456',
        amount: '1000000',
        logIndex: 7
      })
    ]);
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
