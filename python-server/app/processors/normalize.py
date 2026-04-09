# This defines the "(goal/final)" structure of normalized data
NORMALIZED_SCHEMA = {
    "tx_hash": str,
    "wallet": str,
    "from_address": str,
    "to_address": str,
    "amount": float,
    "token": str,
    "timestamp": int,
    "chain": str,
    "direction": str,  # "IN" or "OUT"
}

# ──────────────────────────────────────────────
# EVM normalizer (ETH, BSC, Polygon) — unchanged
# ──────────────────────────────────────────────
def normalize_evm(tx, wallet_address):
    """
    Normalizes raw transaction data from GoldRush (Covalent) for EVM chains.
    @param tx         - Single raw transaction dict from GoldRush.
    @param wallet_address - The wallet we are analyzing.
    @returns list[NormalizedTransaction dicts]
    """
    normalized = []

    tx_hash = tx.get("txHash")
    chain = tx.get("chain")
    timestamp = tx.get("timestamp")
    asset_type = tx.get("assetType")
    native_value = tx.get("nativeValue")
    token_transfers = tx.get("tokenTransfers", [])

    if token_transfers:
        for transfer in token_transfers:
            from_addr = transfer.get("from")
            to_addr = transfer.get("to")
            amount = float(transfer.get("amount", 0))
            token = transfer.get("tokenSymbol", "UNKNOWN")

            direction = "OUT" if from_addr == wallet_address else "IN"

            normalized.append({
                "tx_hash": tx_hash,
                "wallet": wallet_address,
                "from_address": from_addr,
                "to_address": to_addr,
                "amount": amount,
                "token": token,
                "timestamp": timestamp,
                "chain": chain,
                "direction": direction,
                "tokenAddress": transfer.get("tokenAddress"),
                "assetType": asset_type,
                "nativeValue": native_value,
            })
    else:
        from_addr = tx.get("from")
        to_addr = tx.get("to")
        amount = float(tx.get("amount", 0))

        direction = "OUT" if from_addr == wallet_address else "IN"

        normalized.append({
            "tx_hash": tx_hash,
            "wallet": wallet_address,
            "from_address": from_addr,
            "to_address": to_addr,
            "amount": amount,
            "token": "NATIVE",
            "timestamp": timestamp,
            "chain": chain,
            "direction": direction,
            "tokenAddress": None,
            "assetType": asset_type,
            "nativeValue": native_value,
        })

    return normalized


# ──────────────────────────────────────────────────────────────────
# UTXO helpers — shared by BTC, Doge, LTC
# ──────────────────────────────────────────────────────────────────

def _satoshi_to_coin(satoshi_value) -> float:
    """
    Convert satoshi (or smallest UTXO unit) to whole-coin float.
    Works for BTC (÷1e8), DOGE (÷1e8), LTC (÷1e8).
    Input may be int, float, or string.
    """
    try:
        return float(satoshi_value) / 1e8
    except (TypeError, ValueError):
        return 0.0


def _aggregate_utxo_inputs(vin: list, wallet_address: str):
    """
    UTXO transactions have multiple inputs (vin) and multiple outputs (vout).
    We sum all input values that belong to our wallet to get the total sent amount.

    Tatum UTXO vin entry shape (typical):
        {
          "txid": "...",       # previous tx
          "vout": 0,
          "addresses": ["1A2B..."],
          "value": "50000"     # satoshis, may be string
        }

    Returns: (total_input_satoshis_from_wallet: float, primary_sender: str)
    """
    total_in = 0.0
    primary_sender = wallet_address  # fallback

    for inp in vin:
        addrs = inp.get("addresses") or inp.get("address") or []
        if isinstance(addrs, str):
            addrs = [addrs]
        value = float(inp.get("value", 0) or 0)
        if wallet_address in addrs:
            total_in += value
            primary_sender = addrs[0] if addrs else wallet_address

    return total_in, primary_sender


