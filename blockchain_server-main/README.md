## Node Wallet Sync Server

This is a Node.js/Express server that registers wallets and synchronizes their on-chain transaction history into MongoDB using the Goldrush API.

### Tech Stack

- **Runtime**: Node.js (ES modules)
- **Framework**: Express
- **Database**: MongoDB via Mongoose
- **HTTP Client**: Axios
- **Dev**: Nodemon

### Project Structure (key parts)

- `src/index.js` – Express app bootstrap, dotenv loading, MongoDB connection.
- `src/routes/wallet.routes.js` – Wallet-related HTTP routes.
- `src/controllers/wallet.controller.js` – Wallet controller (`/api/wallet/register`).
- `src/services/ledger.service.js` – Historical sync orchestration.
- `src/services/goldrush.service.js` – Goldrush API client.
- `src/models/wallet.model.js` / `src/models/ledgerEntry.model.js` – Mongoose models.
- `src/utils/logger.js` – Simple logging helpers.
- `src/utils/retry.js` – Retry with exponential backoff.
- `src/utils/rateLimiter.js` – Basic in-process rate limiting.

### Prerequisites

- Node.js 18+ (recommended)
- MongoDB instance (local or remote)
- Goldrush API key

### Setup

1. **Install dependencies**

```bash
cd node-server
npm install
```

2. **Create a `.env` file** in `node-server`:

```bash
MONGO_URI=mongodb://localhost:27017/wallet-sync
GOLDRUSH_API_KEY=your_goldrush_api_key_here
PORT=4000
```

3. **Start the dev server**

```bash
npm run dev
```

You should see logs similar to:

```text
Server is running on port 4000
MongoDB connected
```

### Wallet registration & historical sync demo

With the server running:

```bash
curl -X POST http://localhost:4000/api/wallet/register \
  -H "Content-Type: application/json" \
  -d '{"address":"0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045","chain":"ethereum"}'
```

Expected JSON response:

```json
{"message":"Wallet registered. Sync started.","walletId":"<mongo_id>"}
```

On the **server terminal** you’ll see logs like:

```text
[INFO] ... Starting historical sync for 0xd8...
[INFO] ... Fetched transactions: 100 for 0xd8...
[INFO] ... Fetched transactions: 40 for 0xd8...
[INFO] ... Historical sync finished for 0xd8...
```

If Goldrush or network fails, errors are logged via `logError` and the server keeps running.

### Environment variables

- **`MONGO_URI`** – MongoDB connection string (required for DB writes).
- **`GOLDRUSH_API_KEY`** – Goldrush API bearer token (required for transaction sync).
- **`PORT`** – HTTP port (default: `4000`).

### Running in production

Use:

```bash
npm start
```

Make sure your `.env` (or equivalent environment variables) is configured in your production environment.


### Add all the transactions of any wallet address to MongoDB database:

Use: 

```bash
# 1. Navigate to the project directory
cd /home/raghav-maheshwari/Raghav/Software_Engg_Project/Server/node-server

# 2. Import transactions from Covalent API to MongoDB
# Replace the address and chain as needed

#Ethereum:
node src/utils/importTransactions.js 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 eth-mainnet
# Bitcoin: genesis block
node src/utils/importTransactions.js 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa btc-mainnet
# Degecoin:
node src/utils/importTransactions.js DH5yaieqoZN36fDVciNyRueRGvGLR3mr7L doge-mainnet
#Litecoin:
node src/utils/importTransactions.js LZHVJH5YH6m3zvY4xXHzkwmo7aXstixSeK ltc-mainnet

# 3. For other wallet addresses, just change the address and chain:
node src/utils/importTransactions.js <YOUR_ADDRESS> <CHAIN>


# Import for Vitalik's wallet on Ethereum
node src/utils/importTransactions.js 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 eth-mainnet

# Import for a Polygon address
node src/utils/importTransactions.js 0x1234567890123456789012345678901234567890 polygon-mainnet
