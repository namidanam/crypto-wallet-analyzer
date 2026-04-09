import Wallet      from '../models/wallet.model.js';
import LedgerEntry  from '../models/ledgerEntry.model.js';
import { startHistoricalSync } from '../services/ledger.service.js';
import { analyzeWallet }       from '../services/python.service.js';
import { logInfo, logError }   from '../utils/logger.js';

// ─────────────────────────────────────────────────────────
// POST /wallet/register
// Registers a wallet and kicks off a background historical sync.
// ─────────────────────────────────────────────────────────
export async function registerWallet(req, res) {
  try {
    const { address, chain } = req.body;

    if (!address || !chain) {
      return res.status(400).json({ message: 'Address and chain are required' });
    }

    let wallet = await Wallet.findOne({ address, chain });

    if (!wallet) {
      wallet = await Wallet.create({ address, chain, syncStatus: 'PENDING' });
    }

    // Async background job — does not block the response
    startHistoricalSync(wallet);

    return res.json({
      message:  'Wallet registered. Sync started.',
      walletId: wallet._id,
    });
  } catch (err) {
    logError(err);
    return res.status(500).json({ message: 'Internal server error' });
  }
}

// ─────────────────────────────────────────────────────────
// GET /wallet/transactions
// Returns stored ledger entries for a wallet.
// ─────────────────────────────────────────────────────────
export async function getWalletTransactions(req, res) {
  try {
    const { address, chain } = req.query;

    if (!address || !chain) {
      return res.status(400).json({ message: 'Address and chain are required' });
    }

    const wallet = await Wallet.findOne({ address, chain });
    if (!wallet) {
      return res.status(404).json({ message: 'Wallet not found' });
    }

    const transactions = await LedgerEntry
      .find({ wallet: address, chain })
      .sort({ timestamp: -1 });

    return res.json({
      walletId:     wallet._id,
      syncStatus:   wallet.syncStatus,
      transactions,
    });
  } catch (err) {
    logError(err);
    return res.status(500).json({ message: 'Internal server error' });
  }
}

// ─────────────────────────────────────────────────────────
// POST /wallet/analyze
// Full pipeline:
//   1. Ensure wallet is registered + synced
//   2. Call Python /analyze/{wallet} → risk score
//   3. Return score + tier to frontend
//
// Tatum failover is handled inside ledger.service.js / startHistoricalSync.
// By the time this endpoint is called, data is already in MongoDB from
// the GoldRush (primary) or Tatum (fallback) fetch.
// ─────────────────────────────────────────────────────────
export async function analyzeWalletRisk(req, res) {
  try {
    const { address, chain, forceSync } = req.body;

    if (!address || !chain) {
      return res.status(400).json({ message: 'Address and chain are required' });
    }

    // 1. Find or register wallet
    let wallet = await Wallet.findOne({ address, chain });

    if (!wallet) {
      wallet = await Wallet.create({ address, chain, syncStatus: 'PENDING' });
      // Trigger sync and wait — for fresh wallets we need data before scoring
      await startHistoricalSync(wallet);
      // Reload after sync
      wallet = await Wallet.findOne({ address, chain });
    }

    // If keys were fixed after a previous failure, allow an explicit re-sync.
    if (forceSync === true) {
      wallet.syncStatus = 'PENDING';
      await wallet.save();
      await startHistoricalSync(wallet);
      wallet = await Wallet.findOne({ address, chain });
    }

    // If sync failed or is still pending, return early with a useful message
    if (wallet.syncStatus === 'FAILED') {
      return res.status(502).json({
        message: 'Transaction sync failed. Check API keys and try again.',
        syncStatus: wallet.syncStatus,
      });
    }

    if (wallet.syncStatus === 'PENDING') {
      return res.status(202).json({
        message: 'Wallet sync still in progress. Retry in a few seconds.',
        syncStatus: wallet.syncStatus,
      });
    }

    // 2. Call Python risk engine
    logInfo(`[wallet.controller] Calling Python risk engine for ${address}`);
    const riskResult = await analyzeWallet(address, chain);

    // 3. Respond
    return res.json({
      wallet:      address,
      chain,
      syncStatus:  wallet.syncStatus,
      ...riskResult,          // score, tier, hhi, gini, temporal, tx_count, total_volume
    });

  } catch (err) {
    logError(`[wallet.controller] analyzeWalletRisk error: ${err.message}`);

    // Python server down / timeout
    if (err?.response?.status === 404) {
      return res.status(404).json({ message: 'No transactions found for this wallet.' });
    }

    return res.status(500).json({ message: 'Risk analysis failed. Please try again.' });
  }
}