def _aggregate_utxo_outputs(vout: list, wallet_address: str):
    """
    Sum all outputs going TO our wallet (these are "IN" amounts).

    Tatum UTXO vout entry shape (typical):
        {
          "value": "49000",
          "addresses": ["1A2B..."],
          "n": 0
        }

    Returns: (total_received_satoshis: float, primary_receiver: str)
    """
    total_out = 0.0
    primary_receiver = wallet_address  # fallback

    for out in vout:
        addrs = out.get("addresses") or out.get("address") or []
        if isinstance(addrs, str):
            addrs = [addrs]
        value = float(out.get("value", 0) or 0)
        if wallet_address in addrs:
            total_out += value
            primary_receiver = addrs[0] if addrs else wallet_address

    return total_out, primary_receiver


def _normalize_utxo(tx, wallet_address: str, token_symbol: str, chain_name: str) -> list:
    """
    Generic UTXO normalizer — used by BTC, Doge, and LTC.

    Tatum returns the raw Bitcoin-protocol tx structure. A single tx can be
    both a sender and receiver (change outputs), so we may emit both an OUT
    and an IN record.

    Raw tx shape from Tatum UTXO endpoint:
        {
          "txid": "abc123",
          "blocktime": 1680000000,  # unix seconds
          "time": 1680000000,
          "vin":  [ { "addresses": [...], "value": "50000" }, ... ],
          "vout": [ { "addresses": [...], "value": "49000" }, ... ],
          ...
        }
    """
    normalized = []

    tx_hash = (
        tx.get("txHash")    # already remapped by tatum.service.js
        or tx.get("txid")
        or tx.get("txId")
        or tx.get("hash")
        or ""
    )

    # Timestamps: Tatum may give blocktime (unix seconds) or already-ms timestamp
    raw_ts = (
        tx.get("timestamp")   # already ms — set by tatum.service.js
        or tx.get("blocktime")
        or tx.get("time")
        or 0
    )
    # Normalise to milliseconds
    ts_int = int(raw_ts)
    timestamp = ts_int if ts_int > 1_000_000_000_000 else ts_int * 1000

    vin  = tx.get("vin")  or tx.get("inputs")  or []
    vout = tx.get("vout") or tx.get("outputs") or []

    # ── Determine whether this wallet is a SENDER ──
    total_in_sat, primary_sender = _aggregate_utxo_inputs(vin, wallet_address)
    if total_in_sat > 0:
        # wallet is a sender; find the primary recipient (first non-wallet output)
        primary_receiver = wallet_address
        for out in vout:
            addrs = out.get("addresses") or out.get("address") or []
            if isinstance(addrs, str):
                addrs = [addrs]
            if addrs and wallet_address not in addrs:
                primary_receiver = addrs[0]
                break

        normalized.append({
            "tx_hash":      tx_hash,
            "wallet":       wallet_address,
            "from_address": primary_sender,
            "to_address":   primary_receiver,
            "amount":       _satoshi_to_coin(total_in_sat),
            "token":        token_symbol,
            "timestamp":    timestamp,
            "chain":        chain_name,
            "direction":    "OUT",
            "assetType":    "NATIVE",
            "tokenAddress": None,
            "nativeValue":  None,
        })

    # ── Determine whether this wallet is a RECEIVER ──
    total_out_sat, primary_receiver = _aggregate_utxo_outputs(vout, wallet_address)
    if total_out_sat > 0:
        # Find primary sender (first vin address)
        primary_sender = wallet_address
        if vin:
            first_addrs = vin[0].get("addresses") or vin[0].get("address") or []
            if isinstance(first_addrs, str):
                first_addrs = [first_addrs]
            if first_addrs:
                primary_sender = first_addrs[0]

        normalized.append({
            "tx_hash":      tx_hash,
            "wallet":       wallet_address,
            "from_address": primary_sender,
            "to_address":   primary_receiver,
            "amount":       _satoshi_to_coin(total_out_sat),
            "token":        token_symbol,
            "timestamp":    timestamp,
            "chain":        chain_name,
            "direction":    "IN",
            "assetType":    "NATIVE",
            "tokenAddress": None,
            "nativeValue":  None,
        })

    # Edge case: Tatum already remapped to a flat shape (no vin/vout)
    # tatum.service.js maps tx → { txHash, from, to, value, timestamp }
    # Fall back to that if vin/vout are both empty.
    if not normalized:
        from_addr = tx.get("from") or wallet_address
        to_addr   = tx.get("to")   or wallet_address
        value_sat = float(tx.get("value", 0) or 0)
        direction = "OUT" if from_addr == wallet_address else "IN"

        normalized.append({
            "tx_hash":      tx_hash,
            "wallet":       wallet_address,
            "from_address": from_addr,
            "to_address":   to_addr,
            "amount":       _satoshi_to_coin(value_sat),
            "token":        token_symbol,
            "timestamp":    timestamp,
            "chain":        chain_name,
            "direction":    direction,
            "assetType":    "NATIVE",
            "tokenAddress": None,
            "nativeValue":  None,
        })

    return normalized


