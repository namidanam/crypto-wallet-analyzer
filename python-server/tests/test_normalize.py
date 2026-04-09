"""
test_normalize.py
─────────────────
Unit tests for normalize.py

Covers:
  TC-10  ETH native transaction normalization
  TC-11  ETH ERC-20 token transfer normalization
  TC-12  Wei → ETH amount passthrough (already converted upstream by goldrush.service.js)
  TC-13  BTC UTXO multi-input aggregation
  TC-14  BTC fallback (flat Tatum shape with no vin/vout)
  TC-XX  Doge and LTC normalization
  TC-XX  Unsupported chain raises ValueError
"""

import pytest
from app.processors.normalize import (
    normalize_evm,
    normalize_btc,
    normalize_doge,
    normalize_ltc,
    normalize_transaction,
    normalize_transactions,
)

WALLET_ETH  = "0xabc123def456abc123def456abc123def456abc1"
WALLET_BTC  = "1A2B3C4D5E6F7G8H9I0JKL"
WALLET_DOGE = "DRmDMBsXNvxgqMFTuQBEBvRvXj7WPM1234"
WALLET_LTC  = "LTc9BKtBk3f1234567890abcdef1234567"


# ─────────────────────────────────────────────────────────
# ETH tests
# ─────────────────────────────────────────────────────────

class TestNormalizeEvm:

    def test_tc10_native_eth_out(self):
        """TC-10: ETH native send — from wallet → OUT direction."""
        tx = {
            "txHash":    "0xaaa",
            "chain":     "eth-mainnet",
            "timestamp": 1700000000000,
            "from":      WALLET_ETH,
            "to":        "0xrecipient",
            "amount":    1.5,
            "assetType": "NATIVE",
        }
        result = normalize_evm(tx, WALLET_ETH)

        assert len(result) == 1
        r = result[0]
        assert r["direction"]    == "OUT"
        assert r["from_address"] == WALLET_ETH
        assert r["to_address"]   == "0xrecipient"
        assert r["amount"]       == 1.5
        assert r["token"]        == "NATIVE"
        assert r["chain"]        == "eth-mainnet"
        assert r["tx_hash"]      == "0xaaa"

    def test_tc10_native_eth_in(self):
        """TC-10: ETH native receive → IN direction."""
        tx = {
            "txHash":    "0xbbb",
            "chain":     "eth-mainnet",
            "timestamp": 1700000001000,
            "from":      "0xsender",
            "to":        WALLET_ETH,
            "amount":    0.5,
            "assetType": "NATIVE",
        }
        result = normalize_evm(tx, WALLET_ETH)
        assert result[0]["direction"] == "IN"

    def test_tc11_erc20_token_transfer(self):
        """TC-11: ERC-20 tokenTransfer list is expanded into separate records."""
        tx = {
            "txHash":    "0xccc",
            "chain":     "eth-mainnet",
            "timestamp": 1700000002000,
            "assetType": "ERC20",
            "nativeValue": "0",
            "tokenTransfers": [
                {
                    "from":          WALLET_ETH,
                    "to":            "0xrecipient",
                    "amount":        250.0,
                    "tokenSymbol":   "USDC",
                    "tokenAddress":  "0xusdc",
                }
            ],
        }
        result = normalize_evm(tx, WALLET_ETH)

        assert len(result) == 1
        r = result[0]
        assert r["token"]     == "USDC"
        assert r["amount"]    == 250.0
        assert r["direction"] == "OUT"

    def test_tc12_amount_passthrough(self):
        """TC-12: Amount already converted upstream — normalize_evm passes it through as-is."""
        tx = {
            "txHash":    "0xddd",
            "chain":     "eth-mainnet",
            "timestamp": 1700000003000,
            "from":      WALLET_ETH,
            "to":        "0xother",
            "amount":    0.001,   # already ETH (not Wei)
            "assetType": "NATIVE",
        }
        result = normalize_evm(tx, WALLET_ETH)
        assert result[0]["amount"] == pytest.approx(0.001)


# ─────────────────────────────────────────────────────────
# BTC UTXO tests
# ─────────────────────────────────────────────────────────

