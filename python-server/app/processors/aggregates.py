"""
aggregates.py
─────────────
Computes statistical aggregates from a list of NormalizedTransaction dicts.
Called by main.py → /analyze/{wallet} endpoint, feeding into risk_engine.py.

Output shape (AggregateResult):
    {
      "wallet":            str,
      "tx_count":          int,
      "total_volume":      float,   # sum of all amounts (IN + OUT)
      "avg_tx_value":      float,
      "max_tx_value":      float,
      "unique_counterparties": int, # distinct from/to addresses (excluding wallet)
      "in_count":          int,
      "out_count":         int,
      "in_volume":         float,
      "out_volume":        float,
      "frequency_by_day":  dict[str, int],  # "YYYY-MM-DD" → count
      "counterparty_volumes": dict[str, float], # address → total volume
    }
"""

from datetime import datetime, timezone
from collections import defaultdict


def compute_aggregates(normalized_txs: list, wallet_address: str) -> dict:
    """
    Computes aggregate statistics from a normalized transaction list.

    @param normalized_txs  - List of NormalizedTransaction dicts (output of normalize.py).
    @param wallet_address  - The wallet being analyzed.
    @returns AggregateResult dict.
    """
    if not normalized_txs:
        return _empty_aggregates(wallet_address)

    tx_count = 0
    total_volume = 0.0
    in_count = 0
    out_count = 0
    in_volume = 0.0
    out_volume = 0.0
    max_tx_value = 0.0
    amounts = []

    # address → total volume transacted with this wallet
    counterparty_volumes: dict[str, float] = defaultdict(float)

    # "YYYY-MM-DD" → number of transactions on that day
    frequency_by_day: dict[str, int] = defaultdict(int)

    for tx in normalized_txs:
        amount = float(tx.get("amount", 0) or 0)
        direction = tx.get("direction", "")
        timestamp_ms = int(tx.get("timestamp", 0) or 0)

        tx_count += 1
        total_volume += amount
        amounts.append(amount)
        max_tx_value = max(max_tx_value, amount)

        # Direction breakdown
        if direction == "IN":
            in_count += 1
            in_volume += amount
            counterparty = tx.get("from_address") or ""
        else:
            out_count += 1
            out_volume += amount
            counterparty = tx.get("to_address") or ""

        # Counterparty tracking (skip self)
        if counterparty and counterparty.lower() != wallet_address.lower():
            counterparty_volumes[counterparty] += amount

        # Daily frequency
        if timestamp_ms:
            # Tatum gives seconds for older txs; normalise to ms
            ts = timestamp_ms if timestamp_ms > 1_000_000_000_000 else timestamp_ms * 1000
            day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            frequency_by_day[day] += 1

    avg_tx_value = total_volume / tx_count if tx_count else 0.0
    unique_counterparties = len(counterparty_volumes)

    return {
        "wallet":                wallet_address,
        "tx_count":              tx_count,
        "total_volume":          round(total_volume, 8),
        "avg_tx_value":          round(avg_tx_value, 8),
        "max_tx_value":          round(max_tx_value, 8),
        "unique_counterparties": unique_counterparties,
        "in_count":              in_count,
        "out_count":             out_count,
        "in_volume":             round(in_volume, 8),
        "out_volume":            round(out_volume, 8),
        "frequency_by_day":      dict(frequency_by_day),
        "counterparty_volumes":  dict(counterparty_volumes),
        # Keep raw amounts list for HHI / Gini calculation in risk_engine.py
        "_amounts":              amounts,
    }


def _empty_aggregates(wallet_address: str) -> dict:
    return {
        "wallet":                wallet_address,
        "tx_count":              0,
        "total_volume":          0.0,
        "avg_tx_value":          0.0,
        "max_tx_value":          0.0,
        "unique_counterparties": 0,
        "in_count":              0,
        "out_count":             0,
        "in_volume":             0.0,
        "out_volume":            0.0,
        "frequency_by_day":      {},
        "counterparty_volumes":  {},
        "_amounts":              [],
    }