# Docker Runbook

This guide explains how to run, update, rebuild, and fully reset the Docker setup for this project.

It is written for the current architecture:
- `python-server` (FastAPI) on host port `8001`
- `backend` (Node.js) on host port `5001`
- `frontend` (React + Vite → nginx) on host port `3001`
- MongoDB Atlas (cloud) via `MONGO_URI` — **required**
- Shared database name via `DB_NAME` (currently `wallet-sync`)

## Service Dependency Chain

```
python-server (healthy)
  └── backend (healthy)
        └── frontend
```

Services start in order: **python-server → backend → frontend**.

## 1) Prerequisites

- Docker Engine installed
- Docker Compose installed (`docker compose` command)
- Internet access (required for GoldRush, Tatum, and MongoDB Atlas)

## 2) First-Time Setup

From project root:

```bash
cp .env.example .env
```

Edit `.env` and set at least:

```env
PORT=5000
MONGO_URI="mongodb+srv://<user>:<password>@<cluster>/<db-name>"
DB_NAME=wallet-sync
GOLDRUSH_API_KEY=...
TATUM_API_KEY=...
JWT_SECRET=...
```

Important:
- `MONGO_URI` is **required**. The stack will refuse to start without it.
- Keep `DB_NAME` consistent with your intended database name.
- Keep the DB segment in `MONGO_URI` aligned with `DB_NAME` for clarity.

## 3) Start the Stack

Start all three services (recommended):

```bash
docker compose down --remove-orphans
docker compose up -d --build
docker compose ps
```

Follow logs:

```bash
docker compose logs -f --tail=200
```

Health checks:

```bash
curl http://localhost:5001/health    # backend
curl http://localhost:8001/health    # python-server
curl http://localhost:3001           # frontend (should return HTML)
```

## 4) Testing with Sample Wallet Addresses

### Test Addresses by Chain

#### Ethereum (`eth-mainnet`)

| Address | Identity | Notes |
|---|---|---|
| `0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045` | Vitalik Buterin | Very active, diverse transactions |
| `0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8` | Binance Cold Wallet | Whale — massive volumes |
| `0x742d35Cc6634C0532925a3b844Bc9e7595f2bD1e` | Bitfinex | Exchange hot wallet |
| `0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B` | Vitalik (old) | Historical activity |

#### Polygon (`matic-mainnet`)

| Address | Identity | Notes |
|---|---|---|
| `0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045` | Vitalik Buterin | Cross-chain presence |
| `0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270` | WMATIC Contract | Token contract interactions |

#### BSC / BNB Chain (`bsc-mainnet`)

| Address | Identity | Notes |
|---|---|---|
| `0xF977814e90dA44bFA03b6295A0616a897441aceC` | Binance Hot Wallet | High-frequency trading |
| `0x8894E0a0c962CB723c1ef8a1Dc23e1728eF8517b` | PancakeSwap Deployer | DeFi interactions |

#### Bitcoin (`btc-mainnet`) — via Tatum

| Address | Identity | Notes |
|---|---|---|
| `1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa` | Satoshi Nakamoto (Genesis) | The very first Bitcoin address |
| `bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh` | Binance Cold Wallet | High-value BTC holder |
| `3FZbgi29cpjq2GjdwV8eyHuJJnkLtktZc5` | Bitfinex Cold Wallet | Exchange cold storage |

#### Dogecoin (`doge-mainnet`) — via Tatum

| Address | Identity | Notes |
|---|---|---|
| `DH5yaieqoZN36fDVciNyRueRGvGLR3mr7L` | Dogecoin Foundation | Large DOGE holder |
| `D8vFz4p1L37jdg47HXKtSujChhP9f3GLTp` | Known whale | High transaction volume |

#### Litecoin (`ltc-mainnet`) — via Tatum

| Address | Identity | Notes |
|---|---|---|
| `LcHKx4Vy4Tio27z5VNVbpgTDAmerXbH5gH` | Litecoin Foundation | Well-known LTC address |
| `MQd1xEMmqRPNRoKLFPbFT3bTaKPxjB6tkH` | Known LTC whale | Multi-sig address |



### Smoke Test Commands

**Ethereum:**

```bash
curl -X POST http://localhost:5001/api/wallet/analyze \
  -H "Content-Type: application/json" \
  -d '{"address":"0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045","chain":"eth-mainnet"}'
```

**Polygon:**

```bash
curl -X POST http://localhost:5001/api/wallet/analyze \
  -H "Content-Type: application/json" \
  -d '{"address":"0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045","chain":"matic-mainnet"}'
```

