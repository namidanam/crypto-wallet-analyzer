"""
test_risk_engine.py
───────────────────
Tests for both the ML-based RiskEngine and the statistical risk functions.
"""

import pytest
from app.processors.risk_engine import RiskEngine
from app.schemas.models import WalletAggregates
from app.processors.risk_engine_statistical import (
    compute_hhi,
    compute_gini,
    compute_temporal_anomaly,
    compute_risk_score,
    _score_to_tier,
)


# ═══════════════════════════════════════════════════════════════════
# ML Risk Engine Tests
# ═══════════════════════════════════════════════════════════════════


def test_evaluate_heuristic_max_score():
    """All original rules fire → capped at 100."""
    engine = RiskEngine()
    agg = WalletAggregates(
        wallet_address="0x123",
        total_tx_count=2000,
        total_volume=500000.0,
        unique_interacted_addresses=600,
        avg_tx_value=250.0,
        active_days=2,
        risk_factors=[],
    )

    score = engine.evaluate_heuristic(agg)
    assert score == 100.0
    assert "High transaction frequency" in agg.risk_factors
    assert "High transaction volume" in agg.risk_factors
    assert "High activity in short duration (burner wallet format)" in agg.risk_factors


def test_evaluate_heuristic_base_only():
    """Low-risk profile — only the base 10 points."""
    engine = RiskEngine()
    agg = WalletAggregates(
        wallet_address="0xabc",
        total_tx_count=10,
        total_volume=500.0,
        unique_interacted_addresses=5,
        avg_tx_value=50.0,
        active_days=10,
        risk_factors=[],
    )

    score = engine.evaluate_heuristic(agg)
    assert score == 10.0
    assert agg.risk_factors == []


def test_heuristic_large_single_tx():
    """max_tx_value > 50 000 → +15 + flag."""
    engine = RiskEngine()
    agg = WalletAggregates(
        wallet_address="0xwhale",
        total_tx_count=5,
        total_volume=60000.0,
        unique_interacted_addresses=3,
        avg_tx_value=12000.0,
        active_days=10,
        max_tx_value=55000.0,
        risk_factors=[],
    )
    score = engine.evaluate_heuristic(agg)
    assert score == 25.0
    assert "Unusually large single transaction" in agg.risk_factors


def test_heuristic_high_error_rate():
    """error_tx_ratio > 0.15 → +15 + flag."""
    engine = RiskEngine()
    agg = WalletAggregates(
        wallet_address="0xerr",
        total_tx_count=20,
        total_volume=1000.0,
        unique_interacted_addresses=5,
        avg_tx_value=50.0,
        active_days=10,
        error_tx_count=5,
        error_tx_ratio=0.25,
        risk_factors=[],
    )
    score = engine.evaluate_heuristic(agg)
    assert score == 25.0
    assert "High failed transaction rate" in agg.risk_factors


def test_heuristic_mixer_pattern():
    """Near-zero net flow + >100 txs → +25."""
    engine = RiskEngine()
    agg = WalletAggregates(
        wallet_address="0xmix",
        total_tx_count=150,
        total_volume=10000.0,
        unique_interacted_addresses=50,
        avg_tx_value=66.67,
        active_days=30,
        net_flow=100.0,
        total_incoming_volume=5050.0,
        total_outgoing_volume=4950.0,
        std_tx_value=50.0,
        risk_factors=[],
    )
    score = engine.evaluate_heuristic(agg)
    assert score == 35.0
    assert "Near-zero net flow (potential mixer)" in agg.risk_factors


def test_heuristic_bot_detection():
    """avg_time_between_tx < 30s + >200 txs → +20."""
    engine = RiskEngine()
    agg = WalletAggregates(
        wallet_address="0xbot",
        total_tx_count=300,
        total_volume=5000.0,
        unique_interacted_addresses=10,
        avg_tx_value=16.67,
        active_days=5,
        avg_time_between_tx=15.0,
        net_flow=1000.0,
        std_tx_value=50.0,
        risk_factors=[],
    )
    score = engine.evaluate_heuristic(agg)
    assert score == 30.0
    assert "Rapid-fire transactions (bot pattern)" in agg.risk_factors


