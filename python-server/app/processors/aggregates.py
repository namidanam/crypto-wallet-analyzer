from app.schemas.models import WalletHistory, WalletAggregates
import pandas as pd
import numpy as np


def compute_aggregates(history: WalletHistory) -> WalletAggregates:
    if not history.transactions:
        return WalletAggregates(
            wallet_address=history.wallet_address,
            total_tx_count=0,
            total_volume=0.0,
            unique_interacted_addresses=0,
            avg_tx_value=0.0,
            active_days=0,
            risk_factors=[]
        )

    df = pd.DataFrame([tx.model_dump() for tx in history.transactions])

    # ── Core aggregates (existing) ──────────────────────────────────
    total_tx = len(df)
    total_vol = float(df["value"].sum())

    unique_addrs = set(df["from_address"]).union(set(df["to_address"].dropna()))
    if history.wallet_address in unique_addrs:
        unique_addrs.remove(history.wallet_address)

    avg_val = total_vol / total_tx if total_tx > 0 else 0.0

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    active_days = int(df["timestamp"].dt.date.nunique())

    # ── Value statistics ────────────────────────────────────────────
    max_tx_value = float(df["value"].max())
    min_tx_value = float(df["value"].min())
    std_tx_value = float(df["value"].std()) if total_tx > 1 else 0.0

    # ── Directional flow analysis ───────────────────────────────────
    wallet = history.wallet_address.lower()
    outgoing = df[df["from_address"].str.lower() == wallet]
    incoming = df[df["to_address"].fillna("").str.lower() == wallet]

    outgoing_tx_count = len(outgoing)
    incoming_tx_count = len(incoming)
    total_outgoing_volume = float(outgoing["value"].sum())
    total_incoming_volume = float(incoming["value"].sum())
    net_flow = total_incoming_volume - total_outgoing_volume

    # ── Timing analysis ─────────────────────────────────────────────
    if total_tx > 1:
        sorted_ts = df["timestamp"].sort_values()
        diffs = sorted_ts.diff().dropna().dt.total_seconds()
        avg_time_between_tx = float(diffs.mean()) if len(diffs) > 0 else 0.0
    else:
        avg_time_between_tx = 0.0

    # ── Counterparty concentration ──────────────────────────────────
    counterparty_volumes: dict[str, float] = {}
    for _, row in df.iterrows():
        if row["from_address"].lower() == wallet:
            addr = str(row.get("to_address", "")).lower()
        else:
            addr = row["from_address"].lower()
        if addr:
            counterparty_volumes[addr] = counterparty_volumes.get(addr, 0.0) + float(row["value"])

    max_single_address_volume = float(max(counterparty_volumes.values())) if counterparty_volumes else 0.0

    # ── Error analysis ──────────────────────────────────────────────
    error_tx_count = int(df["is_error"].sum())
    error_tx_ratio = error_tx_count / total_tx if total_tx > 0 else 0.0

    return WalletAggregates(
        wallet_address=history.wallet_address,
        total_tx_count=total_tx,
        total_volume=total_vol,
        unique_interacted_addresses=len(unique_addrs),
        avg_tx_value=float(avg_val),
        active_days=active_days,
        risk_factors=[],
        max_tx_value=max_tx_value,
        min_tx_value=min_tx_value,
        std_tx_value=std_tx_value,
        incoming_tx_count=incoming_tx_count,
        outgoing_tx_count=outgoing_tx_count,
        total_incoming_volume=total_incoming_volume,
        total_outgoing_volume=total_outgoing_volume,
        net_flow=net_flow,
        avg_time_between_tx=avg_time_between_tx,
        max_single_address_volume=max_single_address_volume,
        error_tx_count=error_tx_count,
        error_tx_ratio=error_tx_ratio,
    )