**BSC:**

```bash
curl -X POST http://localhost:5001/api/wallet/analyze \
  -H "Content-Type: application/json" \
  -d '{"address":"0xF977814e90dA44bFA03b6295A0616a897441aceC","chain":"bsc-mainnet"}'
```

**Bitcoin:**

```bash
curl -X POST http://localhost:5001/api/wallet/analyze \
  -H "Content-Type: application/json" \
  -d '{"address":"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa","chain":"btc-mainnet"}'
```

**Dogecoin:**

```bash
curl -X POST http://localhost:5001/api/wallet/analyze \
  -H "Content-Type: application/json" \
  -d '{"address":"DH5yaieqoZN36fDVciNyRueRGvGLR3mr7L","chain":"doge-mainnet"}'
```

**Litecoin:**

```bash
curl -X POST http://localhost:5001/api/wallet/analyze \
  -H "Content-Type: application/json" \
  -d '{"address":"LcHKx4Vy4Tio27z5VNVbpgTDAmerXbH5gH","chain":"ltc-mainnet"}'
```

**Force re-sync (useful if a previous scan failed):**

```bash
curl -X POST http://localhost:5001/api/wallet/analyze \
  -H "Content-Type: application/json" \
  -d '{"address":"0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045","chain":"eth-mainnet","forceSync":true}'
```

Notes:
- `forceSync: true` is useful when a wallet was previously marked `FAILED`.
- The first run can take longer due to external API fetches (2–15 seconds).
- Subsequent runs use cached data and are much faster (<500ms).

## 5) Day-to-Day Development Workflow

The compose file mounts source code as volumes for the **backend** and **python-server**:
- `./backend/src:/app/src`
- `./python-server/app:/app/app`

So source code edits for these two services do not require image rebuilds — just restart:

```bash
docker compose restart backend
docker compose restart python-server
```

Or both:

```bash
docker compose restart backend python-server
```

