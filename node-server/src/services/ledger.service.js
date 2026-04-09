import Wallet from '../models/wallet.model.js';
import LedgerEntry from '../models/ledgerEntry.model.js';
import { fetchGoldrushTxs } from './goldrush.service.js';
import { fetchTatumTxs } from './tatum.service.js';
import { retryWithBackoff } from '../utils/retry.js';
import { logInfo, logError } from '../utils/logger.js';
import { formatUnits } from '../utils/units.js';

// EVM chains - use Goldrush (Covalent)
const EVM_CHAINS = ['ethereum-mainnet', 'eth-mainnet', 'polygon-mainnet', 'matic-mainnet', 'bsc-mainnet', 'binance-mainnet'];

// Non-EVM chains - use Tatum
const NON_EVM_CHAINS = ['btc-mainnet', 'bitcoin-mainnet', 'doge-mainnet', 'dogecoin-mainnet', 'ltc-mainnet', 'litecoin-mainnet'];

const ALL_SUPPORTED_CHAINS = [...EVM_CHAINS, ...NON_EVM_CHAINS];
const MAX_PAGES = Number.parseInt(process.env.SYNC_MAX_PAGES || '25', 10);

async function insertEntries(entries) {
  if (!entries.length) return { inserted: 0, duplicates: 0 };

  const valid = entries.filter(e =>
    typeof e?.wallet === 'string' &&
    typeof e?.chain === 'string' &&
    typeof e?.txHash === 'string' && e.txHash.length > 0 &&
    Number.isFinite(e?.blockNumber) &&
    Number.isFinite(e?.timestamp) &&
    typeof e?.assetType === 'string' &&
    typeof e?.source === 'string'
  );

  if (!valid.length) return { inserted: 0, duplicates: 0 };

  const ops = valid.map(doc => ({
    updateOne: {
      filter: { wallet: doc.wallet, chain: doc.chain, txHash: doc.txHash },
      update: { $set: doc },
      upsert: true
    }
  }));

  const res = await LedgerEntry.bulkWrite(ops, { ordered: false });
  const upserted = res?.upsertedCount || 0;
  return { inserted: upserted, duplicates: valid.length - upserted };
}