# ──────────────────────────────────────────────
# Public chain-specific normalizers (TC-13, Card 3)
# ──────────────────────────────────────────────

def normalize_btc(tx, wallet_address: str) -> list:
    """
    Normalizes a raw Bitcoin transaction from Tatum into the unified schema.
    Handles multi-input UTXO aggregation (TC-13).

    @param tx             - Raw Tatum BTC transaction dict.
    @param wallet_address - The BTC address being analyzed.
    @returns list[NormalizedTransaction dicts]
    """
    chain = tx.get("chain", "btc-mainnet")
    return _normalize_utxo(tx, wallet_address, "BTC", chain)


def normalize_doge(tx, wallet_address: str) -> list:
    """
    Normalizes a raw Dogecoin transaction from Tatum into the unified schema.

    @param tx             - Raw Tatum DOGE transaction dict.
    @param wallet_address - The DOGE address being analyzed.
    @returns list[NormalizedTransaction dicts]
    """
    chain = tx.get("chain", "doge-mainnet")
    return _normalize_utxo(tx, wallet_address, "DOGE", chain)


def normalize_ltc(tx, wallet_address: str) -> list:
    """
    Normalizes a raw Litecoin transaction from Tatum into the unified schema.

    @param tx             - Raw Tatum LTC transaction dict.
    @param wallet_address - The LTC address being analyzed.
    @returns list[NormalizedTransaction dicts]
    """
    chain = tx.get("chain", "ltc-mainnet")
    return _normalize_utxo(tx, wallet_address, "LTC", chain)


# ──────────────────────────────────────────────
# Router — dispatches to the right normalizer
# ──────────────────────────────────────────────

def normalize_transaction(tx, wallet_address: str) -> list:
    """
    Routes a raw transaction to the correct chain normalizer.

    @param tx             - Raw transaction dict (from GoldRush or Tatum).
    @param wallet_address - The wallet being analyzed.
    @returns list[NormalizedTransaction dicts]
    @throws ValueError for truly unsupported chains.
    """
    chain = tx.get("chain", "").lower()

    if "eth" in chain or "bsc" in chain or "matic" in chain or "polygon" in chain:
        return normalize_evm(tx, wallet_address)

    elif "btc" in chain or "bitcoin" in chain:
        return normalize_btc(tx, wallet_address)

    elif "doge" in chain or "dogecoin" in chain:
        return normalize_doge(tx, wallet_address)

    elif "ltc" in chain or "litecoin" in chain:
        return normalize_ltc(tx, wallet_address)

    else:
        raise ValueError(f"Unsupported chain: {chain}")


def normalize_transactions(transactions: list, wallet_address: str) -> list:
    """
    Normalizes a list of raw transactions for a given wallet.
    Skips transactions that fail normalization with a warning.

    @param transactions   - List of raw transaction dicts.
    @param wallet_address - The wallet being analyzed.
    @returns list[NormalizedTransaction dicts]
    """
    all_normalized = []

    for tx in transactions:
        try:
            normalized_list = normalize_transaction(tx, wallet_address)
            all_normalized.extend(normalized_list)
        except Exception as e:
            print(f"Skipping transaction due to error: {e}")

    return all_normalized