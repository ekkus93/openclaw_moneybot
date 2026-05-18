"""Governed browser-action preparation without a live automation backend."""

from __future__ import annotations

from collections.abc import Iterable

from openclaw_moneybot.plugins.browser_governor.models import (
    BrowserActionCompletionRequest,
    BrowserActionRequest,
    BrowserActionResult,
)
from openclaw_moneybot.shared import BrowserGovernorConfig, LedgerRecord
from openclaw_moneybot.shared.types import ActionType, PolicyDecisionType, RecordType
from openclaw_moneybot.skills.ledger_skill.models import LedgerEventEntry
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    EvidenceArchiveRequest,
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.utils.ids import make_id
from openclaw_moneybot.utils.time import utc_now


class BrowserGovernorService:
    """Prepare and finalize safe browser actions while keeping automation external."""

    def __init__(
        self,
        config: BrowserGovernorConfig,
        ledger_service: LedgerService,
        archiver: ReceiptAndEvidenceArchiver,
    ) -> None:
        self.config = config
        self.ledger_service = ledger_service
        self.archiver = archiver

    def prepare_action(self, request: BrowserActionRequest) -> BrowserActionResult:
        """Validate a browser action, archive pre-submit evidence, and record audit state."""
        if not self.config.enabled:
            return self._reject(request.action_id, "browser_disabled")
        if request.profile_id not in self.config.allowed_profile_ids:
            return self._reject(request.action_id, "profile_not_allowlisted")
        if request.uses_personal_account:
            return self._reject(request.action_id, "personal_account_blocked")
        if request.requires_kyc:
            return self._reject(request.action_id, "kyc_requires_human_review")
        if request.attempts_captcha_bypass:
            return self._reject(request.action_id, "captcha_bypass_blocked")
        if request.uses_bot_evasion:
            return self._reject(request.action_id, "bot_evasion_blocked")
        if request.mass_signup:
            return self._reject(request.action_id, "mass_signup_blocked")
        if request.scraping_against_terms:
            return self._reject(request.action_id, "scraping_against_terms_blocked")
        if request.action_type is ActionType.PURCHASE and request.spend_request_id is None:
            return self._reject(request.action_id, "wallet_spend_required")
        if request.spend_request_id is not None:
            spend_request = self.ledger_service.get_spend_request(request.spend_request_id)
            if spend_request is None:
                return self._reject(request.action_id, "spend_request_missing")
        policy = self.ledger_service.get_policy_decision(request.policy_decision_id)
        if policy is None:
            return self._reject(request.action_id, "policy_missing")
        if policy.decision is not PolicyDecisionType.ALLOW:
            return self._reject(request.action_id, "policy_not_allow")
        if self.ledger_service.get_opportunity(request.opportunity_id) is None:
            return self._reject(request.action_id, "opportunity_missing")

        archived = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.OPPORTUNITY,
                related_id=request.opportunity_id,
                evidence_type="browser_before_action",
                content_text=request.before_page_text,
                source_url=request.target_url,
                notes=f"Pre-submit evidence for browser action {request.action_id}.",
            )
        )
        audit_record_id = self._record_audit(
            related_record_id=request.action_id,
            payload={
                "kind": "browser_action_prepare",
                "status": "approved",
                "action_id": request.action_id,
                "opportunity_id": request.opportunity_id,
                "policy_decision_id": request.policy_decision_id,
                "action_type": request.action_type.value,
                "profile_id": request.profile_id,
                "target_url": str(request.target_url),
                "purpose": request.purpose,
                "before_evidence_id": archived.evidence_id,
                "spend_request_id": request.spend_request_id,
            },
        )
        return BrowserActionResult(
            status="approved",
            audit_record_id=audit_record_id,
            before_evidence_id=archived.evidence_id,
        )

    def complete_action(self, request: BrowserActionCompletionRequest) -> BrowserActionResult:
        """Archive post-submit evidence and write the completion audit record."""
        if not self.config.enabled:
            return self._reject(request.action_id, "browser_disabled")
        prepared = self._find_prepare_payload(request.action_id)
        if prepared is None:
            return self._reject(request.action_id, "prepare_missing")

        archived = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.OPPORTUNITY,
                related_id=request.opportunity_id,
                evidence_type="browser_after_action",
                content_text=request.after_page_text,
                notes=f"Post-submit evidence for browser action {request.action_id}.",
            )
        )
        audit_record_id = self._record_audit(
            related_record_id=request.action_id,
            payload={
                "kind": "browser_action_complete",
                "status": "completed",
                "action_id": request.action_id,
                "opportunity_id": request.opportunity_id,
                "result_summary": request.result_summary,
                "success": request.success,
                "before_evidence_id": prepared.get("before_evidence_id"),
                "after_evidence_id": archived.evidence_id,
            },
        )
        return BrowserActionResult(
            status="completed",
            audit_record_id=audit_record_id,
            before_evidence_id=str(prepared.get("before_evidence_id")),
            after_evidence_id=archived.evidence_id,
        )

    def _reject(self, action_id: str, reason: str) -> BrowserActionResult:
        audit_record_id = self._record_audit(
            related_record_id=action_id,
            payload={
                "kind": "browser_action_prepare",
                "status": "rejected",
                "action_id": action_id,
                "reason": reason,
            },
        )
        return BrowserActionResult(
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

    def _iter_audit_payloads(self) -> Iterable[tuple[LedgerEventEntry, dict[str, object]]]:
        events = self.ledger_service.get_related_events(related_type=RecordType.AUDIT_EVENT)
        for event in events:
            payload = event.payload.get("payload")
            if isinstance(payload, dict):
                yield event, payload

    def _find_prepare_payload(self, action_id: str) -> dict[str, object] | None:
        for _, payload in self._iter_audit_payloads():
            if (
                payload.get("kind") == "browser_action_prepare"
                and payload.get("action_id") == action_id
            ):
                return payload
        return None
