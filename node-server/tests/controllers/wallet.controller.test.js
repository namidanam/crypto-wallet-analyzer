import { jest } from '@jest/globals';

const mockStartHistoricalSync = jest.fn();
const mockWalletFindOne = jest.fn();
const mockWalletCreate = jest.fn();
const mockLedgerFind = jest.fn();

await jest.unstable_mockModule('../../src/services/ledger.service.js', () => ({
  startHistoricalSync: mockStartHistoricalSync
}));

await jest.unstable_mockModule('../../src/models/wallet.model.js', () => ({
  default: {
    findOne: mockWalletFindOne,
    create: mockWalletCreate
  }
}));

await jest.unstable_mockModule('../../src/models/ledgerEntry.model.js', () => ({
  default: {
    find: mockLedgerFind
  }
}));

const { registerWallet, getWalletTransactions } = await import('../../src/controllers/wallet.controller.js');

describe('Wallet Controller', () => {

  beforeEach(() => {
    jest.clearAllMocks();
  });

  function createRes() {
    const res = {
      statusCode: 200,
      body: undefined,
      status(code) {
        this.statusCode = code;
        return this;
      },
      json(payload) {
        this.body = payload;
        return this;
      }
    };
    return res;
  }

  // -----------------------------------
  // 1. Register wallet triggers sync
  // -----------------------------------
  it('should register wallet and start sync', async () => {
    mockWalletFindOne.mockResolvedValue(null);
    mockWalletCreate.mockResolvedValue({ _id: 'w1', address: '0x123', chain: 'eth-mainnet' });

    const req = { body: { address: '0x123', chain: 'eth-mainnet' } };
    const res = createRes();

    await registerWallet(req, res);

    expect(res.statusCode).toBe(200);
    expect(res.body.walletId).toBeDefined();
    expect(mockStartHistoricalSync).toHaveBeenCalled();
  });

  // -----------------------------------
  // 2. Missing input returns 400
  // -----------------------------------
  it('should return 400 for missing address/chain', async () => {
    const req = { body: { address: '0x123' } };
    const res = createRes();

    await registerWallet(req, res);

    expect(res.statusCode).toBe(400);
  });

  // -----------------------------------
  // 3. Transactions endpoint returns data
  // -----------------------------------
  it('should return transactions for wallet', async () => {
    mockWalletFindOne.mockResolvedValue({ _id: 'w1', address: '0x123', chain: 'eth-mainnet', syncStatus: 'SYNCED' });
    mockLedgerFind.mockReturnValue({
      sort: jest.fn(() =>
        Promise.resolve([{
          txHash: 'tx1',
          assetType: 'ERC20',
          amount: '0.710803131710045577',
          amountRaw: '710803131710045577',
          tokenDecimals: 18,
          tokenTransfers: [{
            tokenDecimals: 18,
            amount: '0.710803131710045577',
            amountRaw: '710803131710045577'
          }]
        }])
      )
    });

    const req = { query: { address: '0x123', chain: 'eth-mainnet' } };
    const res = createRes();

    await getWalletTransactions(req, res);

    expect(res.statusCode).toBe(200);
    expect(res.body.transactions.length).toBe(1);
    expect(res.body.transactions[0].amount).toBe('0.710803131710045577');
    expect(res.body.transactions[0].amountRaw).toBe('710803131710045577');
    expect(res.body.transactions[0].tokenTransfers[0].amount).toBe('0.710803131710045577');
    expect(res.body.transactions[0].tokenTransfers[0].amountRaw).toBe('710803131710045577');
  });

}); 
