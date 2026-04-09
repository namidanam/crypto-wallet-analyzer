from app.processors.normalize import normalize_transactions
from app.schemas.transaction import NormalizedTransaction
from app.db.mongo import (
    get_wallet_transactions,
    insert_normalized_transactions
)

wallet = "0x1234567890123456789012345678901234567890"

# 1. Fetch raw data
raw_txns = get_wallet_transactions(wallet)
print(f"Total number of raw transactions: {len(raw_txns)}")

# 2. Normalize raw data
normalized_txns = normalize_transactions(raw_txns, wallet)
print(f"Total number of normalized transactions: {len(normalized_txns)}")

# 3. Verify the normalized data
validated = []
for tx in normalized_txns:
    try:
        validate_txn = NormalizedTransaction(**tx).model_dump()
        validated.append(validate_txn)
    except Exception as e:
        print(f"Validation failed: {e}")

print(f"Valid transactions: {len(validated)}")

# 4. Store it in database

insert_normalized_transactions(validated)
print("Normalized data stored in database")