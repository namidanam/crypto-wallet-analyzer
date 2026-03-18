import mongoose from 'mongoose';
import dotenv from 'dotenv';
import LedgerEntry from '../models/ledgerEntry.model.js';
import Wallet from '../models/wallet.model.js';
import axios from 'axios';
import { fetchGoldrushTxs } from '../services/goldrush.service.js';
import { fetchTatumTxs } from '../services/tatum.service.js';
import { retryWithBackoff } from './retry.js';

dotenv.config();

// EVM chains - use Goldrush (Covalent)
const EVM_CHAINS = {
  'ethereum-mainnet': 'eth-mainnet',
  'eth-mainnet': 'eth-mainnet',
  'polygon-mainnet': 'matic-mainnet',
  'matic-mainnet': 'matic-mainnet',
  'bsc-mainnet': 'bsc-mainnet',
  'binance-mainnet': 'bsc-mainnet'
};

// Non-EVM chains - use Tatum
const NON_EVM_CHAINS = {
  'btc-mainnet': 'bitcoin',
  'bitcoin-mainnet': 'bitcoin',
  'doge-mainnet': 'dogecoin',
  'dogecoin-mainnet': 'dogecoin',
  'ltc-mainnet': 'litecoin',
  'litecoin-mainnet': 'litecoin'
};

const ALL_SUPPORTED_CHAINS = { ...EVM_CHAINS, ...NON_EVM_CHAINS };
const MAX_PAGES = Number.parseInt(process.env.IMPORT_MAX_PAGES || '25', 10);

/**
 * Import transactions from APIs to MongoDB
 * Uses Goldrush (Covalent) for EVM chains and Tatum for non-EVM chains
 * Usage: node src/utils/importTransactions.js <address> <chain>
 */
async function importTransactionsFromAPI(address, chain) {
  try {
    // Validate chain is supported
    if (!ALL_SUPPORTED_CHAINS[chain]) {
      const supported = Object.keys(ALL_SUPPORTED_CHAINS).join(', ');
      throw new Error(`Chain ${chain} is not supported. Supported chains: ${supported}`);
    }

    // Connect to MongoDB
    const mongoUri = process.env.MONGO_URI;
    if (!mongoUri) {
      throw new Error('MONGO_URI is not set');
    }

    await mongoose.connect(mongoUri);
    console.log('✓ Connected to MongoDB');

    // Get or create wallet
    let wallet = await Wallet.findOne({ address, chain });
    if (!wallet) {
      wallet = await Wallet.create({
        address,
        chain,
        syncStatus: 'SYNCING'
      });
      console.log(`✓ Created wallet: ${wallet._id}`);
    } else {
      console.log(`✓ Found existing wallet: ${wallet._id}`);
    }

    console.log(`\nFetching transactions for ${address} on ${chain}...`);
    let totalFetched = 0;
    let totalInserted = 0;
    let totalDuplicates = 0;
    let totalSkippedInvalid = 0;

    async function insertBatch(txs) {
      if (!txs.length) return;

      const valid = txs.filter(t =>
        typeof t?.wallet === 'string' &&
        typeof t?.chain === 'string' &&
        typeof t?.txHash === 'string' && t.txHash.length > 0 &&
        Number.isFinite(t?.blockNumber) &&
        Number.isFinite(t?.timestamp) &&
        typeof t?.assetType === 'string' &&
        typeof t?.source === 'string'
      );

      totalSkippedInvalid += (txs.length - valid.length);
      if (!valid.length) return;

      // Upsert by (wallet, chain, txHash) so re-runs don't create duplicates.
      const ops = valid.map(doc => ({
        updateOne: {
          filter: { wallet: doc.wallet, chain: doc.chain, txHash: doc.txHash },
          update: { $setOnInsert: doc },
          upsert: true
        }
      }));

      const res = await LedgerEntry.bulkWrite(ops, { ordered: false });
      const upserted = res?.upsertedCount || 0;
      totalInserted += upserted;
      totalDuplicates += (valid.length - upserted);
    }

    // Use Goldrush for EVM chains
    if (EVM_CHAINS[chain]) {
      console.log('Using Goldrush (Covalent) API for EVM chain...');
      let cursor = null;
      let pageCount = 0;

      do {
        pageCount++;
        if (pageCount > MAX_PAGES) {
          console.log(`  Reached max pages (${MAX_PAGES}). Stopping early.`);
          break;
        }
        console.log(`  Fetching page ${pageCount}...`);

        const { transactions, nextCursor } = await retryWithBackoff(() =>
          fetchGoldrushTxs(address, chain, cursor)
        );

        console.log(`  Found ${transactions.length} transactions on page ${pageCount}`);
        totalFetched += transactions.length;

        const txs = transactions.map(tx => ({
          wallet: address,
          chain: chain,
          txHash: tx.txHash ? String(tx.txHash) : '',
          blockNumber: Number.isFinite(Number(tx.blockNumber)) ? Number(tx.blockNumber) : 0,
          timestamp: Number.isFinite(Number(tx.timestamp)) ? Number(tx.timestamp) : Date.now(),
          from: tx.from,
          to: tx.to,
          amount: tx.value,
          assetType: tx.assetType || 'NATIVE',
          source: 'goldrush'
        }));

        await insertBatch(txs);
        cursor = nextCursor;

      } while (cursor);

    } 
    // Use Tatum for non-EVM chains
    else if (NON_EVM_CHAINS[chain]) {
      console.log('Using Tatum API for non-EVM chain...');
      let offset = 0;
      let pageCount = 0;
      let hasMore = true;

      while (hasMore) {
        pageCount++;
        if (pageCount > MAX_PAGES) {
          console.log(`  Reached max pages (${MAX_PAGES}). Stopping early.`);
          break;
        }
        console.log(`  Fetching page ${pageCount}...`);

        const { transactions, nextOffset } = await retryWithBackoff(() =>
          fetchTatumTxs(address, chain, offset)
        );

        console.log(`  Found ${transactions.length} transactions on page ${pageCount}`);
        totalFetched += transactions.length;

        if (!transactions.length) break;

        const txs = transactions.map(tx => ({
          wallet: address,
          chain: chain,
          txHash: tx.txHash ? String(tx.txHash) : '',
          blockNumber: Number.isFinite(Number(tx.blockNumber)) ? Number(tx.blockNumber) : 0,
          timestamp: Number.isFinite(Number(tx.timestamp)) ? Number(tx.timestamp) : Date.now(),
          from: tx.from,
          to: tx.to,
          amount: tx.value,
          assetType: tx.assetType || 'NATIVE',
          source: 'tatum'
        }));

        await insertBatch(txs);
        offset = nextOffset;
        hasMore = transactions.length === 50; // Continue if full page

      }
    }

    console.log(`\n✓ Total transactions fetched: ${totalFetched}`);
    console.log(`✓ Inserted: ${totalInserted}, duplicates skipped: ${totalDuplicates}`);
    if (totalSkippedInvalid) {
      console.log(`⚠ Skipped invalid records: ${totalSkippedInvalid}`);
    }

    if (totalFetched === 0) {
      console.log('No transactions to import');
      await mongoose.disconnect();
      return;
    }

    // Update wallet status
    wallet.syncStatus = 'SYNCED';
    await wallet.save();
    console.log(`✓ Updated wallet sync status to SYNCED`);

    // Get final count
    const finalCount = await LedgerEntry.countDocuments({ wallet: address, chain });
    console.log(`\n✓ Total transactions in database for this wallet: ${finalCount}`);

    await mongoose.disconnect();
    console.log('✓ Disconnected from MongoDB\n');

  } catch (err) {
    console.error('❌ Error during import:', err.message);
    process.exit(1);
  }
}

