"""
End-to-end integration tests for the Enhanced Risk Engine.

Tests the full pipeline: HTTP request → aggregates computation → heuristic scoring
→ ML inference → response with feature_contributions.
"""
import datetime

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ── Helpers ─────────────────────────────────────────────────────────

def _make_tx(hash, from_addr, to_addr, value, timestamp_str, is_error=False):
    return {
        "hash": hash,
        "from_address": from_addr,
        "to_address": to_addr,
        "value": value,
        "timestamp": timestamp_str,
        "is_error": is_error,
        "chain_id": "1",
    }


def _make_rapid_history(wallet, n_txs=300, interval_sec=10):
    """Generate a rapid-fire bot-like wallet history."""
    base = datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    txs = []
    for i in range(n_txs):
        t = (base + datetime.timedelta(seconds=interval_sec * i)).isoformat()
        txs.append(_make_tx(
            hash=f"tx_{i}",
            from_addr=wallet if i % 2 == 0 else f"0xcounter_{i}",
            to_addr=f"0xcounter_{i}" if i % 2 == 0 else wallet,
            value=150.0,
            timestamp_str=t,
            is_error=(i % 5 == 0),  # 20% error rate
        ))
    return {"wallet_address": wallet, "transactions": txs}


# ── Tests ───────────────────────────────────────────────────────────

class TestAggregatesEndpoint:
    """Test /aggregates returns all 17 features correctly."""

    def test_aggregates_new_fields_present(self):
        payload = {
            "wallet_address": "0xIntTest",
            "transactions": [
                _make_tx("t1", "0xIntTest", "0xA", 1000.0, "2024-01-01T10:00:00Z"),
                _make_tx("t2", "0xB", "0xIntTest", 500.0, "2024-01-01T11:00:00Z"),
                _make_tx("t3", "0xIntTest", "0xA", 200.0, "2024-01-01T12:00:00Z", is_error=True),
            ],
        }
        resp = client.post("/aggregates", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        # Original fields
        assert data["total_tx_count"] == 3
        assert data["total_volume"] == 1700.0
        assert data["active_days"] == 1

        # New fields must exist
        for field in [
            "max_tx_value", "min_tx_value", "std_tx_value",
            "incoming_tx_count", "outgoing_tx_count",
            "total_incoming_volume", "total_outgoing_volume", "net_flow",
            "avg_time_between_tx", "max_single_address_volume",
            "error_tx_count", "error_tx_ratio",
        ]:
            assert field in data, f"Missing field: {field}"

        # Spot-check values
        assert data["max_tx_value"] == 1000.0
        assert data["min_tx_value"] == 200.0
        assert data["incoming_tx_count"] == 1
        assert data["outgoing_tx_count"] == 2
        assert data["total_incoming_volume"] == 500.0
        assert data["total_outgoing_volume"] == 1200.0
        assert data["net_flow"] == 500.0 - 1200.0  # -700.0
        assert data["error_tx_count"] == 1
        assert abs(data["error_tx_ratio"] - 1 / 3) < 0.01

    def test_aggregates_empty_wallet(self):
        resp = client.post("/aggregates", json={
            "wallet_address": "0xEmpty",
            "transactions": [],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tx_count"] == 0
        assert data["error_tx_count"] == 0


class TestRiskScoreEndpoint:
    """Test /risk-score returns proper scoring with ML + heuristics."""

    def test_low_risk_wallet(self):
        payload = {
            "wallet_address": "0xGoodGuy",
            "transactions": [
                _make_tx("t1", "0xGoodGuy", "0xA", 50.0, "2024-01-01T10:00:00Z"),
                _make_tx("t2", "0xB", "0xGoodGuy", 30.0, "2024-01-15T10:00:00Z"),
                _make_tx("t3", "0xGoodGuy", "0xC", 20.0, "2024-02-01T10:00:00Z"),
            ],
        }
        resp = client.post("/risk-score", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["risk_level"] in ("LOW", "MEDIUM")
        assert data["heuristic_score"] == 10.0  # base only, no rules triggered
        assert isinstance(data["feature_contributions"], dict)

    def test_high_risk_bot_wallet(self):
        """300 rapid-fire txs with 20% error rate should trigger multiple flags."""
        payload = _make_rapid_history("0xBotWallet", n_txs=300, interval_sec=10)
        resp = client.post("/risk-score", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["heuristic_score"] > 10.0
        assert "High failed transaction rate" in data["flags"]
        assert "Rapid-fire transactions (bot pattern)" in data["flags"]
        assert data["risk_level"] in ("MEDIUM", "HIGH", "CRITICAL")

    def test_ml_score_not_constant_25(self):
        """ML score should not be the old fallback 25.0 — the trained model is loaded."""
        payload = _make_rapid_history("0xMLTest", n_txs=50, interval_sec=60)
        resp = client.post("/risk-score", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        # With a real trained model, the score should differ from the 25.0 constant
        assert data["ml_score"] != 25.0, "ML model appears to still be using the 25.0 fallback"

    def test_feature_contributions_populated(self):
        """With a trained model, feature_contributions should have entries."""
        payload = _make_rapid_history("0xContrib", n_txs=50, interval_sec=60)
        resp = client.post("/risk-score", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        contribs = data["feature_contributions"]
        assert len(contribs) > 0, "feature_contributions is empty"
        # Contributions should sum to ~100%
        total = sum(contribs.values())
        assert 99.0 <= total <= 101.0, f"Contributions sum to {total}, expected ~100"

    def test_whale_transaction_flag(self):
        """A single tx > 50,000 should trigger the whale flag."""
        payload = {
            "wallet_address": "0xWhale",
            "transactions": [
                _make_tx("t1", "0xWhale", "0xA", 75000.0, "2024-01-01T10:00:00Z"),
                _make_tx("t2", "0xB", "0xWhale", 100.0, "2024-02-01T10:00:00Z"),
            ],
        }
        resp = client.post("/risk-score", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "Unusually large single transaction" in data["flags"]

    def test_response_schema_complete(self):
        """Verify the full response schema has all expected keys."""
        payload = {
            "wallet_address": "0xSchema",
            "transactions": [
                _make_tx("t1", "0xSchema", "0xA", 100.0, "2024-01-01T10:00:00Z"),
            ],
        }
        resp = client.post("/risk-score", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        expected_keys = {
            "wallet_address", "heuristic_score", "ml_score",
            "overall_score", "risk_level", "flags", "feature_contributions",
        }
        assert expected_keys == set(data.keys()), f"Missing keys: {expected_keys - set(data.keys())}"
