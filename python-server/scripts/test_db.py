"""
    Testing to see if the get_wallet_transactions function works well
"""

from app.db.mongo import get_wallet_transactions
from app.processors.normalize import normalize_transactions

wallet = "0x1234567890123456789012345678901234567890"

txns = get_wallet_transactions(wallet)

print(f" Total transactions: {len(txns)}")

# Getting the first three transactions
for transaction in txns[:3]:
    print(transaction, end='\n\n\n', )

normalized_transactions = normalize_transactions(txns, wallet)

print(f"Number of normalized transactions: {len(normalized_transactions)}")

for ntxn in normalized_transactions[:3]:
    print(ntxn, end = '\n\n\n')
