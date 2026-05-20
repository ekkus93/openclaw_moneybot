"""Default MoneyBot workflow orchestration."""

from __future__ import annotations

import json
from collections.abc import Mapping

from openclaw_moneybot.orchestration.models import DryRunMissionRequest, DryRunMissionResult
from openclaw_moneybot.shared.types import (
    ActionType,
    BudgetDecisionType,
    PolicyDecisionType,
    RecordType,
)
from openclaw_moneybot.skills.budget_and_roi_planner import BudgetAndRoiPlanner, BudgetPlanRequest
from openclaw_moneybot.skills.budget_and_roi_planner.models import BudgetPlanResult
from openclaw_moneybot.skills.email_drafter import EmailDrafter, EmailDraftRequest
from openclaw_moneybot.skills.experiment_reviewer import ExperimentReviewer, ExperimentReviewRequest
from openclaw_moneybot.skills.experiment_reviewer.models import ExperimentReviewResult
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.moneybot_policy_guard import MoneyBotPolicyGuard, PolicyCheckRequest
from openclaw_moneybot.skills.moneybot_policy_guard.models import PolicyCheckResult
from openclaw_moneybot.skills.opportunity_scout import OpportunityScout, OpportunityScoutRequest
from openclaw_moneybot.skills.opportunity_scout.models import (
    OpportunityCandidate,
    ScoutSourceDocument,
)
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    EvidenceArchiveRequest,
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.tos_legal_checker import TosLegalChecker, TosLegalCheckRequest
from openclaw_moneybot.skills.tos_legal_checker.models import TosLegalCheckResult
from openclaw_moneybot.skills.wallet_governor_client import (
    WalletGovernorClientSkill,
    WalletQuoteSkillRequest,
    WalletSpendRequest,
)
from openclaw_moneybot.skills.wallet_governor_client.models import (
    WalletQuoteSkillResult,
    WalletSpendResult,
)
from openclaw_moneybot.utils.ids import make_id


