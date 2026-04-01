from pymongo import MongoClient
from app.config.settings import MONGO_URI, DB_NAME
from datetime import datetime, timezone

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

ledger_collection     = db["ledgerentries"]
wallet_collection     = db["wallets"]
normalized_collection = db["normalized_transactions"]
analysis_collection   = db["analysisHistory"]          # REQ-9


def get_wallet_transactions(wallet_address: str) -> list:
    """Fetch all raw transactions for a wallet from ledgerentries."""
    return list(ledger_collection.find({"wallet": wallet_address}))


def insert_normalized_transactions(transactions: list) -> None:
    if transactions:
        normalized_collection.insert_many(transactions)


def is_wallet_normalized(wallet: str) -> bool:
    return normalized_collection.count_documents({"wallet": wallet}) > 0


def save_analysis_result(wallet: str, risk_result: dict) -> None:
    """
    Upserts the risk analysis result into analysisHistory collection.
    Node.js wallet.controller.js also writes here — this is the Python side.
    """
    analysis_collection.update_one(
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