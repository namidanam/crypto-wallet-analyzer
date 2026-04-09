"""
risk_engine_statistical.py
──────────────────────────
Statistical risk scoring (HHI, Gini, temporal anomaly detection).
Used by the /analyze/{wallet} pipeline.
Kept separate from risk_engine.py which handles the ML-based scoring.
"""

import math
import statistics
from collections import defaultdict


# ─────────────────────────────────────────────────────────
# 1. HHI — Herfindahl-Hirschman Index
# ─────────────────────────────────────────────────────────

def compute_hhi(counterparty_volumes: dict) -> float:
    total = sum(counterparty_volumes.values())
    if total == 0 or not counterparty_volumes:
        return 0.0
    hhi = sum((v / total) ** 2 for v in counterparty_volumes.values())
    return round(hhi, 6)


# ─────────────────────────────────────────────────────────
# 2. Gini Coefficient
# ─────────────────────────────────────────────────────────

def compute_gini(amounts: list) -> float:
    n = len(amounts)
    if n == 0:
        return 0.0
    vals = sorted(v for v in amounts if v > 0)
    n = len(vals)
    if n == 0:
        return 0.0
    total = sum(vals)
    if total == 0:
        return 0.0
    cumulative_sum = sum((i + 1) * v for i, v in enumerate(vals))
    gini = (2 * cumulative_sum) / (n * total) - (n + 1) / n
    return round(max(0.0, min(1.0, gini)), 6)


# ─────────────────────────────────────────────────────────
# 3. Temporal Anomaly Detection — Z-score
# ─────────────────────────────────────────────────────────

def compute_temporal_anomaly(frequency_by_day: dict) -> dict:
    if not frequency_by_day:
        return {
            "anomaly_score": 0.0, "anomalous_days": [],
            "mean_daily_tx": 0.0, "std_daily_tx": 0.0, "z_threshold": 2.0,
        }

    counts = list(frequency_by_day.values())
    if len(counts) < 2:
        return {
            "anomaly_score": 0.0, "anomalous_days": [],
            "mean_daily_tx": float(counts[0]) if counts else 0.0,
            "std_daily_tx": 0.0, "z_threshold": 2.0,
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
        "anomaly_score": round(anomaly_score, 6),
        "anomalous_days": sorted(anomalous_days),
        "mean_daily_tx": round(mean, 4),
        "std_daily_tx": round(std, 4),
        "z_threshold": z_threshold,
    }


# ─────────────────────────────────────────────────────────
# 4. Composite Risk Score
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
    wallet = aggregates.get("wallet", "")
    counterparty_volumes = aggregates.get("counterparty_volumes", {})
    amounts = aggregates.get("_amounts", [])
    frequency_by_day = aggregates.get("frequency_by_day", {})

    if not amounts:
        return {
            "wallet": wallet, "score": 0, "tier": "LOW",
            "hhi": 0.0, "gini": 0.0,
            "temporal": compute_temporal_anomaly({}),
            "tx_count": 0, "total_volume": 0.0,
        }

    hhi = compute_hhi(counterparty_volumes)
    gini = compute_gini(amounts)
    temporal = compute_temporal_anomaly(frequency_by_day)

    raw_score = (
        WEIGHTS["hhi"]      * hhi +
        WEIGHTS["gini"]     * gini +
        WEIGHTS["temporal"] * temporal["anomaly_score"]
    )

    score = int(min(100, max(0, round(raw_score * 100))))
    tier = _score_to_tier(score)

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
