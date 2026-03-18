import express from 'express';
import walletRoutes from './routes/wallet.routes.js';

const app = express();

app.use(express.json());
app.use('/api/wallet', walletRoutes);

export default app;