**Frontend** does **not** use volume mounts (it's a multi-stage nginx build). Any frontend code change requires a rebuild:

```bash
docker compose up -d --build frontend
```

**Tip:** For rapid frontend development with hot-reload, run the Vite dev server locally:

```bash
cd frontend
npm install
npm run dev
# Vite serves at http://localhost:5173 with HMR
```

## 6) Verify Live Source Sync (Bind Mounts)

To confirm your local source is mounted into containers:

```bash
docker inspect crypto-wallet-backend --format '{{json .Mounts}}'
docker inspect crypto-wallet-python --format '{{json .Mounts}}'
```

Expected mounts include:
- backend: host `./backend/src` -> container `/app/src`
- python: host `./python-server/app` -> container `/app/app`

Quick practical verification:

1. Edit `backend/src/app.js` health response text.
2. Restart backend:

```bash
docker compose restart backend
curl http://localhost:5001/health
```

If response text changed, the mount is working.

Repeat similarly for python:

```bash
docker compose restart python-server
curl http://localhost:8001/health
```

Important:
- File sync is instant, but app processes normally require restart to load changed code.
- Rebuild is not needed for source-only changes in mounted folders.

## 7) When to Rebuild Images

Rebuild required if you changed:
- `Dockerfile` (backend, python, or frontend)
- `package.json` / `package-lock.json` (Node dependencies)
- `requirements.txt` (Python dependencies)
- `frontend/nginx.conf`
- Any source file in `frontend/src/` (frontend has no volume mount)
- `VITE_API_URL` or any `VITE_*` environment variable (baked at build time)

Use:

```bash
docker compose up -d --build
```

Full no-cache rebuild:

```bash
docker compose build --no-cache
docker compose up -d
```

## 8) Handling `.env` Changes

Container environments are fixed at **container creation time**.
A `docker compose restart` reuses the same container with the **old** env.
You must **recreate** (not just restart) to pick up `.env` changes.

### Recreate all services

```bash
docker compose down --remove-orphans
docker compose up -d
```

No `--build` needed unless you also changed code/Dockerfiles.

### Recreate a single service

```bash
docker compose up -d --force-recreate backend
docker compose up -d --force-recreate python-server
```

### Frontend `VITE_*` env change

`VITE_*` variables are baked at **build time**, not at container creation. You must **rebuild**:

```bash
docker compose up -d --build --force-recreate frontend
```

### Quick Reference Table

| Scenario | Command |
|---|---|
| Root `.env` changed | `docker compose down --remove-orphans && docker compose up -d` |
| `.env` changed for one service | `docker compose up -d --force-recreate <service>` |
| Backend code changed | `docker compose restart backend` |
| Python code changed | `docker compose restart python-server` |
| Frontend code changed | `docker compose up -d --build frontend` |
| `VITE_API_URL` changed | `docker compose up -d --build --force-recreate frontend` |
| Dockerfile changed | `docker compose up -d --build` |
| `package.json` / `requirements.txt` changed | `docker compose up -d --build` |
| Restart all services | `docker compose restart` |

> **Key distinction:** `restart` = reuse same container (fast, keeps env). `--force-recreate` = destroy and recreate container (picks up new env). `--build` = rebuild image (picks up code/dependency changes).

## 9) Stop / Shutdown

Normal shutdown:

```bash
docker compose down --remove-orphans
```

## 10) Delete Images and Recreate Everything

If you want a full clean rebuild from scratch:

```bash
docker compose down --remove-orphans
docker image rm crypto-wallet-analyzer-backend crypto-wallet-analyzer-python-server crypto-wallet-analyzer-frontend || true
docker compose build --no-cache
docker compose up -d
```

Notes:
- Atlas cloud data is not affected by Docker cleanup commands.

## 11) Frontend (Docker)

The frontend is an **always-on** service that starts automatically with the full stack.

### Architecture

The frontend Dockerfile is a **multi-stage build**:

1. **Builder stage** (`node:18-alpine`): installs npm dependencies and runs `tsc && vite build`.
2. **Production stage** (`nginx:alpine`): copies the built `dist/` folder into nginx and serves it on port **3000** via `nginx.conf`.

Key files:
- `frontend/Dockerfile` — multi-stage build definition
- `frontend/nginx.conf` — nginx config (SPA fallback, port 3000, caching, security headers)

### Why no volume mount for frontend?

Unlike the backend and python-server, the frontend's running container is **nginx** — it only serves pre-built static files from `/usr/share/nginx/html`. Mounting `./frontend/src:/app/src` would go into the nginx container where nothing reads it. Any frontend code change requires an image rebuild:

```bash
docker compose up -d --build frontend
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `http://localhost:5001` | Backend API base URL used by the React app |

> **Note:** `VITE_*` variables are baked into the app at **build time** (Vite replaces them during `vite build`).
> Changing `VITE_API_URL` requires a full image rebuild, not just a restart.

## 12) Troubleshooting

### A) `invalid interpolation format`

Use:
- `DB_NAME=${DB_NAME:-wallet-sync}` (valid)

Not:
- `DB_NAME=${DB_NAME:wallet-sync}` (invalid)

### B) `MONGO_URI: Set MONGO_URI in .env`

The stack requires `MONGO_URI` to be set. Edit your `.env` file and provide a valid MongoDB Atlas connection string.

### C) `syncStatus: FAILED`

Common reasons:
- Invalid API key (`GOLDRUSH_API_KEY` / `TATUM_API_KEY`)
- Provider rate limits or upstream errors

Check:

```bash
docker compose logs --tail=300 backend
```

### D) `Risk analysis failed. Please try again.`

Check both services:

```bash
docker compose logs --tail=300 backend python-server
```

Frequently caused by DB mismatch between:
- `MONGO_URI` DB path
- `DB_NAME`

### E) Data appears "cached"

Usually not HTTP cache. Verify actual database and counts:
- Confirm Atlas cluster and DB in use (`wallet-sync`)
- Check collections: `wallets`, `ledgerentries`, `normalized_transactions`, `analysisHistory`

### F) Frontend build fails: `nginx.conf not found`

Ensure `frontend/nginx.conf` exists. It is required by the Dockerfile's
`COPY nginx.conf /etc/nginx/conf.d/default.conf` instruction.

### G) `http://localhost:3001` returns 502 or connection refused

1. Check the container is running: `docker compose ps`
2. Check logs: `docker compose logs --tail=100 frontend`
3. Ensure nginx listens on port 3000 (check `frontend/nginx.conf`).

### H) API calls fail from the browser (CORS / network errors)

- Verify `VITE_API_URL` was set correctly at build time.
- The backend must be accessible from the **browser** (not from the container). The backend host port is `5001`.
- Rebuild the frontend image after changing `VITE_API_URL`.

## 13) Team Checklist

Before opening a PR that touches Docker:
- Update `.env.example` when required env vars change
- Validate `docker compose up -d --build`
- Validate all health endpoints (`/health` on ports 5001, 8001; port 3001 for frontend)
- Validate one end-to-end analyze request
- Confirm README / docs references stay consistent
