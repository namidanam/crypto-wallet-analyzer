import Wallet from '../models/wallet.model.js';
import LedgerEntry from '../models/ledgerEntry.model.js';
import { fetchGoldrushTxs } from './goldrush.service.js';
import { retryWithBackoff } from '../utils/retry.js';
import { logInfo, logError } from '../utils/logger.js';

async function startHistoricalSync(wallet) {

  logInfo(`Starting historical sync for ${wallet.address}`);

  let cursor = null;
  let hasMore = true;

  try {

    while (hasMore) {
      try {
        const { transactions, nextCursor } =
          await retryWithBackoff(() =>
            fetchGoldrushTxs(wallet.address, wallet.chain, cursor)
          );

        logInfo(
          `Fetched transactions: ${transactions.length} for ${wallet.address}`
        );

        if (!transactions.length) break;

        const entries = transactions.map(tx => ({
          wallet: wallet.address,
          chain: wallet.chain,
          txHash: tx.txHash,
          blockNumber: tx.blockNumber,
          timestamp: tx.timestamp,
          from: tx.from,
          to: tx.to,
          amount: tx.value,
          assetType: tx.assetType,
          source: 'goldrush'
        }));

        try {
          await LedgerEntry.insertMany(entries, { ordered: false });
        } catch (err) {
          logInfo("Duplicate transactions skipped");
        }

        cursor = nextCursor;
        hasMore = !!nextCursor;
      } catch (err) {
        logError(`Error fetching transactions: ${err.message}`);
        // After retries fail, mark as done with error
        hasMore = false;
      }
    }

    wallet.syncStatus = 'HISTORICAL_DONE';
    await wallet.save();

    logInfo(`Historical sync finished for ${wallet.address}`);

  } catch (err) {
    logError(`Historical sync failed for ${wallet.address}: ${err.message}`);
    wallet.syncStatus = 'FAILED';
    try {
      await wallet.save();
    } catch (saveErr) {
      logError(`Failed to save wallet status: ${saveErr.message}`);
    }
  }
}

export { startHistoricalSync };