class MoneyBotOrchestrator:
    """Wire the default workflow into a deterministic dry-run."""

    def __init__(
        self,
        *,
        ledger_service: LedgerService,
        scout: OpportunityScout,
        policy_guard: MoneyBotPolicyGuard,
        tos_checker: TosLegalChecker,
        budget_planner: BudgetAndRoiPlanner,
        email_drafter: EmailDrafter,
        wallet_client: WalletGovernorClientSkill,
        reviewer: ExperimentReviewer,
        archiver: ReceiptAndEvidenceArchiver,
    ) -> None:
        self.ledger_service = ledger_service
        self.scout = scout
        self.policy_guard = policy_guard
        self.tos_checker = tos_checker
        self.budget_planner = budget_planner
        self.email_drafter = email_drafter
        self.wallet_client = wallet_client
        self.reviewer = reviewer
        self.archiver = archiver

    @staticmethod
    def _wallet_handoff_float(wallet_handoff: Mapping[str, object], key: str) -> float:
        value = wallet_handoff[key]
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            return float(value)
        msg = f"wallet handoff value for {key} must be numeric"
        raise ValueError(msg)

    @staticmethod
    def _wallet_handoff_str(wallet_handoff: Mapping[str, object], key: str) -> str:
        value = wallet_handoff[key]
        if isinstance(value, str):
            return value
        msg = f"wallet handoff value for {key} must be a string"
        raise ValueError(msg)

    def run_dry_run(self, request: DryRunMissionRequest) -> DryRunMissionResult:
        """Execute the default workflow in dry-run mode."""
        scout_result = self.scout.evaluate(
            OpportunityScoutRequest(
                mission=request.mission,
                source_documents=request.source_documents,
            )
        )
        if not scout_result.opportunities:
            msg = "No viable opportunities were found for the mission."
            raise ValueError(msg)
        candidate = scout_result.opportunities[0]
        self.ledger_service.create_opportunity(
            candidate.ledger_record,
            idempotency_key=f"opportunity:{candidate.opportunity_id}",
        )
        evidence_ids = [self._archive_source_document(candidate, request.source_documents)]

        initial_policy = self.policy_guard.evaluate(self._make_initial_policy_request(candidate))
        self.ledger_service.record_policy_decision(
            initial_policy.ledger_record,
            idempotency_key=f"policy:{initial_policy.ledger_record.policy_decision_id}",
        )
        if initial_policy.decision is not PolicyDecisionType.ALLOW:
            return self._finalize_result(
                request=request,
                candidate=candidate,
                evidence_ids=evidence_ids,
                initial_policy=initial_policy,
                status=initial_policy.decision.value,
                stop_stage="initial_policy",
                stop_reason=(
                    initial_policy.human_review_reason
                    or initial_policy.notes
                    or next(iter(initial_policy.blocked_reasons), None)
                ),
            )

        tos_result = self.tos_checker.evaluate(
            TosLegalCheckRequest.model_validate(
                {
                    **candidate.tos_handoff,
                    "evidence_archive_ids": evidence_ids,
                }
            )
        )
        if tos_result.decision != "proceed":
            return self._finalize_result(
                request=request,
                candidate=candidate,
                evidence_ids=evidence_ids,
                initial_policy=initial_policy,
                tos_result=tos_result,
                status=tos_result.decision,
                stop_stage="tos_legal",
                stop_reason=tos_result.tos_risk_summary,
            )
        budget_result = self.budget_planner.evaluate(
            BudgetPlanRequest(
                opportunity_id=candidate.opportunity_id,
                opportunity_name=candidate.name,
                tos_legal_check_id=tos_result.ledger_record.tos_legal_check_id,
                tos_legal_decision=tos_result.decision,
                policy_decision_id=initial_policy.ledger_record.policy_decision_id,
                policy_decision=initial_policy.decision.value,
                proposed_action=f"Pursue {candidate.name} within the approved plan.",
                required_spend_usd=candidate.required_spend_usd,
                max_loss_usd=max(candidate.max_loss_usd, candidate.required_spend_usd),
                estimated_revenue_usd=candidate.estimated_revenue_high_usd,
                estimated_time_hours=candidate.estimated_time_hours,
                fees_usd=0.0,
                recurring_costs_usd=0.0,
                recurring_cost_cap_usd=0.0,
                asset="BTC",
                wallet_balance_usd=request.wallet_balance_usd,
                daily_spend_remaining_usd=request.daily_spend_remaining_usd,
                evidence_archive_ids=evidence_ids,
                approved_spend_categories=["purchase"],
                success_metric=f"Receive the expected outcome from {candidate.name}.",
                stop_condition="Stop if dry-run validation fails or platform requirements change.",
                timebox_hours=max(candidate.estimated_time_hours, 1.0),
            )
        )
        if budget_result.budget_plan.decision is not BudgetDecisionType.EXECUTE_REQUEST:
            return self._finalize_result(
                request=request,
                candidate=candidate,
                evidence_ids=evidence_ids,
                initial_policy=initial_policy,
                tos_result=tos_result,
                budget_result=budget_result,
                status=budget_result.budget_plan.decision.value,
                stop_stage="budget",
                stop_reason=next(iter(budget_result.budget_plan.reasons), None),
                review_enabled=True,
            )

        execution_policy = self.policy_guard.evaluate(
            self._make_execution_policy_request(
                candidate=candidate,
                budget_plan_id=budget_result.budget_plan.budget_plan_id,
                initial_policy_decision_id=initial_policy.ledger_record.policy_decision_id,
                tos_legal_check_id=tos_result.ledger_record.tos_legal_check_id,
                send_email=request.draft_recipient_email is not None,
                enable_wallet_payment=request.enable_wallet_payment,
                payment_counterparty=request.payment_counterparty,
            )
        )
        execution_policy_write = self.ledger_service.record_policy_decision(
            execution_policy.ledger_record,
            idempotency_key=f"policy:{execution_policy.ledger_record.policy_decision_id}",
        )
        if execution_policy.decision is not PolicyDecisionType.ALLOW:
            return self._finalize_result(
                request=request,
                candidate=candidate,
                evidence_ids=evidence_ids,
                initial_policy=initial_policy,
                tos_result=tos_result,
                budget_result=budget_result,
                execution_policy=execution_policy,
                status=execution_policy.decision.value,
                stop_stage="execution_policy",
                stop_reason=(
                    execution_policy.human_review_reason
                    or execution_policy.notes
                    or next(iter(execution_policy.blocked_reasons), None)
                ),
                review_enabled=True,
            )

        email_draft_id: str | None = None
        if request.draft_recipient_email is not None:
            email_result = self.email_drafter.draft(
                EmailDraftRequest(
                    opportunity_id=candidate.opportunity_id,
                    purpose="bounty_application",
                    recipient_name=request.draft_recipient_name,
                    recipient_email=request.draft_recipient_email,
                    recipient_organization=candidate.name,
                    context_summary=f"Dry-run outreach for {candidate.name}.",
                    source_url=candidate.source_url,
                    policy_decision_id=execution_policy.ledger_record.policy_decision_id,
                    policy_decision=execution_policy.decision.value,
                    tos_legal_check_id=tos_result.ledger_record.tos_legal_check_id,
                    tos_legal_decision=tos_result.decision,
                    allowed_claims=[candidate.why_this_is_legitimate],
                    requested_call_to_action=(
                        "Confirm the submission expectations for this opportunity."
                    ),
                )
            )
            email_draft_id = email_result.email_draft_id
            evidence_ids.extend(email_result.evidence_archive_ids)

        wallet_quote = None
        wallet_result = None
        if budget_result.wallet_handoff is not None:
            quote_amount_usd = self._wallet_handoff_float(
                budget_result.wallet_handoff,
                "amount_usd",
            )
            quote_asset = self._wallet_handoff_str(budget_result.wallet_handoff, "asset")
            wallet_quote = self.wallet_client.quote(
                WalletQuoteSkillRequest(
                    asset=quote_asset,
                    amount_usd=quote_amount_usd,
                    destination=request.payment_destination,
                    btc_usd_rate=request.btc_usd_rate,
                )
            )
            if (
                request.enable_wallet_payment
                and execution_policy.decision is PolicyDecisionType.ALLOW
                and wallet_quote.status == "ok"
            ):
                wallet_result = self.wallet_client.spend(
                    WalletSpendRequest(
                        opportunity_id=candidate.opportunity_id,
                        policy_decision_id=execution_policy.ledger_record.policy_decision_id,
                        budget_plan_id=budget_result.budget_plan.budget_plan_id,
                        tos_legal_check_id=tos_result.ledger_record.tos_legal_check_id,
                        ledger_event_id=execution_policy_write.ledger_event_id,
                        amount_usd=quote_amount_usd,
                        asset=quote_asset,
                        destination=request.payment_destination,
                        counterparty=request.payment_counterparty,
                        purpose=request.payment_purpose,
                        category="purchase",
                        evidence_archive_ids=evidence_ids,
                        btc_usd_rate=request.btc_usd_rate,
                        idempotency_key=f"mission:{candidate.opportunity_id}",
                    )
                )
                if wallet_result.raw_response_evidence_id is not None:
                    evidence_ids.append(wallet_result.raw_response_evidence_id)
        return self._finalize_result(
            request=request,
            candidate=candidate,
            evidence_ids=evidence_ids,
            initial_policy=initial_policy,
            tos_result=tos_result,
            budget_result=budget_result,
            execution_policy=execution_policy,
            email_draft_id=email_draft_id,
            wallet_quote=wallet_quote,
            wallet_result=wallet_result,
            status="completed",
            review_enabled=True,
        )

    def _finalize_result(
        self,
        *,
        request: DryRunMissionRequest,
        candidate: OpportunityCandidate,
        evidence_ids: list[str],
        initial_policy: PolicyCheckResult,
        tos_result: TosLegalCheckResult | None = None,
        budget_result: BudgetPlanResult | None = None,
        execution_policy: PolicyCheckResult | None = None,
        email_draft_id: str | None = None,
        wallet_quote: WalletQuoteSkillResult | None = None,
        wallet_result: WalletSpendResult | None = None,
        status: str,
        stop_stage: str | None = None,
        stop_reason: str | None = None,
        review_enabled: bool = False,
    ) -> DryRunMissionResult:
        workflow_evidence = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.OPPORTUNITY,
                related_id=candidate.opportunity_id,
                evidence_type="workflow_summary",
                content_text=json.dumps(
                    {
                        "mission": request.mission,
                        "candidate": candidate.name,
                        "dry_run": not request.enable_wallet_payment,
                        "status": status,
                        "stop_stage": stop_stage,
                        "stop_reason": stop_reason,
                        "initial_policy_decision": initial_policy.decision.value,
                        "tos_decision": None if tos_result is None else tos_result.decision,
                        "budget_decision": (
                            None
                            if budget_result is None
                            else budget_result.budget_plan.decision.value
                        ),
                        "execution_policy_decision": (
                            None
                            if execution_policy is None
                            else execution_policy.decision.value
                        ),
                        "wallet_quote_status": (
                            None if wallet_quote is None else wallet_quote.status
                        ),
                        "wallet_result_status": (
                            None if wallet_result is None else wallet_result.status
                        ),
                    },
                    indent=2,
                    sort_keys=True,
                ),
                notes="Dry-run workflow summary",
            )
        )
        final_evidence_ids = [*evidence_ids, workflow_evidence.evidence_id]
        review_result: ExperimentReviewResult | None = None
        if review_enabled and budget_result is not None:
            review_result = self.reviewer.review(
                ExperimentReviewRequest(
                    opportunity_id=candidate.opportunity_id,
                    budget_plan_id=budget_result.budget_plan.budget_plan_id,
                    review_reason="dry_run",
                    current_date=request.current_date,
                    revenue_usd=request.observed_revenue_usd,
                    time_spent_hours=request.time_spent_hours,
                    success_metric_met=request.observed_revenue_usd > 0,
                    stop_condition_triggered=status != "completed",
                    evidence_archive_ids=final_evidence_ids,
                    manual_notes="Automated workflow dry run",
                )
            )
            final_evidence_ids = review_result.evidence_archive_ids
        timeline = self.ledger_service.get_opportunity_timeline(candidate.opportunity_id)
        return DryRunMissionResult(
            mission=request.mission,
            selected_opportunity_id=candidate.opportunity_id,
            initial_policy_decision_id=initial_policy.ledger_record.policy_decision_id,
            tos_legal_check_id=(
                None if tos_result is None else tos_result.ledger_record.tos_legal_check_id
            ),
            budget_plan_id=(
                None if budget_result is None else budget_result.budget_plan.budget_plan_id
            ),
            execution_policy_decision_id=(
                None
                if execution_policy is None
                else execution_policy.ledger_record.policy_decision_id
            ),
            email_draft_id=email_draft_id,
            wallet_quote=wallet_quote,
            wallet_result=wallet_result,
            experiment_review_id=(
                None if review_result is None else review_result.experiment_review_id
            ),
            evidence_archive_ids=final_evidence_ids,
            timeline=timeline,
            status=status,
            stop_stage=stop_stage,
            stop_reason=stop_reason,
            dry_run=not request.enable_wallet_payment,
        )

    def _archive_source_document(
        self,
        candidate: OpportunityCandidate,
        source_documents: list[ScoutSourceDocument],
    ) -> str:
        source_document = next(
            (
                item
                for item in source_documents
                if str(item.source_url) == str(candidate.source_url)
            ),
            None,
        )
        content_text = candidate.ledger_record.summary or candidate.name
        if source_document is not None:
            content_text = source_document.content_text
        archived = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.OPPORTUNITY,
                related_id=candidate.opportunity_id,
                evidence_type="source_document",
                content_text=content_text,
                source_url=candidate.source_url,
                notes="Opportunity source captured for workflow",
            )
        )
        return archived.evidence_id

    @staticmethod
    def _make_initial_policy_request(candidate: OpportunityCandidate) -> PolicyCheckRequest:
        return PolicyCheckRequest(
            action_id=make_id("action"),
            action_type=ActionType.RESEARCH,
            title=f"Initial review for {candidate.name}",
            description=f"Review the {candidate.category} opportunity before planning execution.",
            category="opportunity_analysis",
            counterparty=candidate.name,
            amount_usd=candidate.required_spend_usd,
            asset="BTC",
            source_urls=[candidate.source_url],
            planned_tools=["ledger_skill", "tos_legal_checker"],
            user_approval_present=True,
            requires_payment=False,
            requires_wallet_action=False,
            metadata={
                "opportunity_id": candidate.opportunity_id,
                "original_opportunity_category": candidate.category,
            },
        )

    @staticmethod
    def _make_execution_policy_request(
        *,
        candidate: OpportunityCandidate,
        budget_plan_id: str,
        initial_policy_decision_id: str,
        tos_legal_check_id: str,
        send_email: bool,
        enable_wallet_payment: bool,
        payment_counterparty: str,
    ) -> PolicyCheckRequest:
        if enable_wallet_payment and candidate.required_spend_usd > 0:
            action_type = ActionType.PURCHASE
            category = "purchase"
        elif send_email:
            action_type = ActionType.EMAIL
            category = "draft_email"
        else:
            action_type = ActionType.RESEARCH
            category = "research"
        return PolicyCheckRequest(
            action_id=make_id("action"),
            action_type=action_type,
            title=f"Execute plan for {candidate.name}",
            description=f"Execute the bounded workflow for {candidate.name}.",
            category=category,
            counterparty=payment_counterparty if enable_wallet_payment else candidate.name,
            amount_usd=candidate.required_spend_usd,
            asset="BTC",
            source_urls=[candidate.source_url],
            planned_tools=[
                "ledger_skill",
                "email_drafter" if send_email else "receipt_and_evidence_archiver",
                "wallet_governor_client" if enable_wallet_payment else "dry_run",
            ],
            user_approval_present=True,
            requires_payment=enable_wallet_payment and candidate.required_spend_usd > 0,
            requires_email_send=send_email,
            requires_wallet_action=enable_wallet_payment and candidate.required_spend_usd > 0,
            metadata={
                "opportunity_id": candidate.opportunity_id,
                "budget_plan_id": budget_plan_id,
                "policy_decision_id": initial_policy_decision_id,
                "tos_legal_check_id": tos_legal_check_id,
                "ledger_record_id": budget_plan_id,
                "original_opportunity_category": candidate.category,
            },
        )
