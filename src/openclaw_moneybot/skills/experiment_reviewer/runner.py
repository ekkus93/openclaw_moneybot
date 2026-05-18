"""Experiment review runner."""

from __future__ import annotations

import json

from openclaw_moneybot.shared import ArchiveConfig, ExperimentReview
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.experiment_reviewer.decision import decide_review
from openclaw_moneybot.skills.experiment_reviewer.metrics import calculate_review_metrics
from openclaw_moneybot.skills.experiment_reviewer.models import (
    ExperimentReviewRequest,
    ExperimentReviewResult,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    EvidenceArchiveRequest,
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.utils.ids import make_id
from openclaw_moneybot.utils.time import utc_now


class ExperimentReviewer:
    """Summarize outcomes and decide next steps deterministically."""

    def __init__(self, archive_config: ArchiveConfig, ledger_service: LedgerService) -> None:
        self.ledger_service = ledger_service
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)

    def review(self, request: ExperimentReviewRequest) -> ExperimentReviewResult:
        """Review one experiment from ledger context and explicit outcomes."""
        opportunity = self.ledger_service.get_opportunity(request.opportunity_id)
        budget_plan = self.ledger_service.get_budget_plan(request.budget_plan_id)
        if opportunity is None or budget_plan is None:
            msg = "Opportunity and budget plan must exist before review."
            raise ValueError(msg)

        wallet_transactions = self.ledger_service.list_wallet_transactions_for_opportunity(
            request.opportunity_id
        )
        spend_requests = self.ledger_service.list_spend_requests_for_opportunity(
            request.opportunity_id
        )
        email_records = self.ledger_service.list_email_records_for_opportunity(
            request.opportunity_id
        )
        policy_decision = self.ledger_service.get_policy_decision(budget_plan.policy_decision_id)
        tos_legal_check = self.ledger_service.get_tos_legal_check(budget_plan.tos_legal_check_id)
        evidence_records = [
            record
            for evidence_id in request.evidence_archive_ids
            if (record := self.ledger_service.get_evidence_record(evidence_id)) is not None
        ]
        evidence_records.extend(
            self.ledger_service.list_evidence_for_related(
                related_type=RecordType.EXPERIMENT_REVIEW,
                related_id=request.opportunity_id,
            )
        )
        metrics = calculate_review_metrics(
            budget_plan=budget_plan,
            wallet_transactions=wallet_transactions,
            revenue_usd=request.revenue_usd,
            unrealized_value_usd=request.unrealized_value_usd,
            fees_usd=request.fees_usd,
            evidence_records=evidence_records,
        )
        incident_flags = list(request.incident_flags)
        failed_spends = [item for item in spend_requests if item.status.value == "failed"]
        rejected_spends = [item for item in spend_requests if item.status.value == "rejected"]
        if failed_spends:
            incident_flags.append("failed_wallet_spend")
        if rejected_spends:
            incident_flags.append("rejected_wallet_spend")
        if not evidence_records:
            incident_flags.append("missing_evidence")
        if not email_records and request.revenue_usd == 0:
            incident_flags.append("no_response_outcome")
        if len(failed_spends) + len(rejected_spends) >= 2:
            incident_flags.append("repeated_failures")
        (
            status,
            decision,
            lessons,
            next_actions,
            new_blocklist_patterns,
            policy_feedback,
        ) = decide_review(
            metrics=metrics,
            incident_flags=incident_flags,
            success_metric_met=request.success_metric_met,
            stop_condition_triggered=request.stop_condition_triggered,
        )
        scoring_feedback = {
            "category": opportunity.category,
            "category_performance": "positive" if metrics.net_usd > 0 else "negative",
            "expected_vs_actual_revenue_delta": round(
                request.revenue_usd - budget_plan.expected_gross_revenue_usd,
                2,
            ),
            "time_spent_hours": request.time_spent_hours,
            "email_draft_count": len(email_records),
        }
        budget_feedback: list[str] = []
        if metrics.budget_exceeded:
            budget_feedback.append("Actual spend exceeded the planned budget.")
        if request.revenue_usd < budget_plan.expected_gross_revenue_usd:
            budget_feedback.append("Expected revenue was overstated relative to the outcome.")
        if request.time_spent_hours > 0:
            budget_feedback.append("Time cost should be considered in future plans.")
        if metrics.fee_usd > 0:
            budget_feedback.append("Wallet and network fees reduced realized ROI.")

        review_id = make_id("review")
        ledger_record = ExperimentReview(
            created_at=utc_now(),
            experiment_review_id=review_id,
            opportunity_id=request.opportunity_id,
            spent_usd=metrics.spent_usd,
            revenue_usd=request.revenue_usd,
            net_usd=metrics.net_usd,
            roi_percent=metrics.roi_percent,
            outcome=status,
            decision=decision,
            lessons=lessons,
            recommended_next_actions=next_actions,
        )
        archived = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.EXPERIMENT_REVIEW,
                related_id=review_id,
                evidence_type="experiment_review_snapshot",
                content_text=json.dumps(
                    {
                        "review_reason": request.review_reason,
                        "incident_flags": request.incident_flags,
                        "derived_incident_flags": incident_flags,
                        "manual_notes": request.manual_notes,
                        "scoring_feedback": scoring_feedback,
                        "budget_feedback": budget_feedback,
                        "policy_feedback": policy_feedback,
                        "policy_decision_id": None
                        if policy_decision is None
                        else policy_decision.policy_decision_id,
                        "tos_legal_check_id": None
                        if tos_legal_check is None
                        else tos_legal_check.tos_legal_check_id,
                        "spend_request_ids": [
                            item.spend_request_id for item in spend_requests
                        ],
                        "wallet_transaction_ids": [
                            item.wallet_transaction_id for item in wallet_transactions
                        ],
                        "email_draft_ids": [item.email_draft_id for item in email_records],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                notes="Deterministic experiment review snapshot",
            )
        )
        self.ledger_service.record_experiment_review(
            ledger_record,
            idempotency_key=f"review:{review_id}",
        )
        return ExperimentReviewResult(
            experiment_review_id=review_id,
            opportunity_id=request.opportunity_id,
            status=status,
            spent_usd=metrics.spent_usd,
            revenue_usd=request.revenue_usd,
            net_usd=metrics.net_usd,
            roi_percent=metrics.roi_percent,
            time_spent_hours=request.time_spent_hours,
            success_metric_status="met" if request.success_metric_met else "not_met",
            stop_condition_status=(
                "triggered" if request.stop_condition_triggered else "not_triggered"
            ),
            evidence_quality=metrics.evidence_quality,
            lessons=lessons,
            decision=decision,
            recommended_next_actions=next_actions,
            new_blocklist_patterns=new_blocklist_patterns,
            scoring_feedback=scoring_feedback,
            budget_feedback=budget_feedback,
            policy_feedback=policy_feedback,
            evidence_archive_ids=[archived.evidence_id, *request.evidence_archive_ids],
            ledger_record=ledger_record,
        )
