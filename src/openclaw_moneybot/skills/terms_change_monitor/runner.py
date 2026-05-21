"""Deterministic monitoring for changed rules and terms."""

from __future__ import annotations

import re
from decimal import Decimal

from openclaw_moneybot.shared import ArchiveConfig
from openclaw_moneybot.shared.types import RecordType, TermsChangeSeverity
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import ReceiptAndEvidenceArchiver
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.skills.terms_change_monitor.models import (
    TermsChangeMonitorRequest,
    TermsChangeMonitorResult,
)
from openclaw_moneybot.utils.ids import make_id


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _extract_amount(value: str) -> Decimal | None:
    match = re.search(r"\$([0-9]+(?:\.[0-9]+)?)", value)
    if match is None:
        return None
    return Decimal(match.group(1))


def _extract_deadline_line(value: str) -> str | None:
    for line in value.splitlines():
        lowered = line.lower()
        if "deadline" in lowered or "due" in lowered:
            return lowered.strip()
    return None


def _max_severity(
    current: TermsChangeSeverity,
    candidate: TermsChangeSeverity,
) -> TermsChangeSeverity:
    order = {
        TermsChangeSeverity.NONE: 0,
        TermsChangeSeverity.LOW: 1,
        TermsChangeSeverity.MEDIUM: 2,
        TermsChangeSeverity.HIGH: 3,
        TermsChangeSeverity.BLOCK: 4,
    }
    return candidate if order[candidate] > order[current] else current


class TermsChangeMonitor:
    """Detect material rules changes and force refreshed checks when needed."""

    def __init__(self, archive_config: ArchiveConfig, ledger_service: LedgerService) -> None:
        self.ledger_service = ledger_service
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)

    def evaluate(self, request: TermsChangeMonitorRequest) -> TermsChangeMonitorResult:
        """Compare a prior rules snapshot to a current rules snapshot."""
        terms_change_id = make_id("terms_change")
        current = request.current_rules_text
        prior = request.prior_rules_text
        changed_fields: list[str] = []
        severity = TermsChangeSeverity.NONE

        if prior is None or not prior.strip():
            changed_fields.append("missing_prior_snapshot")
            severity = TermsChangeSeverity.HIGH
        else:
            normalized_prior = _normalize(prior)
            normalized_current = _normalize(current)
            if normalized_prior == normalized_current:
                if prior == current:
                    severity = TermsChangeSeverity.NONE
                else:
                    changed_fields.append("formatting_only")
                    severity = TermsChangeSeverity.LOW
            elif _extract_amount(prior) != _extract_amount(current):
                changed_fields.append("payout_amount")
                severity = TermsChangeSeverity.HIGH
            if (
                ("paypal" in prior.lower()) != ("paypal" in current.lower())
                or ("bank wire" in prior.lower()) != ("bank wire" in current.lower())
                or ("btc" in prior.lower()) != ("btc" in current.lower())
            ):
                changed_fields.append("payout_method")
                severity = _max_severity(severity, TermsChangeSeverity.MEDIUM)
            if _extract_deadline_line(prior) != _extract_deadline_line(current):
                changed_fields.append("submission_deadline")
                severity = _max_severity(severity, TermsChangeSeverity.MEDIUM)
            if (
                "automation prohibited" in current.lower() or "no bots" in current.lower()
            ) and not (
                "automation prohibited" in prior.lower() or "no bots" in prior.lower()
            ):
                changed_fields.append("automation_policy")
                severity = TermsChangeSeverity.BLOCK
            if ("kyc" in current.lower() or "tax form" in current.lower()) and not (
                "kyc" in prior.lower() or "tax form" in prior.lower()
            ):
                changed_fields.append("kyc_tax_requirement")
                severity = _max_severity(severity, TermsChangeSeverity.HIGH)
            if ("deliverable" in current.lower()) != ("deliverable" in prior.lower()):
                changed_fields.append("required_deliverable")
                severity = _max_severity(severity, TermsChangeSeverity.MEDIUM)
            if ("refund" in current.lower() or "chargeback" in current.lower()) != (
                "refund" in prior.lower() or "chargeback" in prior.lower()
            ):
                changed_fields.append("refund_chargeback")
                severity = _max_severity(severity, TermsChangeSeverity.MEDIUM)
            if not changed_fields and normalized_prior != normalized_current:
                changed_fields.append("formatting_only")
                severity = TermsChangeSeverity.LOW

        change_detected = bool(changed_fields) or severity is TermsChangeSeverity.LOW
        requires_recheck = severity is not TermsChangeSeverity.NONE
        requires_budget_recheck = bool(
            {"payout_amount", "payout_method", "submission_deadline"}
            & set(changed_fields)
        )
        requires_policy_recheck = bool(
            {"automation_policy", "kyc_tax_requirement"} & set(changed_fields)
        ) or severity is TermsChangeSeverity.BLOCK
        if "missing_prior_snapshot" in changed_fields:
            requires_recheck = True
            requires_budget_recheck = request.prior_budget_plan_id is not None
            requires_policy_recheck = True
        summary = (
            "No material changes detected."
            if severity is TermsChangeSeverity.NONE
            else f"Detected {', '.join(changed_fields)} changes with {severity.value} severity."
        )
        snapshot = {
            "opportunity_id": request.opportunity_id,
            "change_detected": change_detected,
            "severity": severity.value,
            "changed_fields": changed_fields,
            "requires_recheck": requires_recheck,
            "requires_budget_recheck": requires_budget_recheck,
            "requires_policy_recheck": requires_policy_recheck,
            "summary": summary,
        }
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.TERMS_CHANGE,
            related_id=terms_change_id,
            evidence_type="terms_diff_report",
            payload=snapshot,
            notes="Rules and terms change summary",
        )
        evidence_archive_ids = [
            *request.prior_evidence_archive_ids,
            *request.current_evidence_archive_ids,
            evidence_id,
        ]
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=terms_change_id,
            record_type=RecordType.TERMS_CHANGE,
            related_record_id=request.opportunity_id,
            payload={**snapshot, "evidence_archive_ids": evidence_archive_ids},
        )
        return TermsChangeMonitorResult(
            terms_change_id=terms_change_id,
            change_detected=change_detected,
            severity=severity,
            changed_fields=changed_fields,
            summary=summary,
            requires_recheck=requires_recheck,
            requires_budget_recheck=requires_budget_recheck,
            requires_policy_recheck=requires_policy_recheck,
            evidence_archive_ids=evidence_archive_ids,
            ledger_record=ledger_record,
        )
