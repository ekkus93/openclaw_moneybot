"""Integration tests for the email drafter and email governor."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from openclaw_moneybot.plugins.email_governor import EmailReplyRequest, EmailSendRequest
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.email_drafter import EmailDraftRequest
from openclaw_moneybot.skills.ledger_skill.models import LedgerEventEntry

from .helpers import make_email_stack


def has_email_audit(
    events: list[LedgerEventEntry],
    *,
    draft_id: str,
    kinds: set[str],
) -> bool:
    for event in events:
        if event.payload.get("related_record_id") != draft_id:
            continue
        payload = event.payload.get("payload")
        if isinstance(payload, dict) and payload.get("kind") in kinds:
            return True
    return False


def count_sent_email_audits(events: list[LedgerEventEntry], *, draft_id: str) -> int:
    count = 0
    for event in events:
        if event.payload.get("related_record_id") != draft_id:
            continue
        payload = event.payload.get("payload")
        if isinstance(payload, dict) and payload.get("status") == "sent":
            count += 1
    return count


def make_draft_request(**overrides: object) -> EmailDraftRequest:
    payload: dict[str, object] = {
        "opportunity_id": "opp_001",
        "purpose": "bounty_application",
        "recipient_name": "Maintainer",
        "recipient_email": "maintainer@example.com",
        "recipient_organization": "Example Org",
        "context_summary": "I have a bounded question about the listed bounty.",
        "source_url": "https://example.com/opportunity",
        "policy_decision_id": "policy_001",
        "policy_decision": "allow",
        "tos_legal_check_id": "tos_001",
        "tos_legal_decision": "proceed",
        "allowed_claims": ["I can submit a documentation patch."],
        "requested_call_to_action": (
            "Please confirm whether documentation-only submissions are accepted."
        ),
    }
    payload.update(overrides)
    return EmailDraftRequest.model_validate(payload)


def make_send_request(email_draft_id: str, **overrides: object) -> EmailSendRequest:
    payload: dict[str, object] = {
        "email_draft_id": email_draft_id,
        "policy_decision_id": "policy_001",
        "sender_email": "bot@example.com",
        "thread_id": "thread-001",
        "recipient_source": "direct_opportunity_contact",
        "current_date": datetime(2026, 1, 2, tzinfo=UTC),
        "idempotency_key": f"send:{email_draft_id}",
        "related_opportunity_id": "opp_001",
    }
    payload.update(overrides)
    return EmailSendRequest.model_validate(payload)


def make_reply_request(**overrides: object) -> EmailReplyRequest:
    payload: dict[str, object] = {
        "thread_id": "thread-001",
        "sender_email": "maintainer@example.com",
        "recipient_email": "bot@example.com",
        "subject": "Re: listed bounty",
        "body": "Interested. Please send invoice.",
        "current_date": datetime(2026, 1, 2, tzinfo=UTC),
        "email_draft_id": "email_draft_placeholder",
        "related_opportunity_id": "opp_001",
    }
    payload.update(overrides)
    return EmailReplyRequest.model_validate(payload)


def test_email_governor_sends_draft_and_archives_outbound_message(tmp_path: Path) -> None:
    ledger_service, drafter, governor, transport = make_email_stack(tmp_path)
    draft = drafter.draft(make_draft_request())

    result = governor.send_draft(make_send_request(draft.email_draft_id))

    stored_draft = ledger_service.get_email_record(draft.email_draft_id)
    audit_events = ledger_service.get_related_events(related_type=RecordType.AUDIT_EVENT)

    assert stored_draft is not None
    assert stored_draft.opportunity_id == "opp_001"
    assert result.status == "sent"
    assert result.archive_evidence_id is not None
    assert len(transport.sent_messages) == 1
    assert has_email_audit(audit_events, draft_id=draft.email_draft_id, kinds={"email_send"})
    assert ledger_service.get_evidence_record(result.archive_evidence_id) is not None


def test_email_governor_rejects_send_when_policy_blocks(tmp_path: Path) -> None:
    ledger_service, drafter, governor, _ = make_email_stack(tmp_path)
    draft = drafter.draft(make_draft_request())

    result = governor.send_draft(
        make_send_request(
            draft.email_draft_id,
            policy_decision_id="policy_blocked",
        )
    )

    audit_events = ledger_service.get_related_events(related_type=RecordType.AUDIT_EVENT)

    assert result.status == "rejected"
    assert result.reason == "policy_not_allow"
    assert has_email_audit(audit_events, draft_id=draft.email_draft_id, kinds={"email_send"})
    assert result.message_id is None


def test_email_governor_rejects_cold_outreach_without_opt_out_text(tmp_path: Path) -> None:
    _, drafter, governor, transport = make_email_stack(tmp_path)
    draft = drafter.draft(
        make_draft_request(
            purpose="proposal",
            context_summary="Offer a small scoped collaboration.",
            requested_call_to_action="Would you be open to a short reply?",
        )
    )

    result = governor.send_draft(
        make_send_request(
            draft.email_draft_id,
            is_cold_outreach=True,
            thread_id="thread-cold",
            idempotency_key="send:cold",
        )
    )

    assert result.status == "rejected"
    assert result.reason == "opt_out_missing"
    assert transport.sent_messages == []


def test_email_governor_positive_reply_is_archived_and_linked(tmp_path: Path) -> None:
    ledger_service, drafter, governor, _ = make_email_stack(tmp_path)
    draft = drafter.draft(make_draft_request())
    send_result = governor.send_draft(make_send_request(draft.email_draft_id))

    reply_result = governor.classify_incoming_reply(
        make_reply_request(email_draft_id=draft.email_draft_id)
    )

    assert send_result.status == "sent"
    assert reply_result.classification == "positive"
    assert ledger_service.get_evidence_record(reply_result.archive_evidence_id) is not None
    audit_events = ledger_service.get_related_events(related_type=RecordType.AUDIT_EVENT)
    assert has_email_audit(
        audit_events,
        draft_id=draft.email_draft_id,
        kinds={"email_send", "email_reply"},
    )


def test_email_governor_opt_out_reply_blocks_future_send_on_same_thread(
    tmp_path: Path,
) -> None:
    _, drafter, governor, transport = make_email_stack(tmp_path)
    draft = drafter.draft(
        make_draft_request(
            purpose="followup",
            context_summary="Checking once on the earlier question.",
            requested_call_to_action="A short yes or no is enough.",
        )
    )
    first_send = governor.send_draft(make_send_request(draft.email_draft_id))
    opt_out_reply = governor.classify_incoming_reply(
        make_reply_request(
            email_draft_id=draft.email_draft_id,
            body="Please unsubscribe and stop contacting me.",
        )
    )
    second_send = governor.send_draft(
        make_send_request(
            draft.email_draft_id,
            is_followup=True,
            idempotency_key="send:followup",
        )
    )

    assert first_send.status == "sent"
    assert opt_out_reply.classification == "opt_out"
    assert second_send.status == "rejected"
    assert second_send.reason == "thread_opted_out"
    assert len(transport.sent_messages) == 1


def test_email_governor_complaint_reply_is_archived_against_same_thread(tmp_path: Path) -> None:
    ledger_service, drafter, governor, _ = make_email_stack(tmp_path)
    draft = drafter.draft(make_draft_request())
    governor.send_draft(make_send_request(draft.email_draft_id))

    reply_result = governor.classify_incoming_reply(
        make_reply_request(
            email_draft_id=draft.email_draft_id,
            body="This is spam and I am filing a complaint.",
        )
    )

    evidence = ledger_service.get_evidence_record(reply_result.archive_evidence_id)

    assert reply_result.classification == "complaint"
    assert evidence is not None
    assert evidence.related_record_type is RecordType.EMAIL_DRAFT


def test_email_send_replay_reuses_prior_success_result(tmp_path: Path) -> None:
    ledger_service, drafter, governor, transport = make_email_stack(tmp_path)
    draft = drafter.draft(make_draft_request())
    request = make_send_request(draft.email_draft_id, idempotency_key="email-send-replay")

    first_result = governor.send_draft(request)
    second_result = governor.send_draft(request)
    audit_events = ledger_service.get_related_events(related_type=RecordType.AUDIT_EVENT)

    assert first_result.status == "sent"
    assert second_result.status == "sent"
    assert first_result.message_id == second_result.message_id
    assert first_result.audit_record_id == second_result.audit_record_id
    assert first_result.archive_evidence_id == second_result.archive_evidence_id
    assert len(transport.sent_messages) == 1
    assert count_sent_email_audits(audit_events, draft_id=draft.email_draft_id) == 1


def test_email_rejected_replay_reuses_prior_audit_result(tmp_path: Path) -> None:
    _, drafter, governor, transport = make_email_stack(tmp_path)
    draft = drafter.draft(make_draft_request())
    request = make_send_request(
        draft.email_draft_id,
        policy_decision_id="policy_blocked",
        idempotency_key="email-send-rejected-replay",
    )

    first_result = governor.send_draft(request)
    second_result = governor.send_draft(request)

    assert first_result.status == "rejected"
    assert second_result.status == "rejected"
    assert first_result.reason == "policy_not_allow"
    assert second_result.reason == "policy_not_allow"
    assert first_result.audit_record_id == second_result.audit_record_id
    assert transport.sent_messages == []
