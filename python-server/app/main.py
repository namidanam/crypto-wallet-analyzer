from fastapi import FastAPI, HTTPException
from app.schemas.models import WalletHistory, WalletAggregates, RiskScoreResponse
from app.processors.aggregates import compute_aggregates
from app.processors.aggregates_dict import compute_aggregates as compute_aggregates_dict
from app.processors.risk_engine import RiskEngine
from app.processors.risk_engine_statistical import (
    compute_risk_score,
)
from app.db.mongo import (
    get_wallet_transactions,
    insert_normalized_transactions,
    is_wallet_normalized,
    save_analysis_result,
)
from app.processors.normalize import normalize_transactions
from app.schemas.transaction import NormalizedTransaction

app = FastAPI(
    title="Crypto Wallet Risk Analyzer - Python Engine",
    description="Calculates statistical aggregates and ML risk scores from normalized data.",
    version="2.0.0",
)

risk_engine = RiskEngine()


# ── Health ──────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "python-server"}


# ── Pydantic-based endpoints (ML risk engine) ──────────────────────

@app.post("/aggregates", response_model=WalletAggregates)
def get_aggregates(history: WalletHistory):
    return compute_aggregates(history)


@app.post("/risk-score", response_model=RiskScoreResponse)
def get_risk_score(history: WalletHistory):
    aggregates = compute_aggregates(history)
    return risk_engine.calculate_risk(aggregates)


# ── Dict-based endpoints (normalize + HHI/Gini/temporal pipeline) ──

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

    normalized = normalize_transactions(raw_txns, wallet)

    validated = []
    for tx in normalized:
        try:
            validated_tx = NormalizedTransaction(**tx).model_dump()
            validated.append(validated_tx)
        except Exception as e:
            print("Validation error:", e)

    insert_normalized_transactions(validated)

    return {
        "wallet": wallet,
        "normalized_count": len(validated),
    }


@app.post("/analyze/{wallet}")
def analyze_wallet(wallet: str):
    """
    Full pipeline: normalize → aggregate → risk score → store.
    Returns the risk result to Node.js.
    """
    raw_txns = get_wallet_transactions(wallet)
    if not raw_txns:
        raise HTTPException(status_code=404, detail="No transactions found for wallet")

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

    if not is_wallet_normalized(wallet):
        insert_normalized_transactions(validated)

    aggregates = compute_aggregates_dict(validated, wallet)
    risk_result = compute_risk_score(aggregates)
    save_analysis_result(wallet, risk_result)

    return risk_result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
