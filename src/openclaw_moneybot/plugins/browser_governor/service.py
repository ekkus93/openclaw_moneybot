"""Governed browser-action preparation without a live automation backend."""

from __future__ import annotations

import json
from collections.abc import Iterable
from urllib.parse import urlparse

from openclaw_moneybot.plugins.browser_governor.backend import (
    BrowserAutomationBackend,
    BrowserAutomationError,
    PlaywrightFirefoxBackend,
)
from openclaw_moneybot.plugins.browser_governor.models import (
    BrowserActionCompletionRequest,
    BrowserActionRequest,
    BrowserActionResult,
    BrowserExecutionRequest,
    BrowserExecutionResult,
    BrowserGovernedActionRequest,
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
    """Prepare, finalize, or execute safe browser actions through the governor."""

    def __init__(
        self,
        config: BrowserGovernorConfig,
        ledger_service: LedgerService,
        archiver: ReceiptAndEvidenceArchiver,
        automation_backend: BrowserAutomationBackend | None = None,
    ) -> None:
        self.config = config
        self.ledger_service = ledger_service
        self.archiver = archiver
        self.automation_backend = (
            PlaywrightFirefoxBackend() if automation_backend is None else automation_backend
        )

    def prepare_action(self, request: BrowserActionRequest) -> BrowserActionResult:
        """Validate a browser action, archive pre-submit evidence, and record audit state."""
        request_fingerprint = self._fingerprint(request.model_dump(mode="json"))
        existing_prepare = self._find_prepare_payload(request.action_id)
        if existing_prepare is not None:
            if existing_prepare.get("request_fingerprint") != request_fingerprint:
                return self._reject(request.action_id, "action_id_conflict")
            return BrowserActionResult(
                status=str(existing_prepare.get("status", "approved")),
                audit_record_id=str(existing_prepare["audit_record_id"]),
                before_evidence_id=str(existing_prepare.get("before_evidence_id")),
            )
        if not self.config.enabled:
            return self._reject(request.action_id, "browser_disabled")
        rejection_reason = self._validate_request(request)
        if rejection_reason is not None:
            return self._reject(request.action_id, rejection_reason)

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
                "request_fingerprint": request_fingerprint,
            },
        )
        return BrowserActionResult(
            status="approved",
            audit_record_id=audit_record_id,
            before_evidence_id=archived.evidence_id,
        )

    def execute_action(self, request: BrowserExecutionRequest) -> BrowserExecutionResult:
        """Run a bounded Playwright+Firefox action when live execution is enabled."""
        request_fingerprint = self._fingerprint(request.model_dump(mode="json"))
        existing_execution = self._find_execute_payload(request.action_id)
        if existing_execution is not None:
            if existing_execution.get("request_fingerprint") != request_fingerprint:
                return self._reject_execution(request.action_id, "action_id_conflict")
            return BrowserExecutionResult(
                status=str(existing_execution.get("status", "completed")),
                reason=self._optional_string(existing_execution.get("reason")),
                audit_record_id=str(existing_execution["audit_record_id"]),
                before_evidence_id=self._optional_string(existing_execution.get("before_evidence_id")),
                after_evidence_id=self._optional_string(existing_execution.get("after_evidence_id")),
                final_url=self._optional_string(existing_execution.get("final_url")),
                result_summary=self._optional_string(existing_execution.get("result_summary")),
            )
        if not self.config.enabled:
            return self._reject_execution(request.action_id, "browser_disabled")
        if not self.config.execution_enabled:
            return self._reject_execution(request.action_id, "browser_execution_disabled")
        rejection_reason = self._validate_request(request, require_allowed_host=True)
        if rejection_reason is not None:
            return self._reject_execution(request.action_id, rejection_reason)

        try:
            execution = self.automation_backend.execute(self.config, request)
        except BrowserAutomationError as error:
            return self._reject_execution(request.action_id, "browser_execution_failed", str(error))

        before_evidence = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.OPPORTUNITY,
                related_id=request.opportunity_id,
                evidence_type="browser_before_action",
                content_text=execution.before.page_text,
                source_url=request.target_url,
                final_url=execution.before.url,
                page_title=execution.before.page_title,
                notes=f"Automated before-action evidence for browser action {request.action_id}.",
            )
        )
        self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.OPPORTUNITY,
                related_id=request.opportunity_id,
                evidence_type="browser_before_html_snapshot",
                content_text=execution.before.html,
                source_url=request.target_url,
                final_url=execution.before.url,
                page_title=execution.before.page_title,
                mime_type="text/html",
                notes=f"Automated before-action HTML for browser action {request.action_id}.",
            )
        )
        after_evidence = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.OPPORTUNITY,
                related_id=request.opportunity_id,
                evidence_type="browser_after_action",
                content_text=execution.after.page_text,
                source_url=request.target_url,
                final_url=execution.after.url,
                page_title=execution.after.page_title,
                notes=f"Automated after-action evidence for browser action {request.action_id}.",
            )
        )
        self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.OPPORTUNITY,
                related_id=request.opportunity_id,
                evidence_type="browser_after_html_snapshot",
                content_text=execution.after.html,
                source_url=request.target_url,
                final_url=execution.after.url,
                page_title=execution.after.page_title,
                mime_type="text/html",
                notes=f"Automated after-action HTML for browser action {request.action_id}.",
            )
        )
        audit_record_id = self._record_audit(
            related_record_id=request.action_id,
            payload={
                "kind": "browser_action_execute",
                "status": "completed",
                "action_id": request.action_id,
                "opportunity_id": request.opportunity_id,
                "policy_decision_id": request.policy_decision_id,
                "action_type": request.action_type.value,
                "profile_id": request.profile_id,
                "target_url": str(request.target_url),
                "purpose": request.purpose,
                "before_evidence_id": before_evidence.evidence_id,
                "after_evidence_id": after_evidence.evidence_id,
                "final_url": execution.after.url,
                "result_summary": execution.result_summary,
                "request_fingerprint": request_fingerprint,
            },
        )
        return BrowserExecutionResult(
            status="completed",
            audit_record_id=audit_record_id,
            before_evidence_id=before_evidence.evidence_id,
            after_evidence_id=after_evidence.evidence_id,
            final_url=execution.after.url,
            result_summary=execution.result_summary,
        )

    def complete_action(self, request: BrowserActionCompletionRequest) -> BrowserActionResult:
        """Archive post-submit evidence and write the completion audit record."""
        request_fingerprint = self._fingerprint(request.model_dump(mode="json"))
        existing_complete = self._find_completion_payload(request.action_id)
        if existing_complete is not None:
            if existing_complete.get("request_fingerprint") != request_fingerprint:
                return self._reject(request.action_id, "action_id_conflict")
            return BrowserActionResult(
                status=str(existing_complete.get("status", "completed")),
                audit_record_id=str(existing_complete["audit_record_id"]),
                before_evidence_id=str(existing_complete.get("before_evidence_id")),
                after_evidence_id=str(existing_complete.get("after_evidence_id")),
            )
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
                "request_fingerprint": request_fingerprint,
            },
        )
        return BrowserActionResult(
            status="completed",
            audit_record_id=audit_record_id,
            before_evidence_id=str(prepared.get("before_evidence_id")),
            after_evidence_id=archived.evidence_id,
        )

    def _reject(self, action_id: str, reason: str) -> BrowserActionResult:
        audit_record_id = self._record_rejection(
            action_id=action_id,
            reason=reason,
            kind="browser_action_prepare",
        )
        return BrowserActionResult(
            status="rejected",
            reason=reason,
            audit_record_id=audit_record_id,
        )

    def _reject_execution(
        self,
        action_id: str,
        reason: str,
        detail: str | None = None,
    ) -> BrowserExecutionResult:
        audit_record_id = self._record_rejection(
            action_id=action_id,
            reason=reason,
            kind="browser_action_execute",
            detail=detail,
        )
        return BrowserExecutionResult(
            status="rejected",
            reason=reason,
            audit_record_id=audit_record_id,
        )

    def _record_rejection(
        self,
        *,
        action_id: str,
        reason: str,
        kind: str,
        detail: str | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "kind": kind,
            "status": "rejected",
            "action_id": action_id,
            "reason": reason,
        }
        if detail is not None:
            payload["detail"] = detail
        return self._record_audit(
            related_record_id=action_id,
            payload=payload,
        )

    def _validate_request(
        self,
        request: BrowserGovernedActionRequest,
        *,
        require_allowed_host: bool = False,
    ) -> str | None:
        if request.profile_id not in self.config.allowed_profile_ids:
            return "profile_not_allowlisted"
        if request.uses_personal_account:
            return "personal_account_blocked"
        if request.requires_kyc:
            return "kyc_requires_human_review"
        if request.attempts_captcha_bypass:
            return "captcha_bypass_blocked"
        if request.uses_bot_evasion:
            return "bot_evasion_blocked"
        if request.mass_signup:
            return "mass_signup_blocked"
        if request.scraping_against_terms:
            return "scraping_against_terms_blocked"
        if request.action_type is ActionType.PURCHASE and request.spend_request_id is None:
            return "wallet_spend_required"
        if request.spend_request_id is not None:
            spend_request = self.ledger_service.get_spend_request(request.spend_request_id)
            if spend_request is None:
                return "spend_request_missing"
        policy = self.ledger_service.get_policy_decision(request.policy_decision_id)
        if policy is None:
            return "policy_missing"
        if policy.decision is not PolicyDecisionType.ALLOW:
            return "policy_not_allow"
        if self.ledger_service.get_opportunity(request.opportunity_id) is None:
            return "opportunity_missing"
        if require_allowed_host and not self._is_host_allowlisted(str(request.target_url)):
            return "target_host_not_allowlisted"
        return None

    def _record_audit(
        self,
        *,
        related_record_id: str,
        payload: dict[str, object],
    ) -> str:
        record_id = make_id("audit")
        audit_payload = {"audit_record_id": record_id, **payload}
        write = self.ledger_service.record_ledger_record(
            LedgerRecord(
                created_at=utc_now(),
                record_id=record_id,
                record_type=RecordType.AUDIT_EVENT,
                related_record_id=related_record_id,
                payload=audit_payload,
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
                and payload.get("status") == "approved"
            ):
                return payload
        return None

    def _find_completion_payload(self, action_id: str) -> dict[str, object] | None:
        for _, payload in self._iter_audit_payloads():
            if (
                payload.get("kind") == "browser_action_complete"
                and payload.get("action_id") == action_id
                and payload.get("status") == "completed"
            ):
                return payload
        return None

    def _find_execute_payload(self, action_id: str) -> dict[str, object] | None:
        for _, payload in self._iter_audit_payloads():
            if (
                payload.get("kind") == "browser_action_execute"
                and payload.get("action_id") == action_id
            ):
                return payload
        return None

    def _is_host_allowlisted(self, url: str) -> bool:
        host = urlparse(url).hostname
        normalized_host = "" if host is None else host.lower()
        return normalized_host in self.config.allowed_hosts

    @staticmethod
    def _optional_string(value: object) -> str | None:
        if isinstance(value, str):
            return value
        return None

    @staticmethod
    def _fingerprint(payload: dict[str, object]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))