/**
 * Import transactions from JSON data (manual array)
 */
async function importTransactionsFromJSON(address, chain, jsonData) {
  try {
    const mongoUri = process.env.MONGO_URI;
    if (!mongoUri) {
      throw new Error('MONGO_URI is not set');
    }

    await mongoose.connect(mongoUri);
    console.log('✓ Connected to MongoDB');

    // Get or create wallet
    let wallet = await Wallet.findOne({ address, chain });
    if (!wallet) {
      wallet = await Wallet.create({
        address,
        chain,
        syncStatus: 'SYNCED'
      });
      console.log(`✓ Created wallet: ${wallet._id}`);
    }

    // Transform JSON data
    const transactions = jsonData.map(tx => ({
      wallet: address,
      chain: chain,
      txHash: tx.txHash || tx.tx_hash,
      blockNumber: tx.blockNumber || tx.block_number || tx.block_height,
      timestamp: typeof tx.timestamp === 'string' 
        ? new Date(tx.timestamp).getTime() 
        : tx.timestamp,
      from: tx.from || tx.from_address,
      to: tx.to || tx.to_address,
      amount: tx.amount || tx.value || '0',
      assetType: tx.assetType || 'NATIVE',
      source: tx.source || 'manual'
    }));

    console.log(`\nImporting ${transactions.length} transactions from JSON...`);

    try {
      const result = await LedgerEntry.insertMany(transactions, { ordered: false });
      console.log(`✓ Successfully inserted ${result.length} transactions`);
    } catch (err) {
      if (err.code === 11000) {
        console.log(`⚠ Some transactions were duplicates (skipped)`);
      } else {
        throw err;
      }
    }

    const finalCount = await LedgerEntry.countDocuments({ wallet: address, chain });
    console.log(`✓ Total transactions in database: ${finalCount}\n`);

    await mongoose.disconnect();

  } catch (err) {
    console.error('❌ Error during import:', err.message);
    process.exit(1);
  }
}

// Main execution
const args = process.argv.slice(2);

if (args.length < 2) {
  console.log(`
Usage:
  Import from API:  node src/utils/importTransactions.js <address> <chain>
  Import from JSON: node src/utils/importTransactions.js <address> <chain> <json-file>

Examples:
  node src/utils/importTransactions.js 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 eth-mainnet
  node src/utils/importTransactions.js 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 eth-mainnet ./transactions.json
  `);
  process.exit(0);
}

const address = args[0];
const chain = args[1];
const jsonFile = args[2];

if (jsonFile) {
  // Import from JSON file
  try {
    const fs = await import('fs');
    const data = fs.readFileSync(jsonFile, 'utf-8');
    const jsonData = JSON.parse(data);
    await importTransactionsFromJSON(address, chain, jsonData);
  } catch (err) {
    console.error('❌ Error reading JSON file:', err.message);
    process.exit(1);
  }
} else {
  // Import from API
  await importTransactionsFromAPI(address, chain);
}
