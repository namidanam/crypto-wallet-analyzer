import mongoose from 'mongoose';
import dotenv from 'dotenv';
import LedgerEntry from '../models/ledgerEntry.model.js';
import Wallet from '../models/wallet.model.js';
import axios from 'axios';

dotenv.config();

/**
 * Import transactions from Covalent API to MongoDB
 * Usage: node --loader ts-node/esm src/utils/importTransactions.js <address> <chain>
 */
async function importTransactionsFromAPI(address, chain) {
  try {
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

    // Fetch transactions from Covalent API
    const apiKey = process.env.GOLDRUSH_API_KEY;
    if (!apiKey) {
      throw new Error('GOLDRUSH_API_KEY is not set');
    }

    console.log(`\nFetching transactions for ${address} on ${chain}...`);
    let allTransactions = [];
    let cursor = null;
    let pageCount = 0;

    do {
      pageCount++;
      const params = { key: apiKey };
      if (cursor) params.cursor = cursor;

      console.log(`  Fetching page ${pageCount}...`);

      const response = await axios.get(
        `https://api.covalenthq.com/v1/${chain}/address/${address}/transactions_v2/`,
        {
          params,
          timeout: 30000
        }
      );

      const data = response.data?.data ?? response.data;
      const items = data?.items ?? [];

      if (!Array.isArray(items)) {
        throw new Error('Invalid response format from API');
      }

      console.log(`  Found ${items.length} transactions on page ${pageCount}`);

      // Transform transactions to match LedgerEntry schema
      const transactions = items.map(tx => ({
        wallet: address,
        chain: chain,
        txHash: tx.tx_hash,
        blockNumber: tx.block_height,
        timestamp: new Date(tx.block_signed_at).getTime(),
        from: tx.from_address,
        to: tx.to_address,
        amount: tx.value || '0',
        assetType: 'NATIVE',
        source: 'covalent'
      }));

      console.log(`  Sample transaction: ${JSON.stringify(transactions[0])}`);
      allTransactions = allTransactions.concat(transactions);
      cursor = data?.pagination?.cursor;

    } while (cursor);

    console.log(`\n✓ Total transactions fetched: ${allTransactions.length}`);

    if (allTransactions.length === 0) {
      console.log('No transactions to import');
      await mongoose.disconnect();
      return;
    }

    // Insert into MongoDB with duplicate handling
    console.log(`\nInserting ${allTransactions.length} transactions into MongoDB...`);

    let insertedCount = 0;
    let duplicateCount = 0;

    try {
      const result = await LedgerEntry.insertMany(allTransactions, { ordered: false });
      insertedCount = result.length;
      console.log(`✓ Successfully inserted ${insertedCount} transactions`);
      console.log(`  Result length: ${result.length}, IDs: ${result.slice(0, 2).map(r => r._id)}`);
    } catch (err) {
      console.error(`Insert error code: ${err.code}`);
      console.error(`Insert error message: ${err.message}`);
      
      if (err.code === 11000 || err.writeErrors) {
        // Duplicate key error - some transactions already exist
        insertedCount = err.insertedCount || 0;
        duplicateCount = allTransactions.length - insertedCount;
        console.log(`⚠ Skipped ${duplicateCount} duplicate transactions`);
        console.log(`✓ Inserted ${insertedCount} new transactions`);
      } else {
        throw err;
      }
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
