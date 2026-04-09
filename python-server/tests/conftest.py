import pytest


@pytest.fixture
def mock_history():
    """Basic 2-tx wallet history for simple tests."""
    return {
        "wallet_address": "0x123",
        "transactions": [
            {
                "hash": "tx1",
                "from_address": "0x123",
                "to_address": "0xabc",
                "value": 1500.50,
                "timestamp": "2023-10-01T10:00:00Z",
                "chain_id": "1",
            },
            {
                "hash": "tx2",
                "from_address": "0xdef",
                "to_address": "0x123",
                "value": 500.00,
                "timestamp": "2023-10-02T12:00:00Z",
                "chain_id": "1",
            },
        ],
    }


@pytest.fixture
def mock_history_with_errors():
    """Wallet history containing error transactions and varied timing."""
    return {
        "wallet_address": "0x456",
        "transactions": [
            {
                "hash": "tx_e1",
                "from_address": "0x456",
                "to_address": "0xaaa",
                "value": 100.0,
                "timestamp": "2023-11-01T08:00:00Z",
                "is_error": True,
                "chain_id": "1",
            },
            {
                "hash": "tx_e2",
                "from_address": "0x456",
                "to_address": "0xbbb",
                "value": 200.0,
                "timestamp": "2023-11-01T08:00:10Z",
                "is_error": False,
                "chain_id": "1",
            },
            {
                "hash": "tx_e3",
                "from_address": "0xccc",
                "to_address": "0x456",
                "value": 300.0,
                "timestamp": "2023-11-01T08:00:20Z",
                "is_error": False,
                "chain_id": "1",
            },
            {
                "hash": "tx_e4",
                "from_address": "0x456",
                "to_address": "0xaaa",
                "value": 150.0,
                "timestamp": "2023-11-01T08:00:30Z",
                "is_error": True,
                "chain_id": "1",
            },
            {
                "hash": "tx_e5",
                "from_address": "0x456",
                "to_address": "0xddd",
                "value": 250.0,
                "timestamp": "2023-11-01T08:00:40Z",
                "is_error": False,
                "chain_id": "1",
            },
        ],
    }