def test_heuristic_address_concentration():
    """max_single_address_volume > 80% of total_volume → +15."""
    engine = RiskEngine()
    agg = WalletAggregates(
        wallet_address="0xconc",
        total_tx_count=10,
        total_volume=1000.0,
        unique_interacted_addresses=3,
        avg_tx_value=100.0,
        active_days=10,
        max_single_address_volume=900.0,
        risk_factors=[],
    )
    score = engine.evaluate_heuristic(agg)
    assert score == 25.0
    assert "High counterparty concentration" in agg.risk_factors


def test_heuristic_uniform_values():
    """std_tx_value < avg_tx_value * 0.05 + >50 txs → +10."""
    engine = RiskEngine()
    agg = WalletAggregates(
        wallet_address="0xuniform",
        total_tx_count=100,
        total_volume=50000.0,
        unique_interacted_addresses=20,
        avg_tx_value=500.0,
        active_days=30,
        std_tx_value=10.0,
        risk_factors=[],
    )
    score = engine.evaluate_heuristic(agg)
    assert score == 20.0
    assert "Suspiciously uniform transaction values" in agg.risk_factors


def test_ml_fallback_without_model():
    """Without a model file, ML returns (25.0, {})."""
    engine = RiskEngine()
    engine.model = None
    agg = WalletAggregates(
        wallet_address="0xfallback",
        total_tx_count=10,
        total_volume=500.0,
        unique_interacted_addresses=5,
        avg_tx_value=50.0,
        active_days=10,
        risk_factors=[],
    )
    score, contributions = engine.evaluate_ml(agg)
    assert score == 25.0
    assert contributions == {}


def test_ml_feature_vector_length():
    """Feature vector has exactly 17 elements."""
    engine = RiskEngine()
    agg = WalletAggregates(
        wallet_address="0xlen",
        total_tx_count=10,
        total_volume=500.0,
        unique_interacted_addresses=5,
        avg_tx_value=50.0,
        active_days=10,
        risk_factors=[],
    )
    fv = engine._build_feature_vector(agg)
    assert len(fv) == 17


def test_calculate_risk_full_pipeline():
    """calculate_risk returns a valid RiskScoreResponse."""
    engine = RiskEngine()
    agg = WalletAggregates(
        wallet_address="0xpipeline",
        total_tx_count=10,
        total_volume=500.0,
        unique_interacted_addresses=5,
        avg_tx_value=50.0,
        active_days=10,
        risk_factors=[],
    )
    res = engine.calculate_risk(agg)
    assert res.wallet_address == "0xpipeline"
    assert res.heuristic_score == 10.0
    assert res.overall_score >= 0.0
    assert res.risk_level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert isinstance(res.feature_contributions, dict)


def test_calculate_risk_high_risk_profile():
    """Profile triggering multiple rules gets a higher score."""
    engine = RiskEngine()
    agg = WalletAggregates(
        wallet_address="0xdanger",
        total_tx_count=1500,
        total_volume=200000.0,
        unique_interacted_addresses=600,
        avg_tx_value=133.33,
        active_days=2,
        max_tx_value=80000.0,
        error_tx_ratio=0.20,
        error_tx_count=300,
        risk_factors=[],
    )
    res = engine.calculate_risk(agg)
    assert res.heuristic_score == 100.0
    assert res.risk_level in ["HIGH", "CRITICAL"]
    assert "High transaction frequency" in res.flags
    assert "Unusually large single transaction" in res.flags
    assert "High failed transaction rate" in res.flags


# ═══════════════════════════════════════════════════════════════════
# Statistical Risk Engine Tests (HHI, Gini, Temporal)
# ═══════════════════════════════════════════════════════════════════