class TestNormalizeBtc:

    def _make_utxo_tx(self, vin_entries, vout_entries, tx_hash="txabc"):
        return {
            "txHash":    tx_hash,
            "chain":     "btc-mainnet",
            "timestamp": 1700000000000,
            "vin":       vin_entries,
            "vout":      vout_entries,
        }

    def test_tc13_multi_input_aggregation(self):
        """TC-13: Multiple vin inputs from our wallet are summed into one OUT record."""
        tx = self._make_utxo_tx(
            vin_entries=[
                {"addresses": [WALLET_BTC], "value": "30000"},   # 0.0003 BTC
                {"addresses": [WALLET_BTC], "value": "20000"},   # 0.0002 BTC
                {"addresses": ["1OTHER"],   "value": "10000"},   # not our wallet
            ],
            vout_entries=[
                {"addresses": ["1RECIPIENT"], "value": "45000"},
                {"addresses": [WALLET_BTC],   "value": "4000"},  # change back
            ],
        )
        result = normalize_btc(tx, WALLET_BTC)

        # Should have an OUT (sent) and IN (change) record
        directions = {r["direction"] for r in result}
        assert "OUT" in directions
        assert "IN"  in directions

        out_record = next(r for r in result if r["direction"] == "OUT")
        # Total inputs from our wallet: 30000 + 20000 = 50000 satoshi = 0.0005 BTC
        assert out_record["amount"] == pytest.approx(0.0005, rel=1e-6)
        assert out_record["token"]  == "BTC"

        in_record = next(r for r in result if r["direction"] == "IN")
        # Change output: 4000 satoshi = 0.00004 BTC
        assert in_record["amount"] == pytest.approx(0.00004, rel=1e-6)

    def test_tc14_flat_tatum_fallback(self):
        """TC-14: Tatum returns a flat shape (no vin/vout). Should still normalize."""
        tx = {
            "txHash":    "txflat",
            "chain":     "btc-mainnet",
            "timestamp": 1700000000000,
            "from":      WALLET_BTC,
            "to":        "1RECIPIENT",
            "value":     "100000",   # 0.001 BTC in satoshis
        }
        result = normalize_btc(tx, WALLET_BTC)

        assert len(result) == 1
        r = result[0]
        assert r["direction"] == "OUT"
        assert r["amount"]    == pytest.approx(0.001, rel=1e-6)
        assert r["token"]     == "BTC"

    def test_receive_only(self):
        """Wallet is only a receiver (no vin inputs from wallet)."""
        tx = self._make_utxo_tx(
            vin_entries=[
                {"addresses": ["1SENDER"], "value": "50000"},
            ],
            vout_entries=[
                {"addresses": [WALLET_BTC], "value": "49000"},
            ],
        )
        result = normalize_btc(tx, WALLET_BTC)

        assert len(result) == 1
        assert result[0]["direction"] == "IN"
        assert result[0]["amount"] == pytest.approx(0.00049, rel=1e-6)

    def test_timestamp_seconds_converted_to_ms(self):
        """Tatum blocktime is in seconds — must be stored as ms."""
        tx = {
            "txHash":    "txts",
            "chain":     "btc-mainnet",
            "blocktime": 1700000000,     # seconds
            "from":      WALLET_BTC,
            "to":        "1REC",
            "value":     "1000",
        }
        result = normalize_btc(tx, WALLET_BTC)
        # Timestamp must be in milliseconds (>1e12)
        assert result[0]["timestamp"] > 1_000_000_000_000


# ─────────────────────────────────────────────────────────
# Doge + LTC tests
# ─────────────────────────────────────────────────────────

class TestNormalizeDogeLtc:

    def test_doge_token_symbol(self):
        tx = {
            "txHash":    "txdoge",
            "chain":     "doge-mainnet",
            "timestamp": 1700000000000,
            "from":      WALLET_DOGE,
            "to":        "DRECIPIENT",
            "value":     "50000000",   # 0.5 DOGE in satoshis
        }
        result = normalize_doge(tx, WALLET_DOGE)
        assert result[0]["token"]  == "DOGE"
        assert result[0]["chain"]  == "doge-mainnet"
        assert result[0]["amount"] == pytest.approx(0.5, rel=1e-6)

    def test_ltc_token_symbol(self):
        tx = {
            "txHash":    "txltc",
            "chain":     "ltc-mainnet",
            "timestamp": 1700000000000,
            "from":      WALLET_LTC,
            "to":        "LRECIPIENT",
            "value":     "100000000",  # 1.0 LTC
        }
        result = normalize_ltc(tx, WALLET_LTC)
        assert result[0]["token"]  == "LTC"
        assert result[0]["amount"] == pytest.approx(1.0, rel=1e-6)


# ─────────────────────────────────────────────────────────
# Router tests
# ─────────────────────────────────────────────────────────

class TestNormalizeRouter:

    def test_routes_eth(self):
        tx = {
            "txHash": "0x1", "chain": "eth-mainnet", "timestamp": 1700000000000,
            "from": WALLET_ETH, "to": "0xother", "amount": 1.0, "assetType": "NATIVE",
        }
        result = normalize_transaction(tx, WALLET_ETH)
        assert result[0]["token"] == "NATIVE"

    def test_routes_btc(self):
        tx = {
            "txHash": "txbtc", "chain": "btc-mainnet", "timestamp": 1700000000000,
            "from": WALLET_BTC, "to": "1REC", "value": "10000",
        }
        result = normalize_transaction(tx, WALLET_BTC)
        assert result[0]["token"] == "BTC"

    def test_routes_doge(self):
        tx = {
            "txHash": "txd", "chain": "doge-mainnet", "timestamp": 1700000000000,
            "from": WALLET_DOGE, "to": "DREC", "value": "10000",
        }
        result = normalize_transaction(tx, WALLET_DOGE)
        assert result[0]["token"] == "DOGE"

    def test_unsupported_chain_raises(self):
        tx = {"txHash": "x", "chain": "solana-mainnet", "timestamp": 0}
        with pytest.raises(ValueError, match="Unsupported chain"):
            normalize_transaction(tx, "someaddr")

    def test_batch_skips_bad_tx(self):
        """normalize_transactions should skip bad txs and continue."""
        txs = [
            {"txHash": "0x1", "chain": "eth-mainnet", "timestamp": 1700000000000,
             "from": WALLET_ETH, "to": "0xother", "amount": 1.0, "assetType": "NATIVE"},
            {"txHash": "bad", "chain": "solana-mainnet"},   # will be skipped
        ]
        result = normalize_transactions(txs, WALLET_ETH)
        assert len(result) == 1
        assert result[0]["tx_hash"] == "0x1"