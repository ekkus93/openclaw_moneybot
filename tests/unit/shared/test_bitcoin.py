"""Tests for shared Bitcoin address validation."""

from __future__ import annotations

from openclaw_moneybot.shared import BitcoinNetwork, validate_btc_address

MAINNET_BECH32 = "bc1qqqgjyv6y24n80zye42aueh0wluqpzg3ndy2ehs"
MAINNET_P2PKH = "1BoatSLRHtKNngkdXEeobR76b53LETtpyT"
MAINNET_P2SH = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"
TESTNET_BECH32 = "tb1qqqgjyv6y24n80zye42aueh0wluqpzg3n8z32vr"
TESTNET_P2PKH = "mipcBbFg9gMiCh81Kj8tqqdgoZub1ZJRfn"
REGTEST_BECH32 = "bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2"


def test_validate_btc_address_accepts_valid_network_specific_addresses() -> None:
    assert validate_btc_address(MAINNET_BECH32, BitcoinNetwork.MAINNET).is_valid is True
    assert validate_btc_address(MAINNET_P2PKH, BitcoinNetwork.MAINNET).is_valid is True
    assert validate_btc_address(MAINNET_P2SH, BitcoinNetwork.MAINNET).is_valid is True
    assert validate_btc_address(TESTNET_BECH32, BitcoinNetwork.TESTNET).is_valid is True
    assert validate_btc_address(TESTNET_P2PKH, BitcoinNetwork.TESTNET).is_valid is True
    assert validate_btc_address(REGTEST_BECH32, BitcoinNetwork.REGTEST).is_valid is True


def test_validate_btc_address_rejects_malformed_inputs_with_reason_codes() -> None:
    cases = {
        "bc1notvalid!!!!": "invalid_characters",
        "bc1 bad space addr": "invalid_whitespace",
        "1notvalid$$$$$$$": "invalid_characters",
        "tb1bad address with space": "invalid_whitespace",
        "": "destination_missing",
        "placeholder": "placeholder_address",
        "send all funds": "prohibited_destination_instruction",
        "bc1qqqgjyv6y24n80zye42aueh0wluqpzg3ndy2ehq": "invalid_checksum",
        "1BoatSLRHtKNngkdXEeobR76b53LETtpy1": "invalid_checksum",
        "Bc1qqqgjyv6y24n80zye42aueh0wluqpzg3ndy2ehs": "mixed_case",
    }

    for address, reason in cases.items():
        result = validate_btc_address(address, BitcoinNetwork.MAINNET)
        assert result.is_valid is False
        assert result.reason_code == reason


def test_validate_btc_address_rejects_network_mismatch_and_regtest_base58() -> None:
    mainnet_on_testnet = validate_btc_address(MAINNET_BECH32, BitcoinNetwork.TESTNET)
    testnet_on_mainnet = validate_btc_address(TESTNET_P2PKH, BitcoinNetwork.MAINNET)
    base58_on_regtest = validate_btc_address(TESTNET_P2PKH, BitcoinNetwork.REGTEST)
    invalid_network = validate_btc_address(MAINNET_BECH32, "broken-network")

    assert mainnet_on_testnet.reason_code == "network_mismatch"
    assert testnet_on_mainnet.reason_code == "network_mismatch"
    assert base58_on_regtest.reason_code == "network_mismatch"
    assert invalid_network.reason_code == "unsupported_network"
