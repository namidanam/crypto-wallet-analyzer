import Wallet      from '../models/wallet.model.js';
import LedgerEntry  from '../models/ledgerEntry.model.js';
import Analysis     from '../models/analysis.model.js';
import { startHistoricalSync } from '../services/ledger.service.js';
import { analyzeWallet }       from '../services/python.service.js';
import { logInfo, logError }   from '../utils/logger.js';

// ─────────────────────────────────────────────────────────
// Address format validation
// ─────────────────────────────────────────────────────────
function validateAddressFormat(address, chain) {
  const addr = address.trim();

  // EVM chains: must be 0x + 40 hex chars
  if (['eth-mainnet', 'ethereum-mainnet', 'matic-mainnet', 'polygon-mainnet', 'bsc-mainnet', 'binance-mainnet'].includes(chain)) {
    if (!/^0x[0-9a-fA-F]{40}$/.test(addr)) {
      return `Invalid ${chain} address. EVM addresses must start with "0x" followed by 40 hex characters (42 total).`;
    }
    return null;
  }

  // Bitcoin: 1... (P2PKH, 25-34 chars), 3... (P2SH, 34 chars), or bc1... (Bech32, 42-62 chars)
  if (['btc-mainnet', 'bitcoin-mainnet'].includes(chain)) {
    if (/^(1|3)[a-km-zA-HJ-NP-Z1-9]{24,33}$/.test(addr)) return null;
    if (/^bc1[a-z0-9]{38,58}$/.test(addr)) return null;
    return 'Invalid Bitcoin address. Expected formats: 1... (P2PKH, 25-34 chars), 3... (P2SH, 34 chars), or bc1... (Bech32).';
  }

  // Litecoin: L/M (34 chars) or ltc1... (Bech32)
  if (['ltc-mainnet', 'litecoin-mainnet'].includes(chain)) {
    if (/^[LM][a-km-zA-HJ-NP-Z1-9]{33}$/.test(addr)) return null;
    if (/^ltc1[a-z0-9]{38,58}$/.test(addr)) return null;
    return `Invalid Litecoin address "${addr}" (${addr.length} chars). Expected formats: L... or M... (34 chars), or ltc1... (Bech32).`;
  }

  // Dogecoin: D... (34 chars) or A... (34 chars)
  if (['doge-mainnet', 'dogecoin-mainnet'].includes(chain)) {
    if (/^[DA][a-km-zA-HJ-NP-Z1-9]{33}$/.test(addr)) return null;
    return `Invalid Dogecoin address "${addr}" (${addr.length} chars). Dogecoin addresses must start with "D" or "A" and be 34 characters.`;
  }

  return null; // Unknown chain — skip validation
}

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
// ─────────────────────────────────────────────────────────
export async function analyzeWalletRisk(req, res) {
  try {
    const { address, chain, forceSync } = req.body;

    if (!address || !chain) {
      return res.status(400).json({ message: 'Address and chain are required' });
    }

    // Basic address format validation before making API calls
    const addrValidationError = validateAddressFormat(address, chain);
    if (addrValidationError) {
      return res.status(400).json({ message: addrValidationError });
    }

    // 1. Find or register wallet
    let wallet = await Wallet.findOne({ address, chain });

    if (!wallet) {
      wallet = await Wallet.create({ address, chain, syncStatus: 'PENDING' });
      // Trigger sync and wait
      await startHistoricalSync(wallet);
      // Reload after sync
      wallet = await Wallet.findOne({ address, chain });
    }

    if (forceSync === true) {
      wallet.syncStatus = 'PENDING';
      await wallet.save();
      await startHistoricalSync(wallet);
      wallet = await Wallet.findOne({ address, chain });
    }

    if (wallet.syncStatus === 'FAILED') {
      return res.status(502).json({
        message: `No transactions could be fetched for this address on ${chain}. Please verify the wallet address format matches the selected chain.`,
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
      ...riskResult,
    });

  } catch (err) {
    logError(`[wallet.controller] analyzeWalletRisk error: ${err.message}`);

    const msg = err.message || '';

    // Python returned 404 — wallet has no transactions in the DB
    if (err?.response?.status === 404 || msg.includes('No transactions found')) {
      return res.status(404).json({
        message: 'No transactions found for this wallet on the selected chain. Ensure the address format matches the chain.',
      });
    }

    // Python returned 422 — all transactions failed validation
    if (err?.response?.status === 422 || msg.includes('failed validation')) {
      return res.status(422).json({
        message: 'Transaction data could not be processed. Try a different wallet.',
      });
    }

    return res.status(500).json({ message: 'Risk analysis failed. Please try again.' });
  }
}

// ─────────────────────────────────────────────────────────
// GET /wallet/analyses
// Returns all completed scan results from analysisHistory.
// ─────────────────────────────────────────────────────────
export async function getAllAnalyses(req, res) {
  try {
    const list = await Analysis.find().sort({ updatedAt: -1 }).limit(50);
    return res.json(list);
  } catch (err) {
    logError(`[wallet.controller] getAllAnalyses error: ${err.message}`);
    return res.status(500).json({ message: 'Failed to fetch scan history.' });
  }
}