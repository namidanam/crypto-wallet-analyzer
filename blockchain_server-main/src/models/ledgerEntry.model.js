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

  assetType: {
    type: String,
    enum: ['NATIVE', 'ERC20'],
    required: true
  },

  source: {
    type: String,
    enum: ['goldrush', 'tatum', 'covalent'],
    required: true
  }
}, { strict: true });

LedgerEntrySchema.index(
  { wallet: 1, txHash: 1 },
  { unique: true }
);

export default model('LedgerEntry', LedgerEntrySchema);