import { jest } from '@jest/globals';

const mockTatum = jest.fn();
const mockGoldrush = jest.fn();
const mockBulkWrite = jest.fn();
const mockRetry = jest.fn(fn => fn());
const logInfo = jest.fn();
const logError = jest.fn();

await jest.unstable_mockModule('../../src/services/tatum.service.js', () => ({
  fetchTatumTxs: mockTatum
}));

await jest.unstable_mockModule('../../src/services/goldrush.service.js', () => ({
  fetchGoldrushTxs: mockGoldrush
}));

await jest.unstable_mockModule('../../src/models/wallet.model.js', () => ({
  default: {}
}));

await jest.unstable_mockModule('../../src/models/ledgerEntry.model.js', () => ({
  default: {
    bulkWrite: mockBulkWrite
  }
}));

await jest.unstable_mockModule('../../src/utils/retry.js', () => ({
  retryWithBackoff: mockRetry
}));

await jest.unstable_mockModule('../../src/utils/logger.js', () => ({
  logInfo,
  logError
}));

const { startHistoricalSync } = await import('../../src/services/ledger.service.js');

describe('Ledger Service', () => {

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // -----------------------------------
  // 1. EVM chain uses Goldrush
  // -----------------------------------
  it('should fetch from goldrush for EVM chain and persist', async () => {
    mockGoldrush.mockResolvedValue({
      transactions: [
        {
          txHash: 'g1',
          blockNumber: 1,
          timestamp: 1700000000000,
          from: 'A',
          to: 'B',
          value: '100',
          assetType: 'NATIVE'
        }
      ],
      nextCursor: null
    });

    mockBulkWrite.mockResolvedValue({ upsertedCount: 1 });

    const wallet = {
      address: '0x123',
      chain: 'eth-mainnet',
      syncStatus: 'PENDING',
      save: jest.fn(async () => {})
    };

    await startHistoricalSync(wallet);

    expect(mockGoldrush).toHaveBeenCalled();
    expect(mockTatum).not.toHaveBeenCalled();
    expect(mockBulkWrite).toHaveBeenCalled();
    expect(wallet.syncStatus).toBe('HISTORICAL_DONE');
    expect(wallet.save).toHaveBeenCalled();
  });

  // -----------------------------------
  // 2. Non-EVM chain uses Tatum
  // -----------------------------------
  it('should fetch from tatum for non-EVM chain and persist', async () => {
    mockTatum.mockResolvedValue({
      transactions: [
        {
          txHash: 't1',
          blockNumber: 0,
          timestamp: 1700000000000,
          from: 'X',
          to: 'Y',
          value: '50',
          assetType: 'NATIVE'
        }
      ],
      nextOffset: 50
    });

    mockBulkWrite.mockResolvedValue({ upsertedCount: 1 });

    const wallet = {
      address: '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
      chain: 'btc-mainnet',
      syncStatus: 'PENDING',
      save: jest.fn(async () => {})
    };

    await startHistoricalSync(wallet);

    expect(mockTatum).toHaveBeenCalled();
    expect(mockGoldrush).not.toHaveBeenCalled();
    expect(mockBulkWrite).toHaveBeenCalled();
    expect(wallet.syncStatus).toBe('HISTORICAL_DONE');
  });

  // -----------------------------------
  // 3. Fetch failure marks wallet FAILED
  // -----------------------------------
  it('should mark wallet FAILED when fetch fails', async () => {
    mockGoldrush.mockRejectedValue(new Error('Goldrush failed'));

    const wallet = {
      address: '0x123',
      chain: 'eth-mainnet',
      syncStatus: 'PENDING',
      save: jest.fn(async () => {})
    };

    await startHistoricalSync(wallet);

    expect(wallet.syncStatus).toBe('FAILED');
    expect(logError).toHaveBeenCalled();
    expect(mockBulkWrite).not.toHaveBeenCalled();
  });

  // -----------------------------------
  // 4. Empty result does not write
  // -----------------------------------
  it('should not write when provider returns empty list', async () => {
    mockGoldrush.mockResolvedValue({ transactions: [], nextCursor: null });

    const wallet = {
      address: '0x123',
      chain: 'eth-mainnet',
      syncStatus: 'PENDING',
      save: jest.fn(async () => {})
    };

    await startHistoricalSync(wallet);

    expect(mockBulkWrite).not.toHaveBeenCalled();
    expect(wallet.syncStatus).toBe('HISTORICAL_DONE');
  });

}); 