class TestHhi:

    def test_tc15_hhi_known_value(self):
        vols = {"addr1": 50.0, "addr2": 25.0, "addr3": 25.0}
        hhi = compute_hhi(vols)
        assert hhi == pytest.approx(0.375, rel=1e-4)

    def test_hhi_single_counterparty_is_one(self):
        assert compute_hhi({"onlyone": 100.0}) == pytest.approx(1.0)

    def test_hhi_equal_distribution(self):
        vols = {f"addr{i}": 10.0 for i in range(10)}
        assert compute_hhi(vols) == pytest.approx(0.1, rel=1e-4)

    def test_hhi_empty(self):
        assert compute_hhi({}) == 0.0


class TestGini:

    def test_perfect_equality(self):
        amounts = [10.0, 10.0, 10.0, 10.0]
        assert compute_gini(amounts) == pytest.approx(0.0, abs=1e-6)

    def test_perfect_inequality(self):
        amounts = [1000.0] + [0.001] * 99
        gini = compute_gini(amounts)
        assert gini > 0.9

    def test_typical_values(self):
        amounts = [1.0, 2.0, 5.0, 10.0, 50.0]
        gini = compute_gini(amounts)
        assert 0.0 <= gini <= 1.0

    def test_empty(self):
        assert compute_gini([]) == 0.0

    def test_zeros_filtered(self):
        assert compute_gini([0.0, 0.0]) == 0.0


class TestTemporalAnomaly:

    def test_no_anomaly_uniform(self):
        freq = {f"2024-01-{d:02d}": 3 for d in range(1, 20)}
        result = compute_temporal_anomaly(freq)
        assert result["anomaly_score"] == 0.0
        assert result["anomalous_days"] == []

    def test_spike_detected(self):
        freq = {f"2024-01-{d:02d}": 2 for d in range(1, 20)}
        freq["2024-01-20"] = 100
        result = compute_temporal_anomaly(freq)
        assert "2024-01-20" in result["anomalous_days"]
        assert result["anomaly_score"] > 0.0

    def test_single_day(self):
        result = compute_temporal_anomaly({"2024-01-01": 5})
        assert result["anomaly_score"] == 0.0

    def test_empty(self):
        result = compute_temporal_anomaly({})
        assert result["anomaly_score"] == 0.0


class TestCompositeScore:

    def _make_aggregates(self, amounts, counterparty_vols, freq):
        return {
            "wallet": "0xtest",
            "_amounts": amounts,
            "counterparty_volumes": counterparty_vols,
            "frequency_by_day": freq,
            "tx_count": len(amounts),
            "total_volume": sum(amounts),
        }

    def test_tc16_score_in_range(self):
        agg = self._make_aggregates(
            amounts=[1.0, 2.0, 3.0, 100.0],
            counterparty_vols={"addr1": 90.0, "addr2": 10.0, "addr3": 6.0},
            freq={"2024-01-01": 2, "2024-01-02": 1},
        )
        result = compute_risk_score(agg)
        assert 0 <= result["score"] <= 100
        assert result["tier"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_zero_data_returns_low(self):
        agg = self._make_aggregates([], {}, {})
        result = compute_risk_score(agg)
        assert result["score"] == 0
        assert result["tier"] == "LOW"

    def test_high_concentration_scores_higher(self):
        concentrated = self._make_aggregates(
            amounts=[100.0] * 10,
            counterparty_vols={"single_addr": 1000.0},
            freq={"2024-01-01": 10},
        )
        spread = self._make_aggregates(
            amounts=[10.0] * 10,
            counterparty_vols={f"addr{i}": 10.0 for i in range(10)},
            freq={"2024-01-01": 10},
        )
        concentrated_score = compute_risk_score(concentrated)["score"]
        spread_score = compute_risk_score(spread)["score"]
        assert concentrated_score > spread_score

    def test_tier_mapping(self):
        assert _score_to_tier(0)   == "LOW"
        assert _score_to_tier(25)  == "LOW"
        assert _score_to_tier(26)  == "MEDIUM"
        assert _score_to_tier(50)  == "MEDIUM"
        assert _score_to_tier(51)  == "HIGH"
        assert _score_to_tier(75)  == "HIGH"
        assert _score_to_tier(76)  == "CRITICAL"
        assert _score_to_tier(100) == "CRITICAL"
