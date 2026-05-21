"""Unit tests for operator profile storage."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from openclaw_moneybot.plugins.operator_profile_store import (
    OperatorProfileStore,
    OperatorProfileStoreReadRequest,
    OperatorProfileStoreWriteRequest,
)
from openclaw_moneybot.shared import OperatorProfileStoreConfig
from openclaw_moneybot.shared.types import ProfileAttributeAvailability, RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_store(tmp_path: Path) -> tuple[OperatorProfileStore, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    return (
        OperatorProfileStore(
            OperatorProfileStoreConfig(
                enabled=True,
                profile_path=tmp_path / "config" / "operator_profile.json",
            ),
            ledger_service,
        ),
        ledger_service,
    )


def test_reading_configured_profile_data_succeeds(tmp_path: Path) -> None:
    store, _ = make_store(tmp_path)
    store.upsert(
        OperatorProfileStoreWriteRequest(
            fields={"region": "united states", "supported_assets": ["btc"]},
            provenance={"region": "operator_config", "supported_assets": "operator_config"},
            idempotency_key="profile:1",
        )
    )

    result = store.read(OperatorProfileStoreReadRequest(field_names=["region", "supported_assets"]))

    assert result.field_results["region"].availability is ProfileAttributeAvailability.CONFIGURED
    assert result.field_results["region"].value == "united states"
    assert result.field_results["supported_assets"].value == ["btc"]


def test_unknown_field_access_returns_safe_structured_result(tmp_path: Path) -> None:
    store, _ = make_store(tmp_path)

    result = store.read(OperatorProfileStoreReadRequest(field_names=["nonexistent_field"]))

    assert (
        result.field_results["nonexistent_field"].availability
        is ProfileAttributeAvailability.UNKNOWN
    )


def test_unsupported_field_write_is_rejected(tmp_path: Path) -> None:
    store, _ = make_store(tmp_path)

    with pytest.raises(ValueError, match="Unsupported operator profile fields"):
        store.upsert(
            OperatorProfileStoreWriteRequest(
                fields={"favorite_color": "blue"},
                provenance={},
                idempotency_key="profile:unsupported",
            )
        )


def test_sensitive_field_types_are_rejected(tmp_path: Path) -> None:
    store, _ = make_store(tmp_path)

    with pytest.raises(ValueError, match="Sensitive operator profile fields"):
        store.upsert(
            OperatorProfileStoreWriteRequest(
                fields={"api_token": "secret"},
                provenance={},
                idempotency_key="profile:sensitive",
            )
        )


def test_provenance_metadata_is_preserved(tmp_path: Path) -> None:
    store, _ = make_store(tmp_path)
    store.upsert(
        OperatorProfileStoreWriteRequest(
            fields={"region": "united states"},
            provenance={"region": "manual_config"},
            idempotency_key="profile:provenance",
        )
    )

    result = store.read(OperatorProfileStoreReadRequest(field_names=["region"]))

    assert result.field_results["region"].provenance == "manual_config"


def test_versioning_and_audit_linkage_are_preserved(tmp_path: Path) -> None:
    store, ledger_service = make_store(tmp_path)
    store.upsert(
        OperatorProfileStoreWriteRequest(
            fields={"region": "united states"},
            provenance={"region": "manual_config"},
            idempotency_key="profile:first",
        )
    )

    result = store.upsert(
        OperatorProfileStoreWriteRequest(
            fields={"supported_assets": ["btc"]},
            provenance={"supported_assets": "manual_config"},
            idempotency_key="profile:second",
        )
    )

    audit_events = ledger_service.get_related_events(related_type=RecordType.AUDIT_EVENT)

    assert result.profile_version == 2
    assert any(
        cast(dict[str, object], event.payload.get("payload")).get("audit_record_id")
        == result.audit_record_id
        for event in audit_events
        if isinstance(event.payload.get("payload"), dict)
    )
