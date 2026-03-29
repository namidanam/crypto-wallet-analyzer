from pymongo import MongoClient
from app.config.settings import MONGO_URI, DB_NAME

# Create client connection
client = MongoClient(MONGO_URI)

# Select the database
db = client[DB_NAME]

# Collections of raw data and wallet addresses of users
ledger_collection = db["ledgerentries"]
wallet_collection = db["wallets"]

# NEW collection for normalized data
normalized_collection = db["normalized_transactions"]

def get_wallet_transactions(wallet_address):
    # Fetch all transactions for a given wallet

    transactions = list(ledger_collection.find({
        "wallet": wallet_address
    }))

    return transactions

def insert_normalized_transactions(transactions):
    if transactions:
        normalized_collection.insert_many(transactions)
