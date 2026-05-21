"""Deterministic expected-versus-observed payout matching."""

from __future__ import annotations

from openclaw_moneybot.shared import ArchiveConfig
from openclaw_moneybot.shared.types import ReconciliationStatus, RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import ReceiptAndEvidenceArchiver
from openclaw_moneybot.skills.revenue_reconciler.models import (
    RevenueReconciliationRequest,
    RevenueReconciliationResult,
)
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id


class RevenueReconciler:
    """Reconcile planned revenue against observed receipts and payouts."""

    def __init__(self, archive_config: ArchiveConfig, ledger_service: LedgerService) -> None:
        self.ledger_service = ledger_service
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)

    def reconcile(self, request: RevenueReconciliationRequest) -> RevenueReconciliationResult:
        """Compare expected payout data against observed evidence."""
        reconciliation_id = make_id("reconciliation")
        observations = [
            item
            for item in request.observations
            if item.currency_or_asset.lower() == request.currency_or_asset.lower()
        ]
        if request.expected_counterparty is not None:
            observations = [
                item
                for item in observations
                if item.counterparty is None
                or item.counterparty.lower() == request.expected_counterparty.lower()
            ]

        exact_matches = [
            item
            for item in observations
            if abs(item.amount - request.expected_amount) <= request.amount_tolerance
        ]
        total_observed = round(sum(item.amount for item in observations), 2)
        reason_codes: list[str] = []
        matched_artifacts = [
            item.evidence_archive_id
            for item in exact_matches
            if item.evidence_archive_id is not None
        ]
        missing_artifacts: list[str] = []

        if len(exact_matches) > 1:
            status = ReconciliationStatus.AMBIGUOUS_NEEDS_REVIEW
            variance = round(total_observed - request.expected_amount, 2)
            reason_codes.append("multiple_exact_matches")
        elif len(exact_matches) == 1:
            matched = exact_matches[0]
            total_observed = matched.amount
            variance = round(matched.amount - request.expected_amount, 2)
            if variance < -request.amount_tolerance:
                status = ReconciliationStatus.UNDERPAID
                reason_codes.append("underpaid")
            elif variance > request.amount_tolerance:
                status = ReconciliationStatus.OVERPAID_NEEDS_REVIEW
                reason_codes.append("overpaid")
            else:
                status = ReconciliationStatus.MATCHED
                reason_codes.append("exact_match")
        elif total_observed > 0:
            variance = round(total_observed - request.expected_amount, 2)
            if len(observations) == 1 and total_observed < request.expected_amount:
                status = ReconciliationStatus.UNDERPAID
                reason_codes.append("underpaid")
            elif total_observed < request.expected_amount:
                status = ReconciliationStatus.PARTIAL
                reason_codes.append("partial_match")
            else:
                status = ReconciliationStatus.AMBIGUOUS_NEEDS_REVIEW
                reason_codes.append("ambiguous_multiple_receipts")
        elif request.expected_date is not None and request.current_date > request.expected_date:
            status = ReconciliationStatus.LATE
            variance = round(-request.expected_amount, 2)
            reason_codes.append("late_payout")
        else:
            status = ReconciliationStatus.MISSING
            variance = round(-request.expected_amount, 2)
            reason_codes.append("missing_payout")

        if not matched_artifacts and observations:
            missing_artifacts.append("payout_proof")
        followup_recommended = status in {
            ReconciliationStatus.PARTIAL,
            ReconciliationStatus.MISSING,
            ReconciliationStatus.LATE,
            ReconciliationStatus.UNDERPAID,
            ReconciliationStatus.AMBIGUOUS_NEEDS_REVIEW,
        }
        snapshot = {
            "opportunity_id": request.opportunity_id,
            "status": status.value,
            "expected_amount": request.expected_amount,
            "observed_amount": total_observed,
            "currency_or_asset": request.currency_or_asset,
            "variance": variance,
            "reason_codes": reason_codes,
            "followup_recommended": followup_recommended,
            "matched_artifacts": matched_artifacts,
            "missing_artifacts": missing_artifacts,
        }
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.PAYOUT_RECONCILIATION,
            related_id=reconciliation_id,
            evidence_type="payout_reconciliation_snapshot",
            payload=snapshot,
            notes="Deterministic payout reconciliation snapshot",
        )
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=reconciliation_id,
            record_type=RecordType.PAYOUT_RECONCILIATION,
            related_record_id=request.opportunity_id,
            payload={
                **snapshot,
                "evidence_archive_ids": [*request.evidence_archive_ids, evidence_id],
            },
        )
        return RevenueReconciliationResult(
            reconciliation_id=reconciliation_id,
            status=status,
            expected_amount=request.expected_amount,
            observed_amount=total_observed,
            currency_or_asset=request.currency_or_asset,
            variance=variance,
            matched_artifacts=matched_artifacts,
            missing_artifacts=missing_artifacts,
            followup_recommended=followup_recommended,
            reason_codes=reason_codes,
            evidence_archive_ids=[*request.evidence_archive_ids, evidence_id],
            ledger_record=ledger_record,
        )
