"""Safe payout follow-up recommendations."""

from __future__ import annotations

from openclaw_moneybot.shared import ArchiveConfig
from openclaw_moneybot.shared.types import (
    CounterpartyRiskTier,
    PayoutFollowupRecommendation,
    ReconciliationStatus,
    RecordType,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.payout_followup_planner.models import (
    PayoutFollowupPlanRequest,
    PayoutFollowupPlanResult,
)
from openclaw_moneybot.skills.receipt_and_evidence_archiver import ReceiptAndEvidenceArchiver
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id


class PayoutFollowupPlanner:
    """Recommend bounded next steps for late or missing payouts."""

    def __init__(self, archive_config: ArchiveConfig, ledger_service: LedgerService) -> None:
        self.ledger_service = ledger_service
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)

    def plan(self, request: PayoutFollowupPlanRequest) -> PayoutFollowupPlanResult:
        """Create a safe follow-up recommendation."""
        plan_id = make_id("followup_plan")
        if request.terms_ambiguous or request.counterparty_risk_tier is CounterpartyRiskTier.HIGH:
            recommendation = PayoutFollowupRecommendation.HUMAN_REVIEW
            draft_needed = False
            message_purpose = None
            timing = "pause_for_manual_review"
        elif not request.has_supporting_evidence:
            recommendation = PayoutFollowupRecommendation.GATHER_MISSING_PROOF
            draft_needed = False
            message_purpose = None
            timing = "collect_receipts_and_threads"
        elif request.reconciliation_status in {
            ReconciliationStatus.LATE,
            ReconciliationStatus.MISSING,
        } and request.days_since_expected <= request.grace_period_days:
            recommendation = PayoutFollowupRecommendation.WAIT
            draft_needed = False
            message_purpose = None
            timing = "wait_for_grace_period"
        elif request.reconciliation_status in {
            ReconciliationStatus.UNDERPAID,
            ReconciliationStatus.LATE,
            ReconciliationStatus.PARTIAL,
        }:
            recommendation = PayoutFollowupRecommendation.DRAFT_FOLLOWUP
            draft_needed = True
            message_purpose = "payment_followup"
            timing = "draft_after_evidence_review"
        else:
            recommendation = PayoutFollowupRecommendation.STOP_AND_RECORD_LOSS
            draft_needed = False
            message_purpose = None
            timing = "record_loss_and_stop"

        required_supporting_evidence = [] if request.has_supporting_evidence else ["payment_proof"]
        stop_conditions = [
            "never_auto_send_followup",
            "stop_if_terms_are_ambiguous",
            "stop_if_manual_review_is_required",
        ]
        snapshot = {
            "recommendation": recommendation.value,
            "draft_needed": draft_needed,
            "suggested_message_purpose": message_purpose,
            "required_supporting_evidence": required_supporting_evidence,
            "timing_recommendation": timing,
            "stop_conditions": stop_conditions,
        }
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.FOLLOWUP_PLAN,
            related_id=plan_id,
            evidence_type="payout_followup_draft",
            payload=snapshot,
            notes="Payout follow-up planning snapshot",
        )
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=plan_id,
            record_type=RecordType.FOLLOWUP_PLAN,
            related_record_id=request.opportunity_id,
            payload={
                **snapshot,
                "evidence_archive_ids": [*request.evidence_archive_ids, evidence_id],
            },
        )
        return PayoutFollowupPlanResult(
            followup_plan_id=plan_id,
            recommendation=recommendation,
            draft_needed=draft_needed,
            suggested_message_purpose=message_purpose,
            required_supporting_evidence=required_supporting_evidence,
            timing_recommendation=timing,
            stop_conditions=stop_conditions,
            evidence_archive_ids=[*request.evidence_archive_ids, evidence_id],
            ledger_record=ledger_record,
        )
