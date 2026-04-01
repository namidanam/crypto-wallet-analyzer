"""
risk_engine.py
──────────────
Computes the composite risk score (0–100) for a wallet.

Metrics implemented:
  1. HHI  — Herfindahl-Hirschman Index (value concentration)   ✅ REQ-8.1
  2. Gini — Gini coefficient (wealth/transfer inequality)        ✅ REQ-8.1 / Sprint 4
  3. Z-score temporal anomaly detection                          ✅ REQ-8.1 / Sprint 4

Score tiers:
  0–25  → LOW
  26–50 → MEDIUM
  51–75 → HIGH
  76–100 → CRITICAL
"""

import math
import statistics
from collections import defaultdict


# ─────────────────────────────────────────────────────────
# 1. HHI — Herfindahl-Hirschman Index
#    Measures how concentrated transactions are among
#    a small number of counterparties.
#    Range: 0 (perfectly spread) → 1 (one counterparty).
#    Risk increases as HHI → 1.
# ─────────────────────────────────────────────────────────

def compute_hhi(counterparty_volumes: dict) -> float:
    """
    @param counterparty_volumes - dict[address, total_volume]
    @returns float HHI in [0, 1]
    """
    total = sum(counterparty_volumes.values())
    if total == 0 or not counterparty_volumes:
        return 0.0

    hhi = sum((v / total) ** 2 for v in counterparty_volumes.values())
    return round(hhi, 6)


# ─────────────────────────────────────────────────────────
# 2. Gini Coefficient
#    Measures inequality of transaction values.
#    Range: 0 (all txs equal) → 1 (one tx dominates).
#    High Gini → unusual spikes = risk signal.
# ─────────────────────────────────────────────────────────

def compute_gini(amounts: list) -> float:
    """
    Computes the Gini coefficient from a list of transaction amounts.
    Uses the sorted absolute-difference formula — O(n log n).

    @param amounts - List of floats (transaction amounts).
    @returns float Gini in [0, 1]
    """
    n = len(amounts)
    if n == 0:
        return 0.0

    # Filter out zero/negative values
    vals = sorted(v for v in amounts if v > 0)
    n = len(vals)
    if n == 0:
        return 0.0

    total = sum(vals)
    if total == 0:
        return 0.0

    # Gini = (2 * Σ i*x_i) / (n * Σ x_i) - (n+1)/n
    cumulative_sum = sum((i + 1) * v for i, v in enumerate(vals))
    gini = (2 * cumulative_sum) / (n * total) - (n + 1) / n
    return round(max(0.0, min(1.0, gini)), 6)


# ─────────────────────────────────────────────────────────
# 3. Temporal Anomaly Detection — Z-score
#    Detects days with abnormally high transaction frequency.
#    A day is anomalous if its count > mean + 2*std.
#    Risk score = fraction of anomalous days.
# ─────────────────────────────────────────────────────────

def compute_temporal_anomaly(frequency_by_day: dict) -> dict:
    """
    Detects temporal spikes in daily transaction frequency using Z-scores.

    @param frequency_by_day - dict["YYYY-MM-DD", int] from aggregates.py
    @returns {
        "anomaly_score":   float in [0, 1],
        "anomalous_days":  list[str],
        "mean_daily_tx":   float,
        "std_daily_tx":    float,
        "z_threshold":     float,
    }
    """
    if not frequency_by_day:
        return {
            "anomaly_score": 0.0,
            "anomalous_days": [],
            "mean_daily_tx": 0.0,
            "std_daily_tx": 0.0,
            "z_threshold": 2.0,
        }

    counts = list(frequency_by_day.values())

    if len(counts) < 2:
        # Only one data point — can't compute std
        return {
            "anomaly_score": 0.0,
            "anomalous_days": [],
            "mean_daily_tx": float(counts[0]) if counts else 0.0,
            "std_daily_tx": 0.0,
            "z_threshold": 2.0,
        }

    mean = statistics.mean(counts)
    std = statistics.stdev(counts)
    z_threshold = 2.0

    anomalous_days = []
    if std > 0:
        for day, count in frequency_by_day.items():
            z_score = (count - mean) / std
            if z_score > z_threshold:
                anomalous_days.append(day)

    total_days = len(frequency_by_day)
    anomaly_score = len(anomalous_days) / total_days if total_days else 0.0

    return {
        "anomaly_score":  round(anomaly_score, 6),
        "anomalous_days": sorted(anomalous_days),
        "mean_daily_tx":  round(mean, 4),
        "std_daily_tx":   round(std, 4),
        "z_threshold":    z_threshold,
    }


# ─────────────────────────────────────────────────────────
# 4. Composite Risk Score
#    Weighted combination of HHI, Gini, and temporal anomaly.
#    Weights (tunable):
#      HHI    → 40%
#      Gini   → 35%
#      Temporal anomaly → 25%
# ─────────────────────────────────────────────────────────

WEIGHTS = {
    "hhi":      0.40,
    "gini":     0.35,
    "temporal": 0.25,
}


def _score_to_tier(score: float) -> str:
    if score <= 25:
        return "LOW"
    elif score <= 50:
        return "MEDIUM"
    elif score <= 75:
        return "HIGH"
    else:
        return "CRITICAL"


def compute_risk_score(aggregates: dict) -> dict:
    """
    Computes the full risk assessment from an AggregateResult dict.

    @param aggregates - Output of aggregates.compute_aggregates()
    @returns {
        "wallet":        str,
        "score":         int  (0–100),
        "tier":          str  (LOW / MEDIUM / HIGH / CRITICAL),
        "hhi":           float,
        "gini":          float,
        "temporal":      dict  (anomaly sub-report),
        "tx_count":      int,
        "total_volume":  float,
    }
    """
    wallet = aggregates.get("wallet", "")

    # Pull pre-computed data from aggregates
    counterparty_volumes = aggregates.get("counterparty_volumes", {})
    amounts              = aggregates.get("_amounts", [])
    frequency_by_day     = aggregates.get("frequency_by_day", {})

    # Guard: no data → zero risk
    if not amounts:
        return {
            "wallet":       wallet,
            "score":        0,
            "tier":         "LOW",
            "hhi":          0.0,
            "gini":         0.0,
            "temporal":     compute_temporal_anomaly({}),
            "tx_count":     0,
            "total_volume": 0.0,
        }

    # Compute individual metrics
    hhi     = compute_hhi(counterparty_volumes)
    gini    = compute_gini(amounts)
    temporal = compute_temporal_anomaly(frequency_by_day)

    # Weighted composite (each metric already in [0, 1])
    raw_score = (
        WEIGHTS["hhi"]      * hhi +
        WEIGHTS["gini"]     * gini +
        WEIGHTS["temporal"] * temporal["anomaly_score"]
    )

    # Scale to 0–100 and clamp
    score = int(min(100, max(0, round(raw_score * 100))))
    tier  = _score_to_tier(score)

    return {
        "wallet":       wallet,
        "score":        score,
        "tier":         tier,
        "hhi":          hhi,
        "gini":         gini,
        "temporal":     temporal,
        "tx_count":     aggregates.get("tx_count", 0),
        "total_volume": aggregates.get("total_volume", 0.0),
    }