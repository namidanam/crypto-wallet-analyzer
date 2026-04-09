import os
import numpy as np
import joblib
from app.schemas.models import WalletAggregates, RiskScoreResponse

# Ordered list of feature names used by the ML model.
# Must match the order used during training (see train_model.py).
ML_FEATURE_NAMES = [
    "total_tx_count",
    "total_volume",
    "unique_interacted_addresses",
    "avg_tx_value",
    "active_days",
    "max_tx_value",
    "min_tx_value",
    "std_tx_value",
    "incoming_tx_count",
    "outgoing_tx_count",
    "total_incoming_volume",
    "total_outgoing_volume",
    "net_flow",
    "avg_time_between_tx",
    "max_single_address_volume",
    "error_tx_count",
    "error_tx_ratio",
]


class RiskEngine:
    def __init__(self):
        self.model_path = os.path.join(os.path.dirname(__file__), "ml_model.joblib")
        self.model = self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            return joblib.load(self.model_path)
        return None

    # ── Heuristic scoring ───────────────────────────────────────────
    def evaluate_heuristic(self, aggregates: WalletAggregates) -> float:
        score = 10.0

        # --- Existing rules (unchanged) ---
        if aggregates.total_tx_count > 1000:
            score += 30
            if "High transaction frequency" not in aggregates.risk_factors:
                aggregates.risk_factors.append("High transaction frequency")

        if aggregates.total_volume > 100000:
            score += 20
            if "High transaction volume" not in aggregates.risk_factors:
                aggregates.risk_factors.append("High transaction volume")

        if aggregates.unique_interacted_addresses > 500:
            score += 20

        if aggregates.active_days < 3 and aggregates.total_tx_count > 50:
            score += 30
            if "High activity in short duration (burner wallet format)" not in aggregates.risk_factors:
                aggregates.risk_factors.append("High activity in short duration (burner wallet format)")

        # --- New rule 1: Large single transaction (whale detection) ---
        if aggregates.max_tx_value > 50000:
            score += 15
            if "Unusually large single transaction" not in aggregates.risk_factors:
                aggregates.risk_factors.append("Unusually large single transaction")

        # --- New rule 2: High error rate ---
        if aggregates.error_tx_ratio > 0.15:
            score += 15
            if "High failed transaction rate" not in aggregates.risk_factors:
                aggregates.risk_factors.append("High failed transaction rate")

        # --- New rule 3: Mixer pattern (near-zero net flow + high volume) ---
        if (aggregates.total_tx_count > 100
                and aggregates.total_volume > 0
                and abs(aggregates.net_flow) < aggregates.total_volume * 0.05):
            score += 25
            if "Near-zero net flow (potential mixer)" not in aggregates.risk_factors:
                aggregates.risk_factors.append("Near-zero net flow (potential mixer)")

        # --- New rule 4: Bot detection (rapid-fire transactions) ---
        if aggregates.avg_time_between_tx < 30 and aggregates.total_tx_count > 200:
            score += 20
            if "Rapid-fire transactions (bot pattern)" not in aggregates.risk_factors:
                aggregates.risk_factors.append("Rapid-fire transactions (bot pattern)")

        # --- New rule 5: Address concentration ---
        if (aggregates.total_volume > 0
                and aggregates.max_single_address_volume > aggregates.total_volume * 0.8):
            score += 15
            if "High counterparty concentration" not in aggregates.risk_factors:
                aggregates.risk_factors.append("High counterparty concentration")

        # --- New rule 6: Suspiciously uniform transaction values ---
        if (aggregates.total_tx_count > 50
                and aggregates.avg_tx_value > 0
                and aggregates.std_tx_value < aggregates.avg_tx_value * 0.05):
            score += 10
            if "Suspiciously uniform transaction values" not in aggregates.risk_factors:
                aggregates.risk_factors.append("Suspiciously uniform transaction values")

        return min(score, 100.0)

    # ── ML scoring ──────────────────────────────────────────────────
    def _build_feature_vector(self, aggregates: WalletAggregates) -> list[float]:
        """Build the 17-feature vector matching training order."""
        return [
            float(aggregates.total_tx_count),
            aggregates.total_volume,
            float(aggregates.unique_interacted_addresses),
            aggregates.avg_tx_value,
            float(aggregates.active_days),
            aggregates.max_tx_value,
            aggregates.min_tx_value,
            aggregates.std_tx_value,
            float(aggregates.incoming_tx_count),
            float(aggregates.outgoing_tx_count),
            aggregates.total_incoming_volume,
            aggregates.total_outgoing_volume,
            aggregates.net_flow,
            aggregates.avg_time_between_tx,
            aggregates.max_single_address_volume,
            float(aggregates.error_tx_count),
            aggregates.error_tx_ratio,
        ]

    def _compute_feature_contributions(
        self, feature_vector: list[float]
    ) -> dict[str, float]:
        """
        Approximate per-prediction feature importance using global
        feature_importances_ weighted by the normalised input values.
        Returns a dict mapping feature name → contribution percentage.
        """
        if self.model is None or not hasattr(self.model, "feature_importances_"):
            return {}

        importances = self.model.feature_importances_  # shape (n_features,)
        fv = np.array(feature_vector, dtype=float)

        # Normalise feature values to [0, 1] keeping zeros intact
        fv_abs = np.abs(fv)
        fv_max = fv_abs.max()
        fv_norm = fv_abs / fv_max if fv_max > 0 else fv_abs

        raw = importances * fv_norm
        total = raw.sum()
        if total == 0:
            return {}

        contributions: dict[str, float] = {}
        for name, val in zip(ML_FEATURE_NAMES, raw / total * 100):
            contributions[name] = round(float(val), 2)

        return contributions

    def evaluate_ml(self, aggregates: WalletAggregates) -> tuple[float, dict[str, float]]:
        """
        Return (risk_score_0_to_100, feature_contributions_dict).
        Falls back to (25.0, {}) when no model is available.
        """
        features = self._build_feature_vector(aggregates)

        if not self.model:
            return 25.0, {}

        try:
            probs = self.model.predict_proba([features])
            score = float(probs[0][1]) * 100.0
            contributions = self._compute_feature_contributions(features)
            return score, contributions
        except Exception:
            return 50.0, {}

    # ── Combined scoring ────────────────────────────────────────────
    def calculate_risk(self, aggregates: WalletAggregates) -> RiskScoreResponse:
        h_score = self.evaluate_heuristic(aggregates)
        m_score, contributions = self.evaluate_ml(aggregates)

        overall = (h_score * 0.6) + (m_score * 0.4)

        if overall >= 80:
            level = "CRITICAL"
        elif overall >= 60:
            level = "HIGH"
        elif overall >= 30:
            level = "MEDIUM"
        else:
            level = "LOW"

        return RiskScoreResponse(
            wallet_address=aggregates.wallet_address,
            heuristic_score=round(h_score, 2),
            ml_score=round(m_score, 2),
            overall_score=round(overall, 2),
            risk_level=level,
            flags=aggregates.risk_factors,
            feature_contributions=contributions,
        )
