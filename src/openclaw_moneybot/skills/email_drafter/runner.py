"""Draft-only email generation."""

from __future__ import annotations

from openclaw_moneybot.shared import ArchiveConfig, EmailDraftRecord
from openclaw_moneybot.skills.email_drafter.compliance import evaluate_compliance
from openclaw_moneybot.skills.email_drafter.models import EmailDraftRequest, EmailDraftResult
from openclaw_moneybot.skills.email_drafter.templates import render_template
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    EvidenceArchiveRequest,
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.utils.ids import make_id
from openclaw_moneybot.utils.time import utc_now


class EmailDrafter:
    """Generate truthful, draft-only business emails."""

    def __init__(self, archive_config: ArchiveConfig, ledger_service: LedgerService) -> None:
        self.ledger_service = ledger_service
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)

    def draft(self, request: EmailDraftRequest) -> EmailDraftResult:
        """Create a draft email, archive it, and write it to the ledger."""
        template_name, subject, body = render_template(request)
        risk_flags, compliance_notes, review_required = evaluate_compliance(request)
        draft_id = make_id("email")
        record = EmailDraftRecord(
            created_at=utc_now(),
            email_draft_id=draft_id,
            opportunity_id=request.opportunity_id,
            to=str(request.recipient_email),
            subject=subject,
            body=body,
            risk_flags=risk_flags,
        )
        self.ledger_service.record_email(record, idempotency_key=f"email:{draft_id}")
        archived = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type="email_draft",
                related_id=draft_id,
                evidence_type="email_draft",
                content_text=body,
                source_url=request.source_url,
                notes=f"Draft email for purpose {request.purpose}",
            )
        )
        return EmailDraftResult(
            email_draft_id=draft_id,
            mode="draft_only",
            to=str(request.recipient_email),
            subject=subject,
            body=body,
            risk_flags=risk_flags,
            compliance_notes=compliance_notes,
            requires_human_review=review_required,
            ledger_record=record,
            evidence_archive_ids=[archived.evidence_id],
            template_name=template_name,
            generated_at=utc_now().isoformat(timespec="seconds"),
        )
