import express from 'express';
import walletRoutes from './routes/wallet.routes.js';

const app = express();

app.use(express.json());

app.get('/health', (_req, res) => {
  res.status(200).json({ status: 'healthy', service: 'node-backend' });
});

app.use('/api/wallet', walletRoutes);

export default app;

