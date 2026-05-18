"""Governed live-email sending and reply classification."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol

from openclaw_moneybot.plugins.email_governor.models import (
    EmailReplyRequest,
    EmailReplyResult,
    EmailSendRequest,
    EmailSendResult,
)
from openclaw_moneybot.shared import EmailConfig, LedgerRecord
from openclaw_moneybot.shared.types import PolicyDecisionType, RecordType
from openclaw_moneybot.skills.ledger_skill.models import LedgerEventEntry
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    EvidenceArchiveRequest,
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.utils.ids import make_id
from openclaw_moneybot.utils.time import utc_now

BLOCKED_DRAFT_RISK_FLAGS = {
    "mass_recipient_request",
    "missing_policy_approval",
    "policy_not_allow",
    "tos_not_cleared",
    "too_many_followups",
    "deceptive_claim_pattern",
    "scraped_recipient_source",
    "harassment_loop_pattern",
    "unsupported_earnings_claim",
}
OPTOUT_CLASSIFICATIONS = {"opt_out", "complaint"}


class EmailTransport(Protocol):
    """Minimal transport interface for governed sends."""

    def send(
        self,
        *,
        sender_email: str,
        recipient_email: str,
        subject: str,
        body: str,
        thread_id: str,
    ) -> str: ...


@dataclass
class FakeEmailTransport:
    """Simple in-memory email transport for tests."""

    sent_messages: list[dict[str, str]] = field(default_factory=list)

    def send(
        self,
        *,
        sender_email: str,
        recipient_email: str,
        subject: str,
        body: str,
        thread_id: str,
    ) -> str:
        message_id = make_id("email_message")
        self.sent_messages.append(
            {
                "message_id": message_id,
                "sender_email": sender_email,
                "recipient_email": recipient_email,
                "subject": subject,
                "body": body,
                "thread_id": thread_id,
            }
        )
        return message_id


class EmailGovernorService:
    """Apply deterministic guardrails before any live email send."""

    def __init__(
        self,
        config: EmailConfig,
        ledger_service: LedgerService,
        archiver: ReceiptAndEvidenceArchiver,
        *,
        transport: EmailTransport | None = None,
    ) -> None:
        self.config = config
        self.ledger_service = ledger_service
        self.archiver = archiver
        self.transport = transport or FakeEmailTransport()

    def send_draft(self, request: EmailSendRequest) -> EmailSendResult:
        """Send a stored draft if all governor checks pass."""
        draft = self.ledger_service.get_email_record(request.email_draft_id)
        if draft is None:
            return self._reject(
                request.email_draft_id,
                "draft_missing",
                thread_id=request.thread_id,
                sender_email=request.sender_email,
            )
        if self.config.mode.value != "capped_send":
            return self._reject(
                request.email_draft_id,
                "sending_disabled",
                thread_id=request.thread_id,
                sender_email=request.sender_email,
                recipient_email=draft.to,
            )
        if request.sender_email not in self.config.allowed_sender_emails:
            return self._reject(
                request.email_draft_id,
                "sender_not_allowlisted",
                thread_id=request.thread_id,
                sender_email=request.sender_email,
                recipient_email=draft.to,
            )
        if request.recipient_source == "personal_import":
            return self._reject(
                request.email_draft_id,
                "personal_contact_import_blocked",
                thread_id=request.thread_id,
                sender_email=request.sender_email,
                recipient_email=draft.to,
            )
        if request.recipient_source == "scraped_list":
            return self._reject(
                request.email_draft_id,
                "scraped_list_blocked",
                thread_id=request.thread_id,
                sender_email=request.sender_email,
                recipient_email=draft.to,
            )
        if "," in draft.to:
            return self._reject(
                request.email_draft_id,
                "bulk_send_blocked",
                thread_id=request.thread_id,
                sender_email=request.sender_email,
                recipient_email=draft.to,
            )
        if draft.opportunity_id is None and draft.related_experiment_id is None:
            return self._reject(
                request.email_draft_id,
                "draft_unlinked",
                thread_id=request.thread_id,
                sender_email=request.sender_email,
                recipient_email=draft.to,
            )
        if (
            request.related_opportunity_id is not None
            and draft.opportunity_id != request.related_opportunity_id
        ):
            return self._reject(
                request.email_draft_id,
                "draft_reference_mismatch",
                thread_id=request.thread_id,
                sender_email=request.sender_email,
                recipient_email=draft.to,
            )
        if (
            request.related_experiment_id is not None
            and draft.related_experiment_id != request.related_experiment_id
        ):
            return self._reject(
                request.email_draft_id,
                "draft_reference_mismatch",
                thread_id=request.thread_id,
                sender_email=request.sender_email,
                recipient_email=draft.to,
            )
        policy = self.ledger_service.get_policy_decision(request.policy_decision_id)
        if policy is None:
            return self._reject(
                request.email_draft_id,
                "policy_missing",
                thread_id=request.thread_id,
                sender_email=request.sender_email,
                recipient_email=draft.to,
            )
        if policy.decision is not PolicyDecisionType.ALLOW:
            return self._reject(
                request.email_draft_id,
                "policy_not_allow",
                thread_id=request.thread_id,
                sender_email=request.sender_email,
                recipient_email=draft.to,
            )
        if any(flag in BLOCKED_DRAFT_RISK_FLAGS for flag in draft.risk_flags):
            return self._reject(
                request.email_draft_id,
                "draft_risk_blocked",
                thread_id=request.thread_id,
                sender_email=request.sender_email,
                recipient_email=draft.to,
            )
        if request.is_cold_outreach and self.config.require_opt_out_for_cold_outreach:
            lowered_body = draft.body.lower()
            if "opt out" not in lowered_body and "unsubscribe" not in lowered_body:
                return self._reject(
                    request.email_draft_id,
                    "opt_out_missing",
                    thread_id=request.thread_id,
                    sender_email=request.sender_email,
                    recipient_email=draft.to,
                )
        sent_events = list(self._iter_audit_payloads(kind="email_send"))
        same_day_count = sum(
            1
            for event, payload in sent_events
            if payload.get("status") == "sent"
            and event.created_at.startswith(request.current_date.date().isoformat())
            and payload.get("sender_email") == request.sender_email
        )
        if same_day_count >= self.config.max_outbound_per_day:
            return self._reject(
                request.email_draft_id,
                "daily_rate_limit_exceeded",
                thread_id=request.thread_id,
                sender_email=request.sender_email,
                recipient_email=draft.to,
            )
        recipient_domain = draft.to.split("@", 1)[1].lower()
        same_domain_count = sum(
            1
            for event, payload in sent_events
            if payload.get("status") == "sent"
            and event.created_at.startswith(request.current_date.date().isoformat())
            and payload.get("recipient_domain") == recipient_domain
        )
        if same_domain_count >= self.config.max_per_domain_per_day:
            return self._reject(
                request.email_draft_id,
                "domain_rate_limit_exceeded",
                thread_id=request.thread_id,
                sender_email=request.sender_email,
                recipient_email=draft.to,
            )
        prior_thread_sends = sum(
            1
            for _, payload in sent_events
            if payload.get("status") == "sent" and payload.get("thread_id") == request.thread_id
        )
        if prior_thread_sends >= 1 + self.config.max_followups_per_thread:
            return self._reject(
                request.email_draft_id,
                "followup_limit_exceeded",
                thread_id=request.thread_id,
                sender_email=request.sender_email,
                recipient_email=draft.to,
            )
        if self._thread_has_opt_out(request.thread_id, recipient_email=draft.to):
            return self._reject(
                request.email_draft_id,
                "thread_opted_out",
                thread_id=request.thread_id,
                sender_email=request.sender_email,
                recipient_email=draft.to,
            )

        message_id = self.transport.send(
            sender_email=request.sender_email,
            recipient_email=draft.to,
            subject=draft.subject,
            body=draft.body,
            thread_id=request.thread_id,
        )
        archived = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.EMAIL_DRAFT,
                related_id=draft.email_draft_id,
                evidence_type="email_outbound_message",
                content_text=(
                    f"From: {request.sender_email}\n"
                    f"To: {draft.to}\n"
                    f"Thread: {request.thread_id}\n"
                    f"Message-ID: {message_id}\n"
                    f"Subject: {draft.subject}\n\n"
                    f"{draft.body}"
                ),
                notes="Governed outbound email send record.",
            )
        )
        audit_record_id = self._record_audit(
            related_record_id=draft.email_draft_id,
            payload={
                "kind": "email_send",
                "status": "sent",
                "email_draft_id": draft.email_draft_id,
                "message_id": message_id,
                "thread_id": request.thread_id,
                "sender_email": request.sender_email,
                "recipient_email": draft.to,
                "recipient_domain": recipient_domain,
                "recipient_source": request.recipient_source,
                "is_followup": request.is_followup,
                "is_cold_outreach": request.is_cold_outreach,
                "archive_evidence_id": archived.evidence_id,
            },
        )
        return EmailSendResult(
            status="sent",
            message_id=message_id,
            audit_record_id=audit_record_id,
            archive_evidence_id=archived.evidence_id,
        )

    def classify_incoming_reply(self, request: EmailReplyRequest) -> EmailReplyResult:
        """Archive and classify one inbound reply."""
        lowered = f"{request.subject}\n{request.body}".lower()
        classification = "needs_review"
        notes: list[str] = []
        if any(token in lowered for token in ("unsubscribe", "opt out", "stop contacting")):
            classification = "opt_out"
            notes.append("Reply requested no further contact.")
        elif any(token in lowered for token in ("spam", "abuse", "complaint")):
            classification = "complaint"
            notes.append("Reply indicates a complaint or abuse report.")
        elif any(token in lowered for token in ("not interested", "decline", "no thanks")):
            classification = "rejection"
            notes.append("Reply declines the outreach.")
        elif any(token in lowered for token in ("approved", "interested", "send invoice")):
            classification = "positive"
            notes.append("Reply indicates positive intent or next-step interest.")
        else:
            notes.append("Reply did not match a safe deterministic bucket.")

        related_id = request.email_draft_id or request.related_opportunity_id or request.thread_id
        archived = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=(
                    RecordType.EMAIL_DRAFT
                    if request.email_draft_id is not None
                    else RecordType.OPPORTUNITY
                ),
                related_id=related_id,
                evidence_type="email_inbound_reply",
                content_text=(
                    f"From: {request.sender_email}\n"
                    f"To: {request.recipient_email}\n"
                    f"Thread: {request.thread_id}\n"
                    f"Subject: {request.subject}\n\n"
                    f"{request.body}"
                ),
                notes="Governed inbound email reply record.",
            )
        )
        audit_record_id = self._record_audit(
            related_record_id=related_id,
            payload={
                "kind": "email_reply",
                "classification": classification,
                "thread_id": request.thread_id,
                "sender_email": request.sender_email,
                "recipient_email": request.recipient_email,
                "email_draft_id": request.email_draft_id,
                "related_opportunity_id": request.related_opportunity_id,
                "related_experiment_id": request.related_experiment_id,
                "archive_evidence_id": archived.evidence_id,
            },
        )
        return EmailReplyResult(
            classification=classification,
            audit_record_id=audit_record_id,
            archive_evidence_id=archived.evidence_id,
            notes=notes,
        )

    def _reject(
        self,
        email_draft_id: str,
        reason: str,
        *,
        thread_id: str,
        sender_email: str,
        recipient_email: str | None = None,
    ) -> EmailSendResult:
        audit_record_id = self._record_audit(
            related_record_id=email_draft_id,
            payload={
                "kind": "email_send",
                "status": "rejected",
                "reason": reason,
                "email_draft_id": email_draft_id,
                "thread_id": thread_id,
                "sender_email": sender_email,
                "recipient_email": recipient_email,
            },
        )
        return EmailSendResult(
            status="rejected",
            reason=reason,
            audit_record_id=audit_record_id,
        )

    def _record_audit(
        self,
        *,
        related_record_id: str,
        payload: dict[str, object],
    ) -> str:
        record_id = make_id("audit")
        write = self.ledger_service.record_ledger_record(
            LedgerRecord(
                created_at=utc_now(),
                record_id=record_id,
                record_type=RecordType.AUDIT_EVENT,
                related_record_id=related_record_id,
                payload=payload,
            )
        )
        return write.record_id

    def _iter_audit_payloads(
        self,
        *,
        kind: str | None = None,
    ) -> Iterable[tuple[LedgerEventEntry, dict[str, object]]]:
        events = self.ledger_service.get_related_events(related_type=RecordType.AUDIT_EVENT)
        for event in events:
            payload = event.payload.get("payload")
            if not isinstance(payload, dict):
                continue
            if kind is not None and payload.get("kind") != kind:
                continue
            yield event, payload

    def _thread_has_opt_out(self, thread_id: str, *, recipient_email: str) -> bool:
        for _, payload in self._iter_audit_payloads():
            kind = payload.get("kind")
            if kind == "email_reply":
                if (
                    payload.get("thread_id") == thread_id
                    and payload.get("classification") in OPTOUT_CLASSIFICATIONS
                ):
                    return True
            if kind == "email_send" and payload.get("status") == "rejected":
                if (
                    payload.get("thread_id") == thread_id
                    and payload.get("recipient_email") == recipient_email
                    and payload.get("reason") == "thread_opted_out"
                ):
                    return True
        return False
