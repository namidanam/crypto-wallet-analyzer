import express from "express";
import { registerWallet, getWalletTransactions } from "../controllers/wallet.controller.js";

const router = express.Router();

// POST /api/wallet/register
router.post("/register", registerWallet);

// GET /api/wallet/transactions
router.get("/transactions", getWalletTransactions);

export default router;