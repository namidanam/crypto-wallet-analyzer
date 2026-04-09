from pymongo import MongoClient
from app.config.settings import MONGO_URI, DB_NAME
from datetime import datetime, timezone

# Lazy connection — only initialize when MONGO_URI is configured
_client = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        if not MONGO_URI:
            raise RuntimeError("MONGO_URI is not configured. Set it in .env to use DB features.")
        _client = MongoClient(MONGO_URI)
        _db = _client[DB_NAME]
    return _db


def get_wallet_transactions(wallet_address: str) -> list:
    """Fetch all raw transactions for a wallet from ledgerentries."""
    db = _get_db()
    return list(db["ledgerentries"].find({"wallet": wallet_address}))


def insert_normalized_transactions(transactions: list) -> None:
    if transactions:
        db = _get_db()
        db["normalized_transactions"].insert_many(transactions)


def is_wallet_normalized(wallet: str) -> bool:
    db = _get_db()
    return db["normalized_transactions"].count_documents({"wallet": wallet}) > 0


def save_analysis_result(wallet: str, risk_result: dict) -> None:
    """
    Upserts the risk analysis result into analysisHistory collection.
    """
    db = _get_db()
    db["analysisHistory"].update_one(
        {"wallet": wallet},
        {
            "$set": {
                **risk_result,
                "updatedAt": datetime.now(tz=timezone.utc),
            },
            "$setOnInsert": {
                "createdAt": datetime.now(tz=timezone.utc),
            },
        },
        upsert=True,
    )