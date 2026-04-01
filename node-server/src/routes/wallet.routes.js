import express from 'express';
import {
  registerWallet,
  getWalletTransactions,
  analyzeWalletRisk,
} from '../controllers/wallet.controller.js';

const router = express.Router();

// POST /api/wallet/register
router.post('/register', registerWallet);

// GET /api/wallet/transactions
router.get('/transactions', getWalletTransactions);

// POST /api/wallet/analyze   ← NEW (TC-17, TC-21)
// Body: { address: string, chain: string }
router.post('/analyze', analyzeWalletRisk);

export default router;