async function startHistoricalSync(wallet) {

  logInfo(`Starting historical sync for ${wallet.address}`);

  try {
    // Validate chain is supported
    if (!ALL_SUPPORTED_CHAINS.includes(wallet.chain)) {
      throw new Error(`Chain ${wallet.chain} is not supported. Supported chains: ${ALL_SUPPORTED_CHAINS.join(', ')}`);
    }

    let pageCount = 0;
    let totalFetched = 0;
    let totalInserted = 0;
    let totalDuplicates = 0;
    let hadFetchError = false;

    // Use Goldrush for EVM chains
    if (EVM_CHAINS.includes(wallet.chain)) {
      logInfo(`Fetching from Goldrush (Covalent) for EVM chain: ${wallet.chain}`);
      let cursor = null;
      let hasMore = true;

      while (hasMore) {
        try {
          pageCount++;
          if (pageCount > MAX_PAGES) {
            logInfo(`Reached max pages (${MAX_PAGES}). Stopping early.`);
            break;
          }
          const { transactions: txs, nextCursor } =
            await retryWithBackoff(() =>
              fetchGoldrushTxs(wallet.address, wallet.chain, cursor)
            );

          logInfo(
            `Fetched transactions: ${txs.length} for ${wallet.address}`
          );

          if (!txs.length) break;

          totalFetched += txs.length;

          const entries = txs
            .map(tx => ({
              ...(() => {
                const valueRaw = String(tx?.value ?? '0');
                const tokenDecimals = Number.isFinite(Number(tx?.tokenDecimals)) ? Number(tx.tokenDecimals) : null;
                const isPrimaryErc20 = tx?.assetType === 'ERC20' && tokenDecimals !== null;
                const amountRaw = isPrimaryErc20 ? valueRaw : undefined;
                const amount = isPrimaryErc20 ? formatUnits(valueRaw, tokenDecimals) : valueRaw;

                const tokenTransfers = Array.isArray(tx?.tokenTransfers)
                  ? tx.tokenTransfers.map(t => {
                    const raw = String(t?.amount ?? '0');
                    const dec = Number.isFinite(Number(t?.tokenDecimals)) ? Number(t.tokenDecimals) : null;
                    return {
                      ...t,
                      amountRaw: raw,
                      amount: dec !== null ? formatUnits(raw, dec) : raw
                    };
                  })
                  : undefined;

                return { amount, amountRaw, tokenTransfers };
              })(),
              wallet: wallet.address,
              chain: wallet.chain,
              txHash: tx.txHash ? String(tx.txHash) : '',
              blockNumber: Number.isFinite(Number(tx.blockNumber)) ? Number(tx.blockNumber) : 0,
              timestamp: Number.isFinite(Number(tx.timestamp)) ? Number(tx.timestamp) : Date.now(),
              from: tx.from,
              to: tx.to,
              nativeValue: tx.nativeValue,
              tokenAddress: tx.tokenAddress,
              tokenSymbol: tx.tokenSymbol,
              tokenDecimals: tx.tokenDecimals,
              assetType: tx.assetType || 'NATIVE',
              source: 'goldrush'
            }));

          const { inserted, duplicates } = await insertEntries(entries);
          totalInserted += inserted;
          totalDuplicates += duplicates;

          cursor = nextCursor;
          hasMore = !!nextCursor;
        } catch (err) {
          logError(`Error fetching transactions from Goldrush: ${err.message}`);
          hadFetchError = true;
          hasMore = false;
        }
      }

    } 
    // Use Tatum for non-EVM chains
    else if (NON_EVM_CHAINS.includes(wallet.chain)) {
      logInfo(`Fetching from Tatum for non-EVM chain: ${wallet.chain}`);
      let offset = 0;
      let hasMore = true;

      while (hasMore) {
        try {
          pageCount++;
          if (pageCount > MAX_PAGES) {
            logInfo(`Reached max pages (${MAX_PAGES}). Stopping early.`);
            break;
          }
          const { transactions: txs, nextOffset } =
            await retryWithBackoff(() =>
              fetchTatumTxs(wallet.address, wallet.chain, offset)
            );

          logInfo(
            `Fetched transactions: ${txs.length} for ${wallet.address}`
          );

          if (!txs.length) break;

          totalFetched += txs.length;

          const entries = txs
            .map(tx => ({
              ...(() => {
                const valueRaw = String(tx?.value ?? '0');
                const tokenDecimals = Number.isFinite(Number(tx?.tokenDecimals)) ? Number(tx.tokenDecimals) : null;
                const isPrimaryErc20 = tx?.assetType === 'ERC20' && tokenDecimals !== null;
                const amountRaw = isPrimaryErc20 ? valueRaw : undefined;
                const amount = isPrimaryErc20 ? formatUnits(valueRaw, tokenDecimals) : valueRaw;

                const tokenTransfers = Array.isArray(tx?.tokenTransfers)
                  ? tx.tokenTransfers.map(t => {
                    const raw = String(t?.amount ?? '0');
                    const dec = Number.isFinite(Number(t?.tokenDecimals)) ? Number(t.tokenDecimals) : null;
                    return {
                      ...t,
                      amountRaw: raw,
                      amount: dec !== null ? formatUnits(raw, dec) : raw
                    };
                  })
                  : undefined;

                return { amount, amountRaw, tokenTransfers };
              })(),
              wallet: wallet.address,
              chain: wallet.chain,
              txHash: tx.txHash ? String(tx.txHash) : '',
              blockNumber: Number.isFinite(Number(tx.blockNumber)) ? Number(tx.blockNumber) : 0,
              timestamp: Number.isFinite(Number(tx.timestamp)) ? Number(tx.timestamp) : Date.now(),
              from: tx.from,
              to: tx.to,
              nativeValue: tx.nativeValue,
              tokenAddress: tx.tokenAddress,
              tokenSymbol: tx.tokenSymbol,
              tokenDecimals: tx.tokenDecimals,
              assetType: tx.assetType || 'NATIVE',
              source: 'tatum'
            }));

          const { inserted, duplicates } = await insertEntries(entries);
          totalInserted += inserted;
          totalDuplicates += duplicates;

          offset = nextOffset;
          hasMore = txs.length === 50; // Continue if we got a full page
        } catch (err) {
          logError(`Error fetching transactions from Tatum: ${err.message}`);
          hadFetchError = true;
          hasMore = false;
        }
      }
    }

    logInfo(
      `Sync summary for ${wallet.address} on ${wallet.chain}: fetched=${totalFetched}, inserted=${totalInserted}, duplicates=${totalDuplicates}`
    );

    // If we couldn't fetch due to network/API errors, mark FAILED to make it obvious in UI/Compass.
    wallet.syncStatus = hadFetchError ? 'FAILED' : 'HISTORICAL_DONE';
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
