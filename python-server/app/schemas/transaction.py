from pydantic import BaseModel
from typing import Literal, Optional

""" 
    Get's inheritance from the BaseModel class, which keeps checking on the 
    type annotation of the class, and the messages described by the interpreter
    - Raises a ValueError in case of a type mismatch!
"""
class NormalizedTransaction(BaseModel):
    tx_hash: str
    wallet: str
    from_address: str
    to_address: str
    amount: float
    token: str
    timestamp: int
    chain: str
    # Literal - specifies if it is either one out of the only suggested strings!
    direction: Literal["IN", "OUT"]


    # EVM - specific fields allowed to be empty for Non - EVM chains(Bitcoin, Dogecoin)
    assetType: Optional[str] = None
    tokenAddress: Optional[str] = None
    nativeValue: Optional[float] = None
