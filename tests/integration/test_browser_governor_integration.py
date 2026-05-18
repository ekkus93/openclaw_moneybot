"""Integration tests for the browser governor."""

from __future__ import annotations

from pathlib import Path

from openclaw_moneybot.plugins.browser_governor import (
    BrowserActionCompletionRequest,
    BrowserActionRequest,
)
from openclaw_moneybot.shared import LedgerRecord
from openclaw_moneybot.shared.types import ActionType, RecordType
from openclaw_moneybot.skills.ledger_skill.models import LedgerEventEntry
from openclaw_moneybot.utils.time import utc_now

from .helpers import make_browser_stack


def make_prepare_request(**overrides: object) -> BrowserActionRequest:
    payload: dict[str, object] = {
        "action_id": "browser-action-1",
        "opportunity_id": "opp_001",
        "policy_decision_id": "policy_001",
        "action_type": ActionType.BROWSER_SUBMIT,
        "profile_id": "moneybot-default",
        "target_url": "https://example.com/form",
        "purpose": "Submit one approved form.",
        "before_page_text": "Visible form fields before submit.",
    }
    payload.update(overrides)
    return BrowserActionRequest.model_validate(payload)


def make_completion_request(**overrides: object) -> BrowserActionCompletionRequest:
    payload: dict[str, object] = {
        "action_id": "browser-action-1",
        "opportunity_id": "opp_001",
        "after_page_text": "Confirmation page after submit.",
        "result_summary": "Submitted successfully.",
        "success": True,
    }
    payload.update(overrides)
    return BrowserActionCompletionRequest.model_validate(payload)


def count_browser_audits(events: list[LedgerEventEntry], *, action_id: str, kind: str) -> int:
    count = 0
    for event in events:
        if event.payload.get("related_record_id") != action_id:
            continue
        payload = event.payload.get("payload")
        if isinstance(payload, dict) and payload.get("kind") == kind:
            count += 1
    return count


def test_browser_prepare_and_complete_write_linked_evidence_and_audits(tmp_path: Path) -> None:
    ledger_service, governor = make_browser_stack(tmp_path, enabled=True)

    prepared = governor.prepare_action(make_prepare_request())
    completed = governor.complete_action(make_completion_request())

    audit_events = ledger_service.get_related_events(related_type=RecordType.AUDIT_EVENT)
    opportunity_evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.OPPORTUNITY,
        related_id="opp_001",
    )

    assert prepared.before_evidence_id is not None
    assert completed.after_evidence_id is not None
    assert prepared.status == "approved"
    assert completed.status == "completed"
    assert completed.before_evidence_id == prepared.before_evidence_id
    assert ledger_service.get_evidence_record(prepared.before_evidence_id) is not None
    assert ledger_service.get_evidence_record(completed.after_evidence_id) is not None
    assert (
        len(
            [
                record
                for record in opportunity_evidence
                if record.evidence_type in {"browser_before_action", "browser_after_action"}
            ]
        )
        == 2
    )
    assert (
        count_browser_audits(
            audit_events,
            action_id="browser-action-1",
            kind="browser_action_prepare",
        )
        == 1
    )
    assert (
        count_browser_audits(
            audit_events,
            action_id="browser-action-1",
            kind="browser_action_complete",
        )
        == 1
    )


def test_browser_prepare_rejects_purchase_without_linked_spend(tmp_path: Path) -> None:
    _, governor = make_browser_stack(tmp_path, enabled=True)

    result = governor.prepare_action(
        make_prepare_request(action_id="browser-action-purchase", action_type=ActionType.PURCHASE)
    )

    assert result.status == "rejected"
    assert result.reason == "wallet_spend_required"


def test_browser_prepare_rejects_non_allow_policy_without_archiving_action_evidence(
    tmp_path: Path,
) -> None:
    ledger_service, governor = make_browser_stack(tmp_path, enabled=True, allow_policy=False)

    result = governor.prepare_action(make_prepare_request(action_id="browser-action-blocked"))

    opportunity_evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.OPPORTUNITY,
        related_id="opp_001",
    )

    assert result.status == "rejected"
    assert result.reason == "policy_not_allow"
    assert [
        record
        for record in opportunity_evidence
        if record.evidence_type in {"browser_before_action", "browser_after_action"}
    ] == []


def test_browser_disabled_blocks_prepare_and_complete_consistently(tmp_path: Path) -> None:
    _, governor = make_browser_stack(tmp_path, enabled=False)

    prepare_result = governor.prepare_action(make_prepare_request())
    complete_result = governor.complete_action(make_completion_request())

    assert prepare_result.status == "rejected"
    assert prepare_result.reason == "browser_disabled"
    assert complete_result.status == "rejected"
    assert complete_result.reason == "browser_disabled"


def test_browser_prepare_and_complete_are_traceable_despite_unrelated_audit_events(
    tmp_path: Path,
) -> None:
    ledger_service, governor = make_browser_stack(tmp_path, enabled=True)
    prepared = governor.prepare_action(make_prepare_request())
    ledger_service.record_ledger_record(
        LedgerRecord(
            created_at=utc_now(),
            record_id="audit_unrelated_browser",
            record_type=RecordType.AUDIT_EVENT,
            related_record_id="other-action",
            payload={"kind": "browser_action_prepare", "action_id": "other-action"},
        ),
        idempotency_key="audit:unrelated-browser",
    )

    completed = governor.complete_action(make_completion_request())
    audit_events = ledger_service.get_related_events(related_type=RecordType.AUDIT_EVENT)

    assert completed.status == "completed"
    assert completed.before_evidence_id == prepared.before_evidence_id
    assert (
        sum(
            1
            for event in audit_events
            if event.payload.get("related_record_id") == "browser-action-1"
        )
        == 2
    )


def test_browser_replay_reuses_prepare_and_complete_artifacts(tmp_path: Path) -> None:
    ledger_service, governor = make_browser_stack(tmp_path, enabled=True)

    first_prepare = governor.prepare_action(make_prepare_request(action_id="browser-action-replay"))
    second_prepare = governor.prepare_action(
        make_prepare_request(action_id="browser-action-replay")
    )
    first_complete = governor.complete_action(
        make_completion_request(action_id="browser-action-replay")
    )
    second_complete = governor.complete_action(
        make_completion_request(action_id="browser-action-replay")
    )
    opportunity_evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.OPPORTUNITY,
        related_id="opp_001",
    )

    assert first_prepare.audit_record_id == second_prepare.audit_record_id
    assert first_prepare.before_evidence_id == second_prepare.before_evidence_id
    assert first_complete.audit_record_id == second_complete.audit_record_id
    assert first_complete.after_evidence_id == second_complete.after_evidence_id
    assert (
        len(
            [
                record
                for record in opportunity_evidence
                if record.evidence_type in {"browser_before_action", "browser_after_action"}
            ]
        )
        == 2
    )
