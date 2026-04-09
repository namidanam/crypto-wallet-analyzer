# Docker Runbook

This guide explains how to run, update, rebuild, and fully reset the Docker setup for this project.

It is written for the current architecture:
- `backend` (Node.js) on host port `4000`
- `python-server` (FastAPI) on host port `8000`
- MongoDB Atlas (cloud) via `MONGO_URI`
- Shared database name via `DB_NAME` (currently `wallet-sync`)
- `frontend` is optional and disabled by default via profile

## 1) Prerequisites

- Docker Engine installed
- Docker Compose installed (`docker compose` command)
- Internet access (required for Goldrush, Tatum, and Atlas)

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
PYTHON_SERVER_URL=http://python-server:8000
GOLDRUSH_API_KEY=...
TATUM_API_KEY=...
JWT_SECRET=...
```

Important:
- Keep `DB_NAME` consistent with your intended database name.
- Keep the DB segment in `MONGO_URI` aligned with `DB_NAME` for clarity.

## 3) Start the Stack

Clean start (recommended):

```bash
docker compose down --remove-orphans
docker compose up -d --build python-server backend
docker compose ps
```

Follow logs:

```bash
docker compose logs -f --tail=200 backend python-server
```

Health checks:

```bash
curl http://localhost:4000/health
curl http://localhost:8000/health
```

## 4) Basic API Smoke Test

```bash
curl -X POST http://localhost:4000/api/wallet/analyze \
  -H "Content-Type: application/json" \
  -d '{"address":"0x1234567890123456789012345678901234567890","chain":"polygon-mainnet","forceSync":true}'
```

Notes:
- `forceSync: true` is useful when a wallet was previously marked `FAILED`.
- The first run can take longer due to external API fetches.

## 5) Day-to-Day Development Workflow

The compose file mounts source code as volumes:
- `./node-server/src:/app/src`
- `./python-server/app:/app/app`

So source code edits do not require image rebuilds.

After code edits, restart only affected services:

```bash
docker compose restart backend
docker compose restart python-server
```

Or both:

```bash
docker compose restart backend python-server
```

## 6) Verify Live Source Sync (Bind Mounts)

To confirm your local source is mounted into containers:

```bash
docker inspect crypto-wallet-backend --format '{{json .Mounts}}'
docker inspect crypto-wallet-python --format '{{json .Mounts}}'
```

Expected mounts include:
- backend: host `./node-server/src` -> container `/app/src`
- python: host `./python-server/app` -> container `/app/app`

Quick practical verification:

1. Edit `node-server/src/app.js` health response text.
2. Restart backend:

```bash
docker compose restart backend
curl http://localhost:4000/health
```

If response text changed, the mount is working.

Repeat similarly for python:

```bash
docker compose restart python-server
curl http://localhost:8000/health
```

Important:
- File sync is instant, but app processes normally require restart to load changed code.
- Rebuild is not needed for source-only changes in mounted folders.

## 7) When to Rebuild Images

Rebuild required if you changed:
- `Dockerfile` (backend or python)
- `package.json` / `package-lock.json` (Node dependencies)
- `requirements.txt` (Python dependencies)
- base image / OS package installation instructions

Use:

```bash
docker compose up -d --build python-server backend
```

Full no-cache rebuild:

```bash
docker compose build --no-cache python-server backend
docker compose up -d python-server backend
```

## 8) Handling `.env` Changes

Container environments are fixed at container creation time.
If `.env` changes, recreate containers:

```bash
docker compose down --remove-orphans
docker compose up -d --build python-server backend
```

## 9) Stop / Shutdown

Normal shutdown:

```bash
docker compose down --remove-orphans

# Use --volumes in the end to wipe docker persistent data/caches only!
```

## 10) Delete Images and Recreate Everything

If you want a full clean rebuild from scratch:

```bash
docker compose down --remove-orphans --volumes
docker image rm crypto-wallet-analyzer-backend crypto-wallet-analyzer-python-server || true
docker compose build --no-cache python-server backend
docker compose up -d python-server backend
```

Notes:
- `--volumes` removes local Docker volumes only.
- Atlas cloud data is not deleted by Docker cleanup commands.

## 11) Optional Frontend

Frontend is profile-gated. To run it:

```bash
docker compose --profile frontend up -d --build frontend
```

To stop frontend only:

```bash
docker compose stop frontend
```

## 12) Troubleshooting

### A) `invalid interpolation format`

Use:
- `DB_NAME=${DB_NAME:-wallet-sync}` (valid)

Not:
- `DB_NAME=${DB_NAME:wallet-sync}` (invalid)

### B) `syncStatus: FAILED`

Common reasons:
- Invalid API key (`GOLDRUSH_API_KEY` / `TATUM_API_KEY`)
- provider rate limits or upstream errors

Check:

```bash
docker compose logs --tail=300 backend
```

### C) `Risk analysis failed. Please try again.`

Check both services:

```bash
docker compose logs --tail=300 backend python-server
```

Frequently caused by DB mismatch between:
- `MONGO_URI` DB path
- `DB_NAME`

### D) Data appears "cached"

Usually not HTTP cache. Verify actual database and counts:
- Confirm Atlas cluster and DB in use (`wallet-sync`)
- Check collections: `wallets`, `ledgerentries`, `normalized_transactions`, `analysisHistory`

## 13) Team Checklist

Before opening a PR that touches Docker:
- Update `.env.example` when required env vars change
- Validate `docker compose up -d --build python-server backend`
- Validate health endpoints
- Validate one end-to-end analyze request
- Confirm README / docs references stay consistent
