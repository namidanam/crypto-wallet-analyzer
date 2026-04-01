from fastapi import FastAPI, HTTPException
from app.db.mongo import (
    get_wallet_transactions,
    insert_normalized_transactions,
    is_wallet_normalized,
    save_analysis_result,
)
from app.processors.normalize   import normalize_transactions
from app.processors.aggregates  import compute_aggregates
from app.processors.risk_engine import compute_risk_score
from app.schemas.transaction    import NormalizedTransaction

app = FastAPI()


@app.get("/health")
def get_health():
    return {"status": "healthy", "service": "python-normalizer"}


@app.post("/normalize/{wallet}")
def normalize_wallet(wallet: str):
    """
    Normalizes raw ledger transactions for a wallet and stores them.
    Called by Node.js python.service.js after fetchGoldrushTxs/fetchTatumTxs.
    """
    if is_wallet_normalized(wallet):
        return {"message": "Already normalized"}

    raw_txns = get_wallet_transactions(wallet)

    if not raw_txns:
        return {"message": "No transactions found"}

    # 1. Normalize
    normalized = normalize_transactions(raw_txns, wallet)

    # 2. Validate with Pydantic
    validated = []
    for tx in normalized:
        try:
            validated_tx = NormalizedTransaction(**tx).model_dump()
            validated.append(validated_tx)
        except Exception as e:
            print("Validation error:", e)

    # 3. Store
    insert_normalized_transactions(validated)

    return {
        "wallet":           wallet,
        "normalized_count": len(validated),
    }


@app.post("/analyze/{wallet}")
def analyze_wallet(wallet: str):
    """
    Full pipeline: normalize → aggregate → risk score → store.
    Returns the risk result to Node.js (python.service.js → wallet.controller.js).

    Response shape:
        {
          "wallet":       str,
          "score":        int,   # 0–100
          "tier":         str,   # LOW / MEDIUM / HIGH / CRITICAL
          "hhi":          float,
          "gini":         float,
          "temporal":     { anomaly_score, anomalous_days, ... },
          "tx_count":     int,
          "total_volume": float,
        }
    """
    # ── Step 1: Fetch raw transactions ──
    raw_txns = get_wallet_transactions(wallet)
    if not raw_txns:
        raise HTTPException(status_code=404, detail="No transactions found for wallet")

    # ── Step 2: Normalize ──
    normalized = normalize_transactions(raw_txns, wallet)

    validated = []
    for tx in normalized:
        try:
            validated_tx = NormalizedTransaction(**tx).model_dump()
            validated.append(validated_tx)
        except Exception as e:
            print("Validation error:", e)

    if not validated:
        raise HTTPException(status_code=422, detail="All transactions failed validation")

    # Store normalized (idempotent — skip if already stored)
    if not is_wallet_normalized(wallet):
        insert_normalized_transactions(validated)

    # ── Step 3: Aggregate ──
    aggregates = compute_aggregates(validated, wallet)

    # ── Step 4: Risk Score ──
    risk_result = compute_risk_score(aggregates)

    # ── Step 5: Persist analysis history ──
    save_analysis_result(wallet, risk_result)

    return risk_result