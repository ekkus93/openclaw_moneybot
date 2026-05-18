"""Tests for the email governor service."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from openclaw_moneybot.plugins.email_governor import (
    EmailGovernorService,
    EmailReplyRequest,
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
from openclaw_moneybot.shared.types import ConfidenceLevel, EmailMode, PolicyDecisionType, RiskLevel
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import ReceiptAndEvidenceArchiver


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
    opportunity_id: str = "opp_email",
) -> None:
    ledger_service.record_email(
        EmailDraftRecord(
            created_at=datetime(2026, 1, 1, 0, 2, tzinfo=UTC),
            email_draft_id=email_draft_id,
            opportunity_id=opportunity_id,
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
