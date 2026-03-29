# This defines the "(goal/final)" structure of normalized data
NORMALIZED_SCHEMA = {
    "tx_hash": str,
    "wallet": str,
    "from": str,
    "to": str,
    "amount": float,
    "token": str,
    "timestamp": int,
    "chain": str,
    "direction": str,  # "IN" or "OUT"
}

# Handles normalization of transaction for Eth, Bsc transactions
def normalize_evm(tx, wallet_address):
    normalized = []

    # Extract common fields
    tx_hash = tx.get("txHash")
    chain = tx.get("chain")
    timestamp = tx.get("timestamp")

    token_transfers = tx.get("tokenTransfers", [])

    # If tokenTransfers exist
    if token_transfers:
        for transfer in token_transfers:
            from_addr = transfer.get("from")
            to_addr = transfer.get("to")
            amount = float(transfer.get("amount", 0))
            token = transfer.get("tokenSymbol", "UNKNOWN")

            # Direction logic
            if from_addr == wallet_address:
                direction = "OUT"
            else:
                direction = "IN"

            normalized.append({
                "tx_hash": tx_hash,
                "wallet": wallet_address,
                "from": from_addr,
                "to": to_addr,
                "amount": amount,
                "token": token,
                "timestamp": timestamp,
                "chain": chain,
                "direction": direction
            })

    # Else (no tokenTransfers)
    else:
        from_addr = tx.get("from")
        to_addr = tx.get("to")
        amount = float(tx.get("amount", 0))

        if from_addr == wallet_address:
            direction = "OUT"
        else:
            direction = "IN"

        normalized.append({
            "tx_hash": tx_hash,
            "wallet": wallet_address,
            "from": from_addr,
            "to": to_addr,
            "amount": amount,
            "token": "NATIVE",
            "timestamp": timestamp,
            "chain": chain,
            "direction": direction
        })

    return normalized


"""
    Main normalization call - Routes all transactions to their 
    respective normalizing functions
"""

def normalize_transaction(tx, wallet_address):
    chain = tx.get("chain", "")

    # Handle EVM chains (Ethereum, BSC, etc.)
    if "eth" in chain or "bsc" in chain:
        return normalize_evm(tx, wallet_address)

    # Future support
    elif "btc" in chain:
        raise NotImplementedError("Bitcoin not supported yet")

    elif "doge" in chain:
        raise NotImplementedError("Dogecoin not supported yet")

    else:
        raise ValueError(f"Unsupported chain: {chain}")
    

# This is where the actual data gets called from the database
def normalize_transactions(transactions, wallet_address):
    all_normalized = []

    for tx in transactions:
        try:
            normalized_list = normalize_transaction(tx, wallet_address)

            # normalized_list is already a list
            all_normalized.extend(normalized_list)

        except Exception as e:
            print(f"Skipping transaction due to error: {e}")

    return all_normalized