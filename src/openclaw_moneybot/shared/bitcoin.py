"""Deterministic Bitcoin address validation helpers."""

from __future__ import annotations

import hashlib

from pydantic import Field

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.types import BitcoinNetwork

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
BECH32_CHARSET_MAP = {char: index for index, char in enumerate(BECH32_CHARSET)}
BECH32_CONST = 1
BECH32M_CONST = 0x2BC830A3
PLACEHOLDER_DESTINATIONS = frozenset({"example", "placeholder", "todo", "changeme", "test"})
PROHIBITED_SEND_TERMS = frozenset({"send_all", "send all", "sweep", "max", "all funds"})
MAINNET_VERSION_BYTES = {0: "p2pkh", 5: "p2sh"}
TESTLIKE_VERSION_BYTES = {111: "p2pkh", 196: "p2sh"}
NETWORK_HRPS = {
    BitcoinNetwork.MAINNET: "bc",
    BitcoinNetwork.TESTNET: "tb",
    BitcoinNetwork.REGTEST: "bcrt",
    BitcoinNetwork.SIGNET: "tb",
}
BECH32_NETWORKS = {
    "bc": BitcoinNetwork.MAINNET,
    "tb": BitcoinNetwork.TESTNET,
    "bcrt": BitcoinNetwork.REGTEST,
}


class AddressValidationResult(MoneyBotModel):
    """Normalized BTC address validation result."""

    is_valid: bool
    network: BitcoinNetwork | None = None
    address_type: str | None = None
    reason_code: str | None = None
    normalized_address: str | None = None
    details: dict[str, str] = Field(default_factory=dict)


def normalize_btc_address_for_comparison(address: str) -> str:
    """Normalize an address for exact-match comparisons."""
    normalized = address.strip()
    lowered = normalized.lower()
    if lowered.startswith(("bc1", "tb1", "bcrt1")):
        return lowered
    return normalized


def validate_btc_address(
    address: str,
    network: BitcoinNetwork | str,
) -> AddressValidationResult:
    """Validate one BTC destination for the configured network."""
    try:
        configured_network = BitcoinNetwork(str(network))
    except ValueError:
        return AddressValidationResult(is_valid=False, reason_code="unsupported_network")

    normalized = address.strip()
    lowered = normalized.lower()
    if not normalized:
        return AddressValidationResult(is_valid=False, reason_code="destination_missing")
    if any(term in lowered for term in PROHIBITED_SEND_TERMS):
        return AddressValidationResult(
            is_valid=False,
            reason_code="prohibited_destination_instruction",
        )
    if normalized != address or any(char.isspace() for char in normalized):
        return AddressValidationResult(is_valid=False, reason_code="invalid_whitespace")
    if any(token in lowered for token in PLACEHOLDER_DESTINATIONS):
        return AddressValidationResult(is_valid=False, reason_code="placeholder_address")

    if any(lowered.startswith(f"{hrp}1") for hrp in BECH32_NETWORKS):
        return _validate_bech32_address(normalized, configured_network)
    return _validate_base58_address(normalized, configured_network)


def _validate_base58_address(
    address: str,
    configured_network: BitcoinNetwork,
) -> AddressValidationResult:
    if configured_network is BitcoinNetwork.REGTEST:
        return AddressValidationResult(
            is_valid=False,
            reason_code="network_mismatch",
            network=BitcoinNetwork.TESTNET,
        )
    if any(char not in BASE58_ALPHABET for char in address):
        return AddressValidationResult(is_valid=False, reason_code="invalid_characters")

    decoded = _base58_decode(address)
    if len(decoded) != 25:
        return AddressValidationResult(is_valid=False, reason_code="invalid_length")
    payload = decoded[:-4]
    checksum = decoded[-4:]
    expected_checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    if checksum != expected_checksum:
        return AddressValidationResult(is_valid=False, reason_code="invalid_checksum")

    version = payload[0]
    if version in MAINNET_VERSION_BYTES:
        detected_network = BitcoinNetwork.MAINNET
        address_type = MAINNET_VERSION_BYTES[version]
    elif version in TESTLIKE_VERSION_BYTES:
        detected_network = BitcoinNetwork.TESTNET
        address_type = TESTLIKE_VERSION_BYTES[version]
    else:
        return AddressValidationResult(is_valid=False, reason_code="unsupported_network")

    if not _network_matches(configured_network, detected_network):
        return AddressValidationResult(
            is_valid=False,
            network=detected_network,
            address_type=address_type,
            reason_code="network_mismatch",
        )
    return AddressValidationResult(
        is_valid=True,
        network=configured_network,
        address_type=address_type,
        normalized_address=address,
    )


def _validate_bech32_address(
    address: str,
    configured_network: BitcoinNetwork,
) -> AddressValidationResult:
    if any(ord(char) < 33 or ord(char) > 126 for char in address):
        return AddressValidationResult(is_valid=False, reason_code="invalid_characters")
    if address.lower() != address and address.upper() != address:
        return AddressValidationResult(is_valid=False, reason_code="mixed_case")

    normalized = address.lower()
    separator = normalized.rfind("1")
    if separator <= 0 or separator + 7 > len(normalized):
        return AddressValidationResult(is_valid=False, reason_code="invalid_length")
    hrp = normalized[:separator]
    if hrp not in BECH32_NETWORKS:
        return AddressValidationResult(is_valid=False, reason_code="unsupported_network")
    detected_network = BECH32_NETWORKS[hrp]
    if not _network_matches(configured_network, detected_network):
        return AddressValidationResult(
            is_valid=False,
            network=detected_network,
            reason_code="network_mismatch",
        )

    try:
        data = [BECH32_CHARSET_MAP[char] for char in normalized[separator + 1 :]]
    except KeyError:
        return AddressValidationResult(is_valid=False, reason_code="invalid_characters")
    if len(data) < 7:
        return AddressValidationResult(is_valid=False, reason_code="invalid_length")

    encoding = _bech32_encoding(hrp, data)
    if encoding is None:
        return AddressValidationResult(is_valid=False, reason_code="invalid_checksum")
    witness_version = data[0]
    if witness_version > 16:
        return AddressValidationResult(is_valid=False, reason_code="invalid_witness_version")
    if witness_version == 0 and encoding != "bech32":
        return AddressValidationResult(is_valid=False, reason_code="invalid_checksum")
    if witness_version != 0 and encoding != "bech32m":
        return AddressValidationResult(is_valid=False, reason_code="invalid_checksum")

    witness_program = _convertbits(data[1:-6], from_bits=5, to_bits=8, pad=False)
    if witness_program is None:
        return AddressValidationResult(is_valid=False, reason_code="invalid_witness_program")
    if not 2 <= len(witness_program) <= 40:
        return AddressValidationResult(is_valid=False, reason_code="invalid_witness_program")
    if witness_version == 0 and len(witness_program) not in {20, 32}:
        return AddressValidationResult(is_valid=False, reason_code="invalid_witness_program")

    address_type = (
        "p2wpkh"
        if witness_version == 0 and len(witness_program) == 20
        else "p2wsh"
        if witness_version == 0 and len(witness_program) == 32
        else f"witness_v{witness_version}"
    )
    accepted_network = (
        configured_network
        if configured_network is BitcoinNetwork.SIGNET
        else detected_network
    )
    return AddressValidationResult(
        is_valid=True,
        network=accepted_network,
        address_type=address_type,
        normalized_address=normalized,
    )


def _network_matches(
    configured_network: BitcoinNetwork,
    detected_network: BitcoinNetwork,
) -> bool:
    if configured_network is BitcoinNetwork.SIGNET:
        return detected_network is BitcoinNetwork.TESTNET
    return configured_network is detected_network


def _base58_decode(value: str) -> bytes:
    number = 0
    for char in value:
        number = number * 58 + BASE58_ALPHABET.index(char)
    decoded = number.to_bytes((number.bit_length() + 7) // 8, "big")
    leading_zeros = len(value) - len(value.lstrip("1"))
    return (b"\x00" * leading_zeros) + decoded


def _bech32_polymod(values: list[int]) -> int:
    generator = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    checksum = 1
    for value in values:
        top = checksum >> 25
        checksum = ((checksum & 0x1FFFFFF) << 5) ^ value
        for index in range(5):
            if (top >> index) & 1:
                checksum ^= generator[index]
    return checksum


def _bech32_hrp_expand(hrp: str) -> list[int]:
    return [ord(char) >> 5 for char in hrp] + [0] + [ord(char) & 31 for char in hrp]


def _bech32_encoding(hrp: str, data: list[int]) -> str | None:
    polymod = _bech32_polymod(_bech32_hrp_expand(hrp) + data)
    if polymod == BECH32_CONST:
        return "bech32"
    if polymod == BECH32M_CONST:
        return "bech32m"
    return None


def _convertbits(
    data: list[int],
    *,
    from_bits: int,
    to_bits: int,
    pad: bool,
) -> list[int] | None:
    accumulator = 0
    bits = 0
    result: list[int] = []
    max_value = (1 << to_bits) - 1
    for value in data:
        if value < 0 or value >> from_bits:
            return None
        accumulator = (accumulator << from_bits) | value
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            result.append((accumulator >> bits) & max_value)
    if pad:
        if bits:
            result.append((accumulator << (to_bits - bits)) & max_value)
    elif bits >= from_bits or ((accumulator << (to_bits - bits)) & max_value):
        return None
    return result
