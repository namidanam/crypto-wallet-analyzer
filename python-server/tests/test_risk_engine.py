"""
test_risk_engine.py
───────────────────
Unit tests for risk_engine.py

Covers:
  TC-15  HHI concentration index
  TC-16  Composite risk score
  TC-XX  Gini coefficient
  TC-XX  Temporal anomaly Z-score
"""

import pytest
from app.processors.risk_engine import (
    compute_hhi,
    compute_gini,
    compute_temporal_anomaly,
    compute_risk_score,
)


class TestHhi:

    def test_tc15_hhi_known_value(self):
        """TC-15: HHI with one dominant counterparty (0.31 per test fixture)."""
        # 3 counterparties: one has 50% of volume, two have 25% each
        # HHI = 0.5^2 + 0.25^2 + 0.25^2 = 0.25 + 0.0625 + 0.0625 = 0.375
        vols = {"addr1": 50.0, "addr2": 25.0, "addr3": 25.0}
        hhi = compute_hhi(vols)
        assert hhi == pytest.approx(0.375, rel=1e-4)

    def test_hhi_single_counterparty_is_one(self):
        """One counterparty = maximum concentration."""
        assert compute_hhi({"onlyone": 100.0}) == pytest.approx(1.0)

    def test_hhi_equal_distribution(self):
        """10 equal counterparties → HHI = 0.1."""
        vols = {f"addr{i}": 10.0 for i in range(10)}
        assert compute_hhi(vols) == pytest.approx(0.1, rel=1e-4)

    def test_hhi_empty(self):
        assert compute_hhi({}) == 0.0


class TestGini:

    def test_perfect_equality(self):
        """All transactions equal → Gini = 0."""
        amounts = [10.0, 10.0, 10.0, 10.0]
        assert compute_gini(amounts) == pytest.approx(0.0, abs=1e-6)

    def test_perfect_inequality(self):
        """One huge tx, rest tiny → Gini close to 1."""
        amounts = [1000.0] + [0.001] * 99
        gini = compute_gini(amounts)
        assert gini > 0.9

    def test_typical_values(self):
        """Gini in [0, 1] for typical amounts."""
        amounts = [1.0, 2.0, 5.0, 10.0, 50.0]
        gini = compute_gini(amounts)
        assert 0.0 <= gini <= 1.0

    def test_empty(self):
        assert compute_gini([]) == 0.0

    def test_zeros_filtered(self):
        """Zero amounts are filtered out — shouldn't crash."""
        assert compute_gini([0.0, 0.0]) == 0.0


class TestTemporalAnomaly:

    def test_no_anomaly_uniform(self):
        """Uniform daily counts → no anomalous days."""
        freq = {f"2024-01-{d:02d}": 3 for d in range(1, 20)}
        result = compute_temporal_anomaly(freq)
        assert result["anomaly_score"] == 0.0
        assert result["anomalous_days"] == []

    def test_spike_detected(self):
        """One day with a massive spike → detected as anomalous."""
        freq = {f"2024-01-{d:02d}": 2 for d in range(1, 20)}
        freq["2024-01-20"] = 100   # huge spike
        result = compute_temporal_anomaly(freq)
        assert "2024-01-20" in result["anomalous_days"]
        assert result["anomaly_score"] > 0.0

    def test_single_day(self):
        """Only one day of data — can't compute std, no anomaly."""
        result = compute_temporal_anomaly({"2024-01-01": 5})
        assert result["anomaly_score"] == 0.0

    def test_empty(self):
        result = compute_temporal_anomaly({})
        assert result["anomaly_score"] == 0.0


class TestCompositeScore:

    def _make_aggregates(self, amounts, counterparty_vols, freq):
        return {
            "wallet":               "0xtest",
            "_amounts":             amounts,
            "counterparty_volumes": counterparty_vols,
            "frequency_by_day":     freq,
            "tx_count":             len(amounts),
            "total_volume":         sum(amounts),
        }

    def test_tc16_score_in_range(self):
        """TC-16: Composite score must be 0–100."""
        agg = self._make_aggregates(
            amounts=[1.0, 2.0, 3.0, 100.0],
            counterparty_vols={"addr1": 90.0, "addr2": 10.0, "addr3": 6.0},
            freq={"2024-01-01": 2, "2024-01-02": 1},
        )
        result = compute_risk_score(agg)
        assert 0 <= result["score"] <= 100
        assert result["tier"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_zero_data_returns_low(self):
        """No transactions → zero risk score, LOW tier."""
        agg = self._make_aggregates([], {}, {})
        result = compute_risk_score(agg)
        assert result["score"] == 0
        assert result["tier"] == "LOW"

    def test_high_concentration_scores_higher(self):
        """Wallet with all transactions to one counterparty should score higher than spread."""
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
        """Score → tier mapping is consistent."""
        # Force known scores by injecting mock aggregates
        # We test the _score_to_tier logic indirectly via full pipeline
        from app.processors.risk_engine import _score_to_tier
        assert _score_to_tier(0)   == "LOW"
        assert _score_to_tier(25)  == "LOW"
        assert _score_to_tier(26)  == "MEDIUM"
        assert _score_to_tier(50)  == "MEDIUM"
        assert _score_to_tier(51)  == "HIGH"
        assert _score_to_tier(75)  == "HIGH"
        assert _score_to_tier(76)  == "CRITICAL"
        assert _score_to_tier(100) == "CRITICAL"