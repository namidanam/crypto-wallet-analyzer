// src/index.js

import dns from 'node:dns';
import express from 'express';
import mongoose from 'mongoose';
import dotenv from 'dotenv';
import walletRoutes from './routes/wallet.routes.js';

dotenv.config();

// Helps in networks where IPv6/DNS causes TLS handshakes to reset.
// Enable with `FORCE_IPV4=true` (or `GOLDRUSH_FORCE_IPV4=true`).
if (process.env.FORCE_IPV4 === 'true' || process.env.GOLDRUSH_FORCE_IPV4 === 'true') {
  dns.setDefaultResultOrder('ipv4first');
}

const app = express();

// Middleware to read JSON body

app.use(express.json());

// Routes

app.use('/api/wallet', walletRoutes);

// MongoDB connection
const mongoUri = process.env.MONGO_URI;

if (mongoUri) {
  mongoose.connect(mongoUri)
    .then(() => console.log('MongoDB connected'))
    .catch(err => console.error('MongoDB connection error:', err));
} else {
  console.warn('MONGO_URI is not set. Skipping MongoDB connection.');
}

const PORT = process.env.PORT || 4000;

app.listen(PORT, ()=>{
    console.log('Server is running on port', PORT);
});                                                         
