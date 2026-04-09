// src/index.js

import dns from 'node:dns';
import { pathToFileURL } from 'node:url';
import mongoose from 'mongoose';
import dotenv from 'dotenv';
import app from './app.js';

dotenv.config();

// Helps in networks where IPv6/DNS causes TLS handshakes to reset.
// Enable with `FORCE_IPV4=true` (or `GOLDRUSH_FORCE_IPV4=true`).
if (process.env.FORCE_IPV4 === 'true' || process.env.GOLDRUSH_FORCE_IPV4 === 'true') {
  dns.setDefaultResultOrder('ipv4first');
}

const isMain = (() => {
  if (!process.argv[1]) return false;
  try {
    return import.meta.url === pathToFileURL(process.argv[1]).href;
  } catch {
    return false;
  }
})();

async function start() {
  const mongoUri = process.env.MONGO_URI;
  if (mongoUri) {
    try {
      await mongoose.connect(mongoUri);
      console.log('MongoDB connected');
    } catch (err) {
      console.error('MongoDB connection error:', err);
    }
  } else {
    console.warn('MONGO_URI is not set. Skipping MongoDB connection.');
  }

  const PORT = process.env.PORT || 4000;
  app.listen(PORT, () => {
    console.log('Server is running on port', PORT);
  });
}

if (isMain && process.env.NODE_ENV !== 'test') {
  start();
}

export default app;
