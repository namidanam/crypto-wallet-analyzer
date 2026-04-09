from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime

class NormalizedTransaction(BaseModel):
    hash: str
    from_address: str
    to_address: Optional[str] = None
    value: float  # Absolute transaction value
    timestamp: datetime
    is_error: bool = False
    chain_id: str

class WalletHistory(BaseModel):
    wallet_address: str
    transactions: List[NormalizedTransaction]

class WalletAggregates(BaseModel):
    wallet_address: str
    total_tx_count: int
    total_volume: float
    unique_interacted_addresses: int
    avg_tx_value: float
    active_days: int
    risk_factors: List[str] = []

    # --- New behavioral features ---
    max_tx_value: float = 0.0          # Largest single transaction — whale detection
    min_tx_value: float = 0.0          # Smallest single transaction — dust attack detection
    std_tx_value: float = 0.0          # Std deviation of values — uniform = bot-like
    incoming_tx_count: int = 0         # Inbound transaction count
    outgoing_tx_count: int = 0         # Outbound transaction count
    total_incoming_volume: float = 0.0 # Total value received
    total_outgoing_volume: float = 0.0 # Total value sent
    net_flow: float = 0.0             # incoming − outgoing (negative = net sender)
    avg_time_between_tx: float = 0.0  # Mean seconds between consecutive txs
    max_single_address_volume: float = 0.0  # Largest volume with any single counterparty
    error_tx_count: int = 0           # Number of failed transactions
    error_tx_ratio: float = 0.0       # Failed / total ratio

class RiskScoreResponse(BaseModel):
    wallet_address: str
    heuristic_score: float
    ml_score: float
    overall_score: float
    risk_level: str
    flags: List[str]
    feature_contributions: Dict[str, float] = {}  # Per-prediction feature importance breakdown
