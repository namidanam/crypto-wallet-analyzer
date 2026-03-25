// src/models/ledgerEntry.model.js
import { Schema, model } from 'mongoose';

const LedgerEntrySchema = new Schema({
  wallet: { type: String, required: true, index: true },
  chain: { type: String, required: true },

  txHash: { type: String, required: true },
  blockNumber: { type: Number, required: true },
  timestamp: { type: Number, required: true },

  from: String,
  to: String,
  amount: String,
  amountRaw: String,
  nativeValue: String,

  // For simple single-token transfers, these mirror the "primary" token transfer.
  tokenAddress: String,
  tokenSymbol: String,
  tokenDecimals: Number,

  // For contract interactions, capture all ERC20 Transfer events involving the wallet.
  tokenTransfers: [{
    tokenAddress: String,
    tokenSymbol: String,
    tokenDecimals: Number,
    from: String,
    to: String,
    amount: String,
    amountRaw: String,
    logIndex: Number
  }],

  assetType: {
    type: String,
    enum: ['NATIVE', 'ERC20'],
    required: true
  },

  source: {
    type: String,
    enum: ['goldrush', 'tatum', 'covalent', 'manual'],
    required: true
  }
}, { strict: true });

LedgerEntrySchema.index(
  { wallet: 1, chain: 1, txHash: 1 },
  { unique: true }
);

export default model('LedgerEntry', LedgerEntrySchema);
