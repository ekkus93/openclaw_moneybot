"""Tests for the email governor service."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from openclaw_moneybot.plugins.email_governor import (
    EmailGovernorService,
    EmailReplyRequest,
    EmailReplyResult,
    EmailSendRequest,
    FakeEmailTransport,
)
from openclaw_moneybot.shared import (
    ArchiveConfig,
    EmailConfig,
    EmailDraftRecord,
    Opportunity,
    PolicyDecision,
)
from openclaw_moneybot.shared.types import (
    ConfidenceLevel,
    EmailMode,
    PolicyDecisionType,
    RecordType,
    RiskLevel,
)
from openclaw_moneybot.skills.ledger_skill.models import LedgerEventEntry
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import ReceiptAndEvidenceArchiver
from openclaw_moneybot.utils.time import utc_now


def make_service(
    tmp_path: Path,
    *,
    mode: EmailMode = EmailMode.CAPPED_SEND,
    max_outbound_per_day: int = 2,
    max_per_domain_per_day: int = 2,
    max_followups_per_thread: int = 1,
    allowed_sender_emails: list[str] | None = None,
) -> tuple[EmailGovernorService, FakeEmailTransport, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    ledger_service.create_opportunity(
        Opportunity(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            opportunity_id="opp_email",
            name="Email opportunity",
            category="bounty",
            status="approved",
            source_url="https://example.com/opportunity",
            required_spend_usd=0,
            estimated_revenue_usd=10,
            max_loss_usd=0,
            legal_risk_precheck=RiskLevel.LOW,
            tos_risk_precheck=RiskLevel.LOW,
        ),
        idempotency_key="opportunity:opp_email",
    )
    ledger_service.record_policy_decision(
        PolicyDecision(
            created_at=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
            policy_decision_id="policy_email_allow",
            opportunity_id="opp_email",
            decision=PolicyDecisionType.ALLOW,
            risk_level=RiskLevel.LOW,
            confidence=ConfidenceLevel.HIGH,
            policy_version="v1",
            request_fingerprint="fingerprint",
        ),
        idempotency_key="policy:policy_email_allow",
    )
    archiver = ReceiptAndEvidenceArchiver(
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    )
    transport = FakeEmailTransport()
    service = EmailGovernorService(
        EmailConfig(
            mode=mode,
            max_outbound_per_day=max_outbound_per_day,
            max_per_domain_per_day=max_per_domain_per_day,
            max_followups_per_thread=max_followups_per_thread,
            allowed_sender_emails=allowed_sender_emails or ["bot@example.com"],
        ),
        ledger_service,
        archiver,
        transport=transport,
    )
    return service, transport, ledger_service


def record_draft(
    ledger_service: LedgerService,
    *,
    email_draft_id: str,
    recipient: str,
    subject: str = "Truthful subject",
    body: str = "Hello there.\n\nYou can opt out by replying with opt out.",
    risk_flags: list[str] | None = None,
    opportunity_id: str | None = "opp_email",
    related_experiment_id: str | None = None,
) -> None:
    ledger_service.record_email(
        EmailDraftRecord(
            created_at=datetime(2026, 1, 1, 0, 2, tzinfo=UTC),
            email_draft_id=email_draft_id,
            opportunity_id=opportunity_id,
            related_experiment_id=related_experiment_id,
            to=recipient,
            subject=subject,
            body=body,
            risk_flags=risk_flags or [],
        ),
        idempotency_key=f"email:{email_draft_id}",
    )


def make_send_request(
    *,
    email_draft_id: str,
    thread_id: str = "thread-1",
    recipient_source: str = "direct_opportunity_contact",
    current_date: datetime | None = None,
    is_followup: bool = False,
    sender_email: str = "bot@example.com",
) -> EmailSendRequest:
    return EmailSendRequest(
        email_draft_id=email_draft_id,
        policy_decision_id="policy_email_allow",
        sender_email=sender_email,
        thread_id=thread_id,
        recipient_source=recipient_source,
        current_date=current_date or datetime(2026, 1, 2, tzinfo=UTC),
        idempotency_key=f"send:{email_draft_id}:{thread_id}:{is_followup}",
        is_followup=is_followup,
    )


def test_send_rejects_when_draft_only_mode(tmp_path: Path) -> None:
    service, _, ledger = make_service(tmp_path, mode=EmailMode.DRAFT_ONLY)
    record_draft(ledger, email_draft_id="draft_disabled", recipient="ops@example.com")

    result = service.send_draft(make_send_request(email_draft_id="draft_disabled"))

    assert result.status == "rejected"
    assert result.reason == "sending_disabled"


def test_send_rejects_non_allowlisted_sender(tmp_path: Path) -> None:
    service, _, ledger = make_service(tmp_path, allowed_sender_emails=["bot@example.com"])
    record_draft(ledger, email_draft_id="draft_sender", recipient="ops@example.com")

    result = service.send_draft(
        make_send_request(email_draft_id="draft_sender", sender_email="me@personal.com")
    )

    assert result.status == "rejected"
    assert result.reason == "sender_not_allowlisted"


def test_send_rejects_scraped_or_imported_contacts(tmp_path: Path) -> None:
    service, _, ledger = make_service(tmp_path)
    record_draft(ledger, email_draft_id="draft_scraped", recipient="ops@example.com")

    scraped = service.send_draft(
        make_send_request(email_draft_id="draft_scraped", recipient_source="scraped_list")
    )
    imported = service.send_draft(
        make_send_request(email_draft_id="draft_scraped", recipient_source="personal_import")
    )

    assert scraped.reason == "scraped_list_blocked"
    assert imported.reason == "personal_contact_import_blocked"


def test_send_succeeds_and_archives_message(tmp_path: Path) -> None:
    service, transport, ledger = make_service(tmp_path)
    record_draft(ledger, email_draft_id="draft_ok", recipient="ops@example.com")

    result = service.send_draft(make_send_request(email_draft_id="draft_ok"))

    assert result.status == "sent"
    assert result.message_id is not None
    assert result.archive_evidence_id is not None
    assert len(transport.sent_messages) == 1
    evidence = ledger.get_evidence_record(result.archive_evidence_id)
    assert evidence is not None
    assert evidence.evidence_type == "email_outbound_message"


def test_send_enforces_followup_limit_per_thread(tmp_path: Path) -> None:
    service, _, ledger = make_service(
        tmp_path,
        max_outbound_per_day=5,
        max_per_domain_per_day=5,
        max_followups_per_thread=1,
    )
    record_draft(ledger, email_draft_id="draft_first", recipient="ops@example.com")
    record_draft(ledger, email_draft_id="draft_second", recipient="ops@example.com")
    record_draft(ledger, email_draft_id="draft_third", recipient="ops@example.com")

    first = service.send_draft(
        make_send_request(email_draft_id="draft_first", thread_id="thread-2")
    )
    second = service.send_draft(
        make_send_request(
            email_draft_id="draft_second",
            thread_id="thread-2",
            is_followup=True,
        )
    )
    third = service.send_draft(
        make_send_request(
            email_draft_id="draft_third",
            thread_id="thread-2",
            is_followup=True,
        )
    )

    assert first.status == "sent"
    assert second.status == "sent"
    assert third.status == "rejected"
    assert third.reason == "followup_limit_exceeded"


def test_opt_out_reply_blocks_future_send(tmp_path: Path) -> None:
    service, _, ledger = make_service(tmp_path)
    record_draft(ledger, email_draft_id="draft_reply", recipient="ops@example.com")

    reply = service.classify_incoming_reply(
        EmailReplyRequest(
            thread_id="thread-3",
            sender_email="ops@example.com",
            recipient_email="bot@example.com",
            subject="Please stop",
            body="Opt out. Please stop contacting us.",
            current_date=datetime(2026, 1, 2, tzinfo=UTC),
            email_draft_id="draft_reply",
            related_opportunity_id="opp_email",
        )
    )
    result = service.send_draft(
        make_send_request(email_draft_id="draft_reply", thread_id="thread-3")
    )

    assert reply.classification == "opt_out"
    assert result.status == "rejected"
    assert result.reason == "thread_opted_out"


def test_send_rejects_missing_draft(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)

    result = service.send_draft(make_send_request(email_draft_id="missing"))

    assert result.status == "rejected"
    assert result.reason == "draft_missing"


def test_send_rejects_unlinked_draft(tmp_path: Path) -> None:
    service, _, ledger = make_service(tmp_path)
    record_draft(
        ledger,
        email_draft_id="draft_unlinked",
        recipient="ops@example.com",
        opportunity_id=None,
    )

    result = service.send_draft(make_send_request(email_draft_id="draft_unlinked"))

    assert result.status == "rejected"
    assert result.reason == "draft_unlinked"


def test_send_rejects_related_reference_mismatch(tmp_path: Path) -> None:
    service, _, ledger = make_service(tmp_path)
    record_draft(ledger, email_draft_id="draft_opp_mismatch", recipient="ops@example.com")
    record_draft(
        ledger,
        email_draft_id="draft_exp_mismatch",
        recipient="ops@example.com",
        opportunity_id=None,
        related_experiment_id="exp_1",
    )

    opp_result = service.send_draft(
        make_send_request(email_draft_id="draft_opp_mismatch").model_copy(
            update={"related_opportunity_id": "opp_other"}
        )
    )
    exp_result = service.send_draft(
        make_send_request(email_draft_id="draft_exp_mismatch").model_copy(
            update={"related_experiment_id": "exp_other"}
        )
    )

    assert opp_result.reason == "draft_reference_mismatch"
    assert exp_result.reason == "draft_reference_mismatch"


def test_send_rejects_missing_or_non_allow_policy(tmp_path: Path) -> None:
    service, _, ledger = make_service(tmp_path)
    record_draft(ledger, email_draft_id="draft_policy", recipient="ops@example.com")
    ledger.record_policy_decision(
        PolicyDecision(
            created_at=datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
            policy_decision_id="policy_email_block",
            opportunity_id="opp_email",
            decision=PolicyDecisionType.NEEDS_REVIEW,
            risk_level=RiskLevel.MEDIUM,
            confidence=ConfidenceLevel.HIGH,
            policy_version="v1",
            request_fingerprint="fingerprint-2",
        ),
        idempotency_key="policy:policy_email_block",
    )

    missing = service.send_draft(
        make_send_request(email_draft_id="draft_policy").model_copy(
            update={"policy_decision_id": "missing"}
        )
    )
    not_allow = service.send_draft(
        make_send_request(email_draft_id="draft_policy").model_copy(
            update={"policy_decision_id": "policy_email_block"}
        )
    )

    assert missing.reason == "policy_missing"
    assert not_allow.reason == "policy_not_allow"


def test_send_rejects_blocked_risk_flag_and_missing_opt_out(tmp_path: Path) -> None:
    service, _, ledger = make_service(tmp_path)
    record_draft(
        ledger,
        email_draft_id="draft_risk",
        recipient="ops@example.com",
        risk_flags=["deceptive_claim_pattern"],
    )
    record_draft(
        ledger,
        email_draft_id="draft_cold",
        recipient="ops@example.com",
        body="Hello there.\n\nThis is a cold outreach message without any opt-out text.",
    )

    risky = service.send_draft(make_send_request(email_draft_id="draft_risk"))
    no_opt_out = service.send_draft(
        make_send_request(email_draft_id="draft_cold").model_copy(update={"is_cold_outreach": True})
    )

    assert risky.reason == "draft_risk_blocked"
    assert no_opt_out.reason == "opt_out_missing"


def test_send_enforces_daily_and_domain_caps(tmp_path: Path) -> None:
    current_date = utc_now()
    service, _, ledger = make_service(
        tmp_path,
        max_outbound_per_day=1,
        max_per_domain_per_day=1,
    )
    record_draft(ledger, email_draft_id="draft_daily_1", recipient="ops@example.com")
    record_draft(ledger, email_draft_id="draft_daily_2", recipient="other@example.com")
    record_draft(ledger, email_draft_id="draft_domain", recipient="team@example.com")

    first = service.send_draft(
        make_send_request(email_draft_id="draft_daily_1", current_date=current_date)
    )
    daily = service.send_draft(
        make_send_request(email_draft_id="draft_daily_2", current_date=current_date)
    )

    assert first.status == "sent"
    assert daily.reason == "daily_rate_limit_exceeded"

    service_domain, _, ledger_domain = make_service(
        tmp_path / "domain_case",
        max_outbound_per_day=5,
        max_per_domain_per_day=1,
    )
    record_draft(ledger_domain, email_draft_id="draft_domain_1", recipient="ops@example.com")
    record_draft(ledger_domain, email_draft_id="draft_domain_2", recipient="team@example.com")
    assert (
        service_domain.send_draft(
            make_send_request(email_draft_id="draft_domain_1", current_date=current_date)
        ).status
        == "sent"
    )
    domain = service_domain.send_draft(
        make_send_request(email_draft_id="draft_domain_2", current_date=current_date)
    )
    assert domain.reason == "domain_rate_limit_exceeded"


def test_reply_classification_variants_and_related_targets(tmp_path: Path) -> None:
    service, _, ledger = make_service(tmp_path)
    record_draft(ledger, email_draft_id="draft_reply_variants", recipient="ops@example.com")

    complaint = service.classify_incoming_reply(
        EmailReplyRequest(
            thread_id="thread-complaint",
            sender_email="ops@example.com",
            recipient_email="bot@example.com",
            subject="Spam complaint",
            body="This is spam and an abuse complaint.",
            current_date=datetime(2026, 1, 2, tzinfo=UTC),
            email_draft_id="draft_reply_variants",
        )
    )
    rejection = service.classify_incoming_reply(
        EmailReplyRequest(
            thread_id="thread-rejection",
            sender_email="ops@example.com",
            recipient_email="bot@example.com",
            subject="No thanks",
            body="Not interested, decline.",
            current_date=datetime(2026, 1, 2, tzinfo=UTC),
            email_draft_id="draft_reply_variants",
        )
    )
    positive = service.classify_incoming_reply(
        EmailReplyRequest(
            thread_id="thread-positive",
            sender_email="ops@example.com",
            recipient_email="bot@example.com",
            subject="Approved",
            body="Interested, please send invoice.",
            current_date=datetime(2026, 1, 2, tzinfo=UTC),
            email_draft_id="draft_reply_variants",
        )
    )
    unmatched = service.classify_incoming_reply(
        EmailReplyRequest(
            thread_id="thread-unmatched",
            sender_email="ops@example.com",
            recipient_email="bot@example.com",
            subject="Question",
            body="Can you clarify a detail?",
            current_date=datetime(2026, 1, 2, tzinfo=UTC),
            related_opportunity_id="opp_email",
        )
    )
    fallback = service.classify_incoming_reply(
        EmailReplyRequest(
            thread_id="thread-fallback",
            sender_email="ops@example.com",
            recipient_email="bot@example.com",
            subject="Hello",
            body="General reply text.",
            current_date=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )

    assert complaint.classification == "complaint"
    assert rejection.classification == "rejection"
    assert positive.classification == "positive"
    assert unmatched.classification == "needs_review"
    unmatched_evidence = ledger.get_evidence_record(unmatched.archive_evidence_id)
    assert unmatched_evidence is not None
    assert unmatched_evidence.related_record_type is RecordType.OPPORTUNITY
    assert unmatched_evidence.related_record_id == "opp_email"
    fallback_evidence = ledger.get_evidence_record(fallback.archive_evidence_id)
    assert fallback_evidence is not None
    assert fallback_evidence.related_record_type is RecordType.OPPORTUNITY
    assert fallback_evidence.related_record_id == "thread-fallback"


def test_iter_audit_payloads_skips_malformed_and_filters_kind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _, _ = make_service(tmp_path)
    events = [
        LedgerEventEntry(
            ledger_event_id="event_bad",
            created_at=utc_now().isoformat(),
            event_type="record_audit_event",
            related_type=RecordType.AUDIT_EVENT,
            related_id="audit_1",
            payload={"payload": "not-a-dict"},
        ),
        LedgerEventEntry(
            ledger_event_id="event_send",
            created_at=utc_now().isoformat(),
            event_type="record_audit_event",
            related_type=RecordType.AUDIT_EVENT,
            related_id="audit_2",
            payload={"payload": {"kind": "email_send", "status": "sent"}},
        ),
        LedgerEventEntry(
            ledger_event_id="event_reply",
            created_at=utc_now().isoformat(),
            event_type="record_audit_event",
            related_type=RecordType.AUDIT_EVENT,
            related_id="audit_3",
            payload={"payload": {"kind": "email_reply", "classification": "opt_out"}},
        ),
    ]
    monkeypatch.setattr(service.ledger_service, "get_related_events", lambda **kwargs: events)

    all_payloads = list(service._iter_audit_payloads())
    send_payloads = list(service._iter_audit_payloads(kind="email_send"))

    assert len(all_payloads) == 2
    assert len(send_payloads) == 1
    assert send_payloads[0][1]["kind"] == "email_send"


def make_audit_iterator(
    items: list[tuple[LedgerEventEntry, dict[str, object]]],
) -> Callable[[str | None], Iterable[tuple[LedgerEventEntry, dict[str, object]]]]:
    def _iter(kind: str | None = None) -> Iterable[tuple[LedgerEventEntry, dict[str, object]]]:
        del kind
        return iter(items)

    return _iter


def test_thread_opt_out_helper_covers_true_and_false_cases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _, _ = make_service(tmp_path)
    monkeypatch.setattr(
        service,
        "_iter_audit_payloads",
        make_audit_iterator(
            [
                (
                    LedgerEventEntry(
                        ledger_event_id="event_reply",
                        created_at=utc_now().isoformat(),
                        event_type="record_audit_event",
                        related_type=RecordType.AUDIT_EVENT,
                        related_id="audit_reply",
                        payload={"payload": {"kind": "email_reply"}},
                    ),
                    {
                        "kind": "email_reply",
                        "thread_id": "thread-a",
                        "classification": "opt_out",
                    },
                )
            ]
        ),
    )
    assert service._thread_has_opt_out("thread-a", recipient_email="nobody@example.com")

    monkeypatch.setattr(
        service,
        "_iter_audit_payloads",
        make_audit_iterator(
            [
                (
                    LedgerEventEntry(
                        ledger_event_id="event_rejected",
                        created_at=utc_now().isoformat(),
                        event_type="record_audit_event",
                        related_type=RecordType.AUDIT_EVENT,
                        related_id="audit_rejected",
                        payload={"payload": {"kind": "email_send"}},
                    ),
                    {
                        "kind": "email_send",
                        "status": "rejected",
                        "thread_id": "thread-b",
                        "recipient_email": "ops@example.com",
                        "reason": "thread_opted_out",
                    },
                )
            ]
        ),
    )
    assert service._thread_has_opt_out("thread-b", recipient_email="ops@example.com")

    monkeypatch.setattr(
        service,
        "_iter_audit_payloads",
        make_audit_iterator(
            [
                (
                    LedgerEventEntry(
                        ledger_event_id="event_other",
                        created_at=utc_now().isoformat(),
                        event_type="record_audit_event",
                        related_type=RecordType.AUDIT_EVENT,
                        related_id="audit_other",
                        payload={"payload": {"kind": "email_send"}},
                    ),
                    {
                        "kind": "email_send",
                        "status": "rejected",
                        "thread_id": "thread-other",
                        "recipient_email": "other@example.com",
                        "reason": "thread_opted_out",
                    },
                )
            ]
        ),
    )
    assert not service._thread_has_opt_out("thread-c", recipient_email="ops@example.com")


def test_email_send_request_rejects_invalid_sender_addresses() -> None:
    with pytest.raises(ValidationError):
        make_send_request(email_draft_id="draft_invalid", sender_email="broken")

    with pytest.raises(ValidationError):
        make_send_request(email_draft_id="draft_invalid", sender_email="bot@invalid")


def test_email_reply_result_classification_is_constrained() -> None:
    for classification in ["positive", "rejection", "opt_out", "complaint", "needs_review"]:
        result = EmailReplyResult(
            classification=classification,
            audit_record_id="audit_1",
            archive_evidence_id="evidence_1",
        )
        assert result.classification == classification

    with pytest.raises(ValidationError):
        EmailReplyResult(
            classification="unknown",
            audit_record_id="audit_1",
            archive_evidence_id="evidence_1",
        )
