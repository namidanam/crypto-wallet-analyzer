// src/models/wallet.model.js
import { Schema, model } from 'mongoose';

const WalletSchema = new Schema({
  address: {
    type: String,
    required: true,
    index: true
  },
  chain: {
    type: String,
    required: true
  },
  syncStatus: {
    type: String,
    enum: ['PENDING', 'SYNCING', 'SYNCED', 'HISTORICAL_DONE', 'FAILED'],
    default: 'PENDING'
  },
  lastGoldrushBlock: {
    type: Number,
    default: null
  },
  createdAt: {
    type: Date,
    default: Date.now
  }
});

WalletSchema.index({ address: 1, chain: 1 }, { unique: true });

export default model('Wallet', WalletSchema);
