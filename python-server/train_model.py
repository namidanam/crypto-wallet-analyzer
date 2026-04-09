#!/usr/bin/env python3
"""
train_model.py — Train a GradientBoostingClassifier on the Kaggle
Ethereum Fraud Detection Dataset and save the model for the risk engine.

Usage:
    cd /home/anhad/Documents/crypto-wallet-analyzer/python-server
    ./venv/bin/python train_model.py

Outputs:
    - Classification report + feature importance ranking to stdout
    - Trained model saved to app/processors/ml_model.joblib
"""

import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

# ── Configuration ───────────────────────────────────────────────────
DATASET_PATH = os.path.join(os.path.dirname(__file__), "data", "ethereum_fraud_dataset.csv")
MODEL_OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "app", "processors", "ml_model.joblib")

# Feature names matching the order used in risk_engine.py
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


def load_and_map_dataset(path: str) -> tuple[pd.DataFrame, pd.Series]:
    """Load the Kaggle CSV and map its columns to our WalletAggregates features."""
    print(f"Loading dataset from {path} ...")
    df = pd.read_csv(path)
    print(f"  → {len(df)} accounts, {df.columns.size} raw columns")
    print(f"  → Label distribution: {dict(df['FLAG'].value_counts())}")

    # Strip whitespace from column names
    df.columns = df.columns.str.strip()

    # ── Column mapping ──────────────────────────────────────────────
    mapped = pd.DataFrame()

    # total_tx_count = total transactions (including tnx to create contract)
    mapped["total_tx_count"] = df["total transactions (including tnx to create contract"]

    # total_volume = total ether sent + total ether received
    mapped["total_volume"] = df["total Ether sent"] + df["total ether received"]

    # unique_interacted_addresses = Unique Sent To + Unique Received From
    mapped["unique_interacted_addresses"] = (
        df["Unique Sent To Addresses"] + df["Unique Received From Addresses"]
    )

    # avg_tx_value = total_volume / total_tx_count (avoid div-by-zero)
    mapped["avg_tx_value"] = np.where(
        mapped["total_tx_count"] > 0,
        mapped["total_volume"] / mapped["total_tx_count"],
        0.0,
    )

    # active_days = Time Diff between first and last (Mins) / 1440
    mapped["active_days"] = np.clip(
        (df["Time Diff between first and last (Mins)"] / 1440.0).round().astype(int),
        a_min=0,
        a_max=None,
    )

    # max_tx_value = max(max val sent, max value received)
    mapped["max_tx_value"] = np.maximum(
        df["max val sent"], df["max value received"]
    )

    # min_tx_value = min of non-zero mins; if both zero, keep zero
    min_sent = df["min val sent"]
    min_recv = df["min value received"]
    mapped["min_tx_value"] = np.where(
        (min_sent > 0) & (min_recv > 0),
        np.minimum(min_sent, min_recv),
        np.maximum(min_sent, min_recv),  # take whichever is non-zero
    )

    # std_tx_value — approximate from avg & volume spread
    # The dataset doesn't have an explicit std, so we derive it from the
    # spread between max and avg values (a reasonable proxy).
    avg_sent = df["avg val sent"]
    avg_recv = df["avg val received"]
    max_sent = df["max val sent"]
    max_recv = df["max value received"]
    combined_avg = (avg_sent + avg_recv) / 2
    combined_max = np.maximum(max_sent, max_recv)
    mapped["std_tx_value"] = np.abs(combined_max - combined_avg)

    # incoming_tx_count = Received Tnx
    mapped["incoming_tx_count"] = df["Received Tnx"]

    # outgoing_tx_count = Sent tnx
    mapped["outgoing_tx_count"] = df["Sent tnx"]

    # total_incoming_volume = total ether received
    mapped["total_incoming_volume"] = df["total ether received"]

    # total_outgoing_volume = total Ether sent
    mapped["total_outgoing_volume"] = df["total Ether sent"]

    # net_flow = received − sent
    mapped["net_flow"] = df["total ether received"] - df["total Ether sent"]

    # avg_time_between_tx — average of sent & received avg min, converted to seconds
    avg_min_sent = df["Avg min between sent tnx"].fillna(0)
    avg_min_recv = df["Avg min between received tnx"].fillna(0)
    mapped["avg_time_between_tx"] = ((avg_min_sent + avg_min_recv) / 2) * 60  # → seconds

    # max_single_address_volume — not directly in dataset, proxy with max val sent
    mapped["max_single_address_volume"] = df["max val sent"]

    # error_tx_count — not in dataset, default to 0
    mapped["error_tx_count"] = 0

    # error_tx_ratio — not in dataset, default to 0
    mapped["error_tx_ratio"] = 0.0

    # Replace NaN / inf with 0
    mapped = mapped.replace([np.inf, -np.inf], 0.0).fillna(0.0)

    labels = df["FLAG"]
    return mapped[ML_FEATURE_NAMES], labels


def train(X: pd.DataFrame, y: pd.Series) -> GradientBoostingClassifier:
    """Train a GradientBoostingClassifier with stratified split."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Compute sample weights for class imbalance
    class_counts = y_train.value_counts()
    total = len(y_train)
    weight_map = {cls: total / (len(class_counts) * count) for cls, count in class_counts.items()}
    sample_weights = y_train.map(weight_map)

    print("\n── Training GradientBoostingClassifier ──")
    print(f"  n_estimators=200, max_depth=4, learning_rate=0.1")
    print(f"  Training samples: {len(X_train)}, Test samples: {len(X_test)}")
    print(f"  Class weights: {weight_map}")

    model = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
        subsample=0.8,
        min_samples_leaf=10,
    )
    model.fit(X_train, y_train, sample_weight=sample_weights)

    # ── Evaluation ──────────────────────────────────────────────────
    y_pred = model.predict(X_test)
    print("\n── Classification Report ──")
    print(classification_report(y_test, y_pred, target_names=["Legit (0)", "Fraud (1)"]))

    # ── Feature Importance ──────────────────────────────────────────
    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1]
    print("── Feature Importance Ranking ──")
    for rank, idx in enumerate(indices, 1):
        print(f"  {rank:2d}. {ML_FEATURE_NAMES[idx]:<35s} {importances[idx]:.4f}")

    return model


def main():
    if not os.path.exists(DATASET_PATH):
        print(f"ERROR: Dataset not found at {DATASET_PATH}")
        print("Download from: https://github.com/Vagif12/Ethereum-Fraud-Detection/blob/master/datasets/final_combined_dataset.csv")
        sys.exit(1)

    X, y = load_and_map_dataset(DATASET_PATH)
    model = train(X, y)

    print(f"\n── Saving model to {MODEL_OUTPUT_PATH} ──")
    os.makedirs(os.path.dirname(MODEL_OUTPUT_PATH), exist_ok=True)
    joblib.dump(model, MODEL_OUTPUT_PATH)
    print("Done ✓")


if __name__ == "__main__":
    main()
