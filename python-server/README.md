# Python Processing Server (FastAPI)

## Overview

This is the Python-based data processing server that handles:
- Transaction data normalization across different blockchains
- Statistical aggregate computations
- Risk scoring algorithms
- Heavy numerical processing

## Structure

```
python-server/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── config/
│   │   └── settings.py      # Configuration management
│   ├── db/
│   │   └── mongo.py         # MongoDB connection
│   ├── processors/
│   │   ├── normalize.py     # Transaction normalization (VIJNA)
│   │   ├── aggregates.py    # Statistical computations (ANMOL)
│   │   └── risk_engine.py   # Risk scoring (ANHAD)
│   ├── schemas/
│   │   ├── transaction.py   # Pydantic models
│   │   └── wallet.py
│   └── utils/
│       └── converters.py    # Unit conversion utilities
├── tests/
│   ├── test_normalize.py
│   └── test_aggregates.py
├── requirements.txt
└── Dockerfile
```

## Installation

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Development

```bash
# Run server with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest

# Run tests with coverage
pytest --cov=app tests/

# Format code
black app/
isort app/

# Type checking
mypy app/
```

## Effort Estimation (Intermediate COCOMO)

Project-level Intermediate COCOMO estimation (excluding `node_modules/`, generated artifacts, documentation, and config/lock files) is documented in `docs/ESTIMATION.md`.


## Running the Python Server

Start the server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Server will be available at `http://localhost:8000`

**Access via Browser:**
- Health Check: `http://localhost:8000/health`
- Interactive API Docs (Swagger UI): `http://localhost:8000/docs` — allows testing endpoints without curl.


## API Endpoints

### Health Check
```
GET /health
Response: { "status": "healthy", "service": "python-normalizer" }
```

This endpoint verifies that the Python processing server is running correctly.

**Access via:**
- Browser: `http://localhost:8000/health`
- curl:
```bash
curl http://localhost:8000/health
```

---

### Normalize Transactions

```
POST /normalize/{wallet}
```

Fetches raw transaction data for a given wallet from MongoDB, normalizes it into a unified schema, validates it, and stores the normalized data back into MongoDB.

**Flow:**
```
Node Server → stores raw data in MongoDB
        ↓
Python API (/normalize/{wallet})
        ↓
Fetch raw transactions from DB
        ↓
Normalize + validate
        ↓
Store in normalized_transactions collection
```

**Response:**
```json
{
  "wallet": "0x123...",
  "normalized_count": 42
}
```

**Example Usage:**

Linux (curl):
```bash
curl -X POST http://localhost:8000/normalize/0x1234567890123456789012345678901234567890 
(or)
curl -X POST http://localhost:8000/normalize/{wallet_address}

```

Windows (PowerShell):
```powershell
Invoke-RestMethod -Method POST `
  -Uri "http://localhost:8000/normalize/0x1234567890123456789012345678901234567890"
```

> **Note:** The Python server does not return normalized data to Node. It acts as a processing service that updates the database directly. Communication between Node and Python happens via MongoDB.

---

### Compute Aggregates
```
POST /aggregates
Body: {
  "transactions": [...]
}
Response: {
  "total_volume": 123.45,
  "tx_count": 50,
  "avg_value": 2.47,
  ...
}
```


---

### Calculate Risk Score
```
POST /risk-score
Body: {
  "aggregates": {...}
}
Response: {
  "risk_score": 65.5,
  "risk_level": "medium",
  "factors": {...}
}
```

---

## Example Workflow

1. Run the Node server and ensure raw transactions are stored in MongoDB.
2. Start the Python server:
```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
3. Trigger normalization:
```bash
   curl -X POST http://localhost:8000/normalize/
```
4. Check MongoDB — normalized data will appear in:
```
   wallet-sync → normalized_transactions
```

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_normalize.py

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=app --cov-report=html tests/
```

## Docker

```bash
# Build image
docker build -t crypto-wallet-python .

# Run container
docker run -p 8000:8000 crypto-wallet-python
```

## Key Responsibilities

### Anmol (Alpha 2 - The Integrator)
**Primary Owner**: `processors/normalize.py`

Normalize transactions from different blockchains into unified format:
- Handle Ethereum (Wei → ETH conversion)
- Handle Bitcoin (Satoshi → BTC conversion)
- Handle Polygon, BSC (EVM-compatible)
- Timestamp parsing and standardization
- Error handling for missing/invalid data

### Anhad (Alpha 3 - The Analyst)
**Primary Owner**: `processors/risk_engine.py`, `processors/aggregates.py`

Compute risk scores and statistical metrics:
- Transaction frequency analysis
- Value concentration patterns
- Temporal anomaly detection
- Multi-factor risk scoring
- Statistical aggregates

## Code Quality Standards

- **Type hints**: All functions must have type annotations
- **Docstrings**: Use Google-style docstrings
- **Testing**: Minimum 80% code coverage
- **Formatting**: Use `black` and `isort`
- **Linting**: Must pass `flake8` checks

## Example: Normalization

```python
from app.processors.normalize import TransactionNormalizer

normalizer = TransactionNormalizer()

# Ethereum transaction
eth_tx = {
    "tx_hash": "0x123...",
    "from_address": "0xabc...",
    "to_address": "0xdef...",
    "value": "1000000000000000000",  # 1 ETH in Wei
    "block_signed_at": "2024-01-01T00:00:00Z"
}

normalized = normalizer.normalize_ethereum_tx(eth_tx)
# Result: { "value": 1.0, "timestamp": 1704067200, ... }
```

## Performance Targets

- Normalization: 1000+ tx/minute
- Aggregates: <500ms for 500 transactions
- Risk scoring: <200ms per wallet


## Development Workspace

A `.code-workspace` file is included for seamless development:
- Automatically selects the correct interpreter:
  - Python → virtual environment (`venv`)
  - Node.js → JavaScript runtime
- Ensures consistent environment across team members

**Usage:** Open the `.code-workspace` file in VS Code instead of opening folders individually.
