import express from 'express';
import cors from 'cors';
import walletRoutes from './routes/wallet.routes.js';
import authRoutes from './routes/auth.routes.js';

const app = express();

app.use(cors());
app.use(express.json());

app.get('/health', (_req, res) => {
  res.status(200).json({ status: 'healthy', service: 'node-backend' });
});

app.use('/api/auth', authRoutes);
app.use('/api/wallet', walletRoutes);

export default app;
