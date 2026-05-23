"""Integration tests for the default workflow."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from openclaw_moneybot.orchestration import DryRunMissionRequest
from openclaw_moneybot.plugins.inner_voice_plugin import (
    ArbiterService,
    DebateResponderOutput,
    DebateResponderRequest,
    InnerVoiceCoordinator,
    InnerVoiceDebateRequest,
    InnerVoicePlugin,
)
from openclaw_moneybot.shared import ArbiterConfig, ArchiveConfig, InnerVoiceConfig
from openclaw_moneybot.shared.types import (
    ArbiterFinalResolution,
    InnerVoiceDisposition,
    InnerVoiceObjectionSeverity,
    InnerVoiceStage,
    InnerVoiceSubjectType,
    PolicyDecisionType,
    ProviderName,
    RecordType,
    ReviewDecisionType,
)
from openclaw_moneybot.skills.budget_and_roi_planner import BudgetAndRoiPlanner
from openclaw_moneybot.skills.budget_and_roi_planner.models import (
    BudgetPlanRequest,
    BudgetPlanResult,
)
from openclaw_moneybot.skills.deliverable_quality_checker import DeliverableArtifact
from openclaw_moneybot.skills.experiment_reviewer import ExperimentReviewRequest
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.moneybot_policy_guard import MoneyBotPolicyGuard
from openclaw_moneybot.skills.moneybot_policy_guard.models import (
    PolicyCheckRequest,
    PolicyCheckResult,
)
from openclaw_moneybot.skills.wallet_governor_client.models import (
    WalletLimitCheck,
    WalletQuoteSkillRequest,
    WalletQuoteSkillResult,
    WalletSpendRequest,
    WalletSpendResult,
)

from .helpers import (
    make_archive_config,
    make_orchestrator,
    make_policy_config,
    make_source_document,
)


class PolicyGuardWithCategoryOverride:
    """Wrap the policy guard and override category on selected calls."""

    def __init__(
        self,
        policy_guard: MoneyBotPolicyGuard,
        *,
        first_category: str | None = None,
        second_category: str | None = None,
    ) -> None:
        self.policy_guard = policy_guard
        self.first_category = first_category
        self.second_category = second_category
        self.call_count = 0

    def evaluate(self, request: PolicyCheckRequest) -> PolicyCheckResult:
        self.call_count += 1
        updated_request = request
        if self.call_count == 1 and self.first_category is not None:
            updated_request = request.model_copy(update={"category": self.first_category})
        if self.call_count == 2 and self.second_category is not None:
            updated_request = request.model_copy(update={"category": self.second_category})
        return self.policy_guard.evaluate(updated_request)


class BudgetPlannerWithUnknownFees:
    """Wrap the budget planner and force a human-review outcome."""

    def __init__(self, planner: BudgetAndRoiPlanner) -> None:
        self.planner = planner

    def evaluate(self, request: BudgetPlanRequest) -> BudgetPlanResult:
        updated_request = request.model_copy(update={"fees_usd": None})
        return self.planner.evaluate(updated_request)


def make_request(**overrides: object) -> DryRunMissionRequest:
    payload: dict[str, object] = {
        "mission": "Integration workflow mission.",
        "source_documents": [
            make_source_document(extra_text="Requires $5 spend. Payout is up to $25.")
        ],
        "current_date": datetime(2026, 1, 2, tzinfo=UTC),
    }
    payload.update(overrides)
    return DryRunMissionRequest.model_validate(payload)


def make_inner_voice_plugin(
    tmp_path: Path,
    ledger_service: LedgerService,
    *,
    run_after_stages: list[InnerVoiceStage],
    handler: httpx.BaseTransport,
    require_for_spend: bool = True,
) -> InnerVoicePlugin:
    return InnerVoicePlugin(
        InnerVoiceConfig(
            enabled=True,
            provider=ProviderName.OLLAMA,
            model_name="inner-voice-test",
            base_url="http://127.0.0.1:11434",
            run_after_stages=run_after_stages,
            require_for_spend=require_for_spend,
        ),
        ArchiveConfig(base_directory=make_archive_config(tmp_path).base_directory),
        ledger_service,
        transport=handler,
    )


def make_arbiter_service(
    tmp_path: Path,
    ledger_service: LedgerService,
    *,
    handler: httpx.BaseTransport,
) -> ArbiterService:
    return ArbiterService(
        ArbiterConfig(
            provider=ProviderName.LLAMA_SERVER,
            model_name="arbiter-test",
            base_url="http://127.0.0.1:8080/v1",
            allow_hosted_provider=False,
            allow_non_local_provider=False,
        ),
        ArchiveConfig(base_directory=make_archive_config(tmp_path).base_directory),
        ledger_service,
        transport=handler,
    )


class StaticResponder:
    def __init__(self, outputs: list[DebateResponderOutput]) -> None:
        self._outputs = iter(outputs)

    def respond_to_debate(self, request: DebateResponderRequest) -> DebateResponderOutput:
        return next(self._outputs)


def test_dry_run_workflow_creates_full_trail(tmp_path: Path) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        make_request(
            mission="Review one bounded bounty.",
            draft_recipient_email="maintainer@example.com",
            draft_recipient_name="Maintainer",
            enable_wallet_payment=False,
        )
    )

    event_types = {item.event_type for item in result.timeline}

    assert result.status == "completed"
    assert result.stop_stage is None
    assert result.dry_run is True
    assert result.wallet_quote is not None
    assert result.wallet_result is None
    assert result.email_draft_id is not None
    assert result.experiment_review_id is not None
    assert {
        "opportunity",
        "policy_decision",
        "tos_legal_check",
        "budget_plan",
        "email_draft",
        "experiment_review",
    } <= event_types
    assert result.evidence_archive_ids


def test_workflow_runs_configured_inner_voice_review_after_budget(tmp_path: Path) -> None:
    def inner_voice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"overall_assessment":"Proceed, but collect one more receipt.",'
                        '"recommended_disposition":"proceed_with_followups",'
                        '"confidence_adjustment":0,'
                        '"objections":[{"title":"Receipt gap","severity":"low",'
                        '"reason":"A payout receipt should still be archived."}],'
                        '"missing_evidence":["payout receipt"],'
                        '"stale_information_risks":[],'
                        '"overlooked_constraints":[],'
                        '"counterarguments":[],'
                        '"recommended_followups":["archive payout receipt"]}'
                    )
                },
                "done_reason": "stop",
            },
        )

    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=False)
    orchestrator.inner_voice_plugin = make_inner_voice_plugin(
        tmp_path,
        ledger_service,
        run_after_stages=[InnerVoiceStage.BUDGET_PLANNING],
        handler=httpx.MockTransport(inner_voice_handler),
    )

    result = orchestrator.run_dry_run(make_request(enable_wallet_payment=False))

    assert result.status == "completed"
    assert result.inner_voice_review_ids
    review_evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.INNER_VOICE_REVIEW,
        related_id=result.inner_voice_review_ids[0],
    )
    assert {item.evidence_type for item in review_evidence} >= {
        "inner_voice_prompt",
        "inner_voice_response",
    }


def test_required_pre_execution_inner_voice_failure_stops_wallet_path(tmp_path: Path) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=True)
    orchestrator.inner_voice_plugin = make_inner_voice_plugin(
        tmp_path,
        ledger_service,
        run_after_stages=[InnerVoiceStage.PRE_EXECUTION],
        handler=httpx.MockTransport(lambda request: httpx.Response(500)),
    )

    result = orchestrator.run_dry_run(
        make_request(
            enable_wallet_payment=True,
            draft_recipient_email="maintainer@example.com",
            draft_recipient_name="Maintainer",
        )
    )

    assert result.status == "needs_review"
    assert result.stop_stage == "inner_voice_pre_execution"
    assert result.wallet_result is None


def test_required_pre_execution_inner_voice_stage_missing_stops_wallet_path(tmp_path: Path) -> None:
    def inner_voice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "{}"}, "done_reason": "stop"})

    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=True)
    orchestrator.inner_voice_plugin = make_inner_voice_plugin(
        tmp_path,
        ledger_service,
        run_after_stages=[InnerVoiceStage.BUDGET_PLANNING],
        handler=httpx.MockTransport(inner_voice_handler),
    )

    result = orchestrator.run_dry_run(
        make_request(
            enable_wallet_payment=True,
            draft_recipient_email="maintainer@example.com",
            draft_recipient_name="Maintainer",
        )
    )

    assert result.status == "needs_review"
    assert result.stop_stage == "inner_voice_pre_execution"
    assert result.stop_reason is not None
    assert "required inner voice stage pre_execution" in result.stop_reason
    assert result.wallet_result is None


def test_spend_path_debate_can_return_followup_gated_result(tmp_path: Path) -> None:
    def inner_voice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"turn_type":"objection",'
                        '"message_text":"Use a refreshed receipt before sending funds.",'
                        '"cited_evidence_ids":["ev_2"],'
                        '"disposition_signal":"needs_review",'
                        '"max_unresolved_severity":"high",'
                        '"request_arbiter":false}'
                    )
                },
                "done_reason": "stop",
            },
        )

    def arbiter_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": (
                                '{"final_resolution":"proceed_with_followups",'
                                '"prevailing_side":"mixed",'
                                '"resolution_summary":"Proceed only after refreshing the receipt.",'
                                '"rationale_summary":"The spend can continue once '
                                'the proof is refreshed.",'
                                '"required_followups":["refresh payout receipt"],'
                                '"unresolved_risks":["stale receipt"]}'
                            )
                        },
                    }
                ]
            },
        )

    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=True)
    plugin = make_inner_voice_plugin(
        tmp_path,
        ledger_service,
        run_after_stages=[InnerVoiceStage.PRE_EXECUTION],
        handler=httpx.MockTransport(inner_voice_handler),
    )
    arbiter = make_arbiter_service(
        tmp_path,
        ledger_service,
        handler=httpx.MockTransport(arbiter_handler),
    )
    coordinator = InnerVoiceCoordinator(plugin, arbiter, plugin.archiver, ledger_service)
    orchestrator.inner_voice_plugin = plugin
    orchestrator.arbiter_service = arbiter
    orchestrator.inner_voice_coordinator = coordinator

    outcome = orchestrator.resolve_model_disagreement(
        InnerVoiceDebateRequest(
            stage=InnerVoiceStage.PRE_EXECUTION,
            subject_type=InnerVoiceSubjectType.EXECUTION_STEP,
            subject_id="wallet_step_001",
            review_goal="Resolve the pre-execution spend disagreement.",
            claim_summary="Proceed with the approved wallet spend.",
            disagreement_summary="Send now or require one more receipt refresh first.",
            openclaw_initial_position="Proceed with the approved wallet spend now.",
            openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
            openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
            max_debate_rounds=1,
        ),
        openclaw=StaticResponder([]),
    )

    interpretation = orchestrator.interpret_model_disagreement(outcome)

    assert interpretation.final_status == "proceed_with_followups"
    assert interpretation.required_followups == ["refresh payout receipt"]
    assert interpretation.transcript_archive_ids


def test_irreversible_action_debate_can_stop_auto_advance(tmp_path: Path) -> None:
    def inner_voice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"turn_type":"objection",'
                        '"message_text":"Do not submit until the irreversible step is reviewed.",'
                        '"cited_evidence_ids":["ev_3"],'
                        '"disposition_signal":"needs_review",'
                        '"max_unresolved_severity":"high",'
                        '"request_arbiter":false}'
                    )
                },
                "done_reason": "stop",
            },
        )

    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=False)
    plugin = make_inner_voice_plugin(
        tmp_path,
        ledger_service,
        run_after_stages=[InnerVoiceStage.PRE_EXECUTION],
        handler=httpx.MockTransport(inner_voice_handler),
    )
    arbiter = make_arbiter_service(
        tmp_path,
        ledger_service,
        handler=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "content": (
                                    '{"final_resolution":"block_pending_checks",'
                                    '"prevailing_side":"inner_voice",'
                                    '"resolution_summary":"Pause the irreversible step.",'
                                    '"rationale_summary":"The remaining risk is too high.",'
                                    '"required_followups":["perform manual review"],'
                                    '"unresolved_risks":["irreversible action risk"]}'
                                )
                            },
                        }
                    ]
                },
            )
        ),
    )
    coordinator = InnerVoiceCoordinator(plugin, arbiter, plugin.archiver, ledger_service)
    orchestrator.inner_voice_plugin = plugin
    orchestrator.arbiter_service = arbiter
    orchestrator.inner_voice_coordinator = coordinator

    outcome = orchestrator.resolve_model_disagreement(
        InnerVoiceDebateRequest(
            stage=InnerVoiceStage.PRE_EXECUTION,
            subject_type=InnerVoiceSubjectType.EXECUTION_STEP,
            subject_id="submission_step_001",
            review_goal="Resolve the irreversible submission disagreement.",
            claim_summary="Proceed with the irreversible submission step.",
            disagreement_summary="Submit now or stop for manual review.",
            openclaw_initial_position="Proceed with the irreversible submission step.",
            openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
            openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
            max_debate_rounds=1,
        ),
        openclaw=StaticResponder([]),
    )

    interpretation = orchestrator.interpret_model_disagreement(outcome)

    assert interpretation.final_status == "needs_review"
    assert interpretation.stop_stage == "inner_voice_debate"
    assert interpretation.stop_reason == "Pause the irreversible step."


def test_deterministic_policy_still_outranks_arbiter_output(tmp_path: Path) -> None:
    def inner_voice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"turn_type":"objection",'
                        '"message_text":"I disagree but arbitration can resolve it.",'
                        '"cited_evidence_ids":["ev_2"],'
                        '"disposition_signal":"needs_review",'
                        '"max_unresolved_severity":"medium",'
                        '"request_arbiter":false}'
                    )
                },
                "done_reason": "stop",
            },
        )

    def arbiter_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": (
                                '{"final_resolution":"adopt_openclaw",'
                                '"prevailing_side":"openclaw",'
                                '"resolution_summary":"Proceeding would be acceptable '
                                'at the LLM layer.",'
                                '"rationale_summary":"The disagreement is not material.",'
                                '"required_followups":[],'
                                '"unresolved_risks":[]}'
                            )
                        },
                    }
                ]
            },
        )

    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=True)
    plugin = make_inner_voice_plugin(
        tmp_path,
        ledger_service,
        run_after_stages=[InnerVoiceStage.PRE_EXECUTION],
        handler=httpx.MockTransport(inner_voice_handler),
    )
    arbiter = make_arbiter_service(
        tmp_path,
        ledger_service,
        handler=httpx.MockTransport(arbiter_handler),
    )
    coordinator = InnerVoiceCoordinator(plugin, arbiter, plugin.archiver, ledger_service)
    orchestrator.inner_voice_plugin = plugin
    orchestrator.arbiter_service = arbiter
    orchestrator.inner_voice_coordinator = coordinator

    outcome = orchestrator.resolve_model_disagreement(
        InnerVoiceDebateRequest(
            stage=InnerVoiceStage.PRE_EXECUTION,
            subject_type=InnerVoiceSubjectType.EXECUTION_STEP,
            subject_id="wallet_step_002",
            review_goal="Resolve the spend disagreement.",
            claim_summary="Proceed with the approved wallet spend.",
            disagreement_summary="Proceed now or stop.",
            openclaw_initial_position="Proceed with the approved wallet spend now.",
            openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
            openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
            max_debate_rounds=1,
        ),
        openclaw=StaticResponder([]),
    )

    interpretation = orchestrator.interpret_model_disagreement(
        outcome,
        deterministic_status="block",
        deterministic_reason="Policy blocked the purchase category.",
    )

    assert outcome.arbiter_result is not None
    assert outcome.arbiter_result.final_resolution is ArbiterFinalResolution.ADOPT_OPENCLAW
    assert interpretation.final_status == "block"
    assert interpretation.stop_stage == "deterministic_gate"
    assert interpretation.stop_reason == "Policy blocked the purchase category."


def test_initial_policy_block_stops_before_downstream_work(tmp_path: Path) -> None:
    policy_guard = PolicyGuardWithCategoryOverride(
        MoneyBotPolicyGuard(make_policy_config()),
        first_category="gambling",
    )
    orchestrator, ledger_service = make_orchestrator(
        tmp_path,
        spend_enabled=True,
        policy_guard=policy_guard,
    )

    result = orchestrator.run_dry_run(
        make_request(
            mission="Try a blocked category.",
            source_documents=[make_source_document()],
            draft_recipient_email="maintainer@example.com",
            enable_wallet_payment=True,
        )
    )

    assert result.status == "block"
    assert result.stop_stage == "initial_policy"
    assert result.initial_policy_decision_id is not None
    assert result.tos_legal_check_id is None
    assert result.budget_plan_id is None
    assert result.execution_policy_decision_id is None
    assert result.email_draft_id is None
    assert result.experiment_review_id is None
    assert ledger_service.get_opportunity(result.selected_opportunity_id) is not None
    assert ledger_service.get_policy_decision(result.initial_policy_decision_id) is not None
    assert ledger_service.list_email_records_for_opportunity(result.selected_opportunity_id) == []
    assert (
        ledger_service.list_wallet_transactions_for_opportunity(result.selected_opportunity_id)
        == []
    )
    assert result.evidence_archive_ids


def test_eligibility_block_stops_before_policy_and_budget(tmp_path: Path) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        make_request(
            mission="Reject a personal-account-only opportunity.",
            source_documents=[
                make_source_document(extra_text="Requires personal account and PayPal payout.")
            ],
        )
    )

    assert result.status == "blocked"
    assert result.stop_stage == "eligibility"
    assert result.initial_policy_decision_id is None
    assert result.budget_plan_id is None
    assert result.eligibility_id is not None
    assert ledger_service.get_opportunity(result.selected_opportunity_id) is not None


def test_eligibility_review_stops_safely_before_budget(tmp_path: Path) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        make_request(
            mission="Pause for ambiguous KYC requirements.",
            source_documents=[make_source_document(extra_text="Requires KYC tax form.")],
        )
    )

    assert result.status == "needs_review"
    assert result.stop_stage == "eligibility"
    assert result.budget_plan_id is None


def test_initial_policy_needs_review_stops_before_downstream_work(tmp_path: Path) -> None:
    policy_guard = PolicyGuardWithCategoryOverride(
        MoneyBotPolicyGuard(make_policy_config()),
        first_category="affiliate_marketing",
    )
    orchestrator, ledger_service = make_orchestrator(
        tmp_path,
        spend_enabled=False,
        policy_guard=policy_guard,
    )

    result = orchestrator.run_dry_run(
        make_request(
            mission="Try a review-required category.",
            source_documents=[make_source_document()],
        )
    )

    assert result.status == "needs_review"
    assert result.stop_stage == "initial_policy"
    assert result.initial_policy_decision_id is not None
    assert result.tos_legal_check_id is None
    assert result.budget_plan_id is None
    assert result.experiment_review_id is None
    assert ledger_service.get_policy_decision(result.initial_policy_decision_id) is not None
    assert ledger_service.list_email_records_for_opportunity(result.selected_opportunity_id) == []


def test_tos_reject_stops_before_budget_and_execution(tmp_path: Path) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=True)

    result = orchestrator.run_dry_run(
        make_request(
            mission="Review terms that reject automation.",
            source_documents=[make_source_document(extra_text="Automation prohibited. No bots.")],
            draft_recipient_email="maintainer@example.com",
            enable_wallet_payment=True,
        )
    )

    assert result.status == "reject"
    assert result.stop_stage == "tos_legal"
    assert result.tos_legal_check_id is not None
    assert result.budget_plan_id is None
    assert result.execution_policy_decision_id is None
    assert result.experiment_review_id is None
    assert ledger_service.get_tos_legal_check(result.tos_legal_check_id) is not None
    assert ledger_service.list_email_records_for_opportunity(result.selected_opportunity_id) == []
    assert (
        ledger_service.list_wallet_transactions_for_opportunity(result.selected_opportunity_id)
        == []
    )


def test_tos_human_review_stops_before_budget_and_execution(tmp_path: Path) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        make_request(
            mission="Review terms needing clarification.",
            source_documents=[make_source_document(extra_text="Identity verification required.")],
        )
    )

    assert result.status == "human_review"
    assert result.stop_stage == "tos_legal"
    assert result.tos_legal_check_id is not None
    assert result.budget_plan_id is None
    assert result.experiment_review_id is None
    assert ledger_service.get_tos_legal_check(result.tos_legal_check_id) is not None


def test_budget_reject_stops_execution_but_still_records_review(tmp_path: Path) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=True)

    result = orchestrator.run_dry_run(
        make_request(
            mission="Run a plan that exceeds the remaining budget.",
            draft_recipient_email="maintainer@example.com",
            enable_wallet_payment=True,
            wallet_balance_usd=100.0,
            daily_spend_remaining_usd=1.0,
        )
    )

    assert result.status == "reject"
    assert result.stop_stage == "budget"
    assert result.budget_plan_id is not None
    assert result.execution_policy_decision_id is None
    assert result.email_draft_id is None
    assert result.wallet_result is None
    assert result.experiment_review_id is not None
    assert ledger_service.get_budget_plan(result.budget_plan_id) is not None
    assert ledger_service.list_email_records_for_opportunity(result.selected_opportunity_id) == []
    assert (
        ledger_service.list_wallet_transactions_for_opportunity(result.selected_opportunity_id)
        == []
    )


def test_budget_human_review_without_wallet_handoff_allows_non_wallet_review(
    tmp_path: Path,
) -> None:
    planner_ledger = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    budget_planner = BudgetPlannerWithUnknownFees(
        BudgetAndRoiPlanner(make_policy_config(), planner_ledger)
    )
    orchestrator, ledger_service = make_orchestrator(
        tmp_path,
        spend_enabled=False,
        budget_planner=budget_planner,
    )

    result = orchestrator.run_dry_run(make_request(mission="Run a plan with unknown fees."))

    assert result.status == "human_review"
    assert result.stop_stage == "budget"
    assert result.wallet_quote is None
    assert result.wallet_result is None
    assert result.experiment_review_id is not None
    assert ledger_service.get_experiment_review(result.experiment_review_id) is not None


def test_rejected_wallet_quote_prevents_wallet_send(tmp_path: Path) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=True)
    spend_called = False

    def reject_quote(request: WalletQuoteSkillRequest) -> WalletQuoteSkillResult:
        del request
        return WalletQuoteSkillResult(
            status="rejected",
            asset="BTC",
            reason="destination_invalid",
            amount_usd_estimate=5.0,
            estimated_fee_usd=0.0,
            limit_check=WalletLimitCheck(
                single_spend_ok=False,
                daily_spend_ok=False,
                weekly_spend_ok=False,
                wallet_balance_ok=False,
            ),
            rejection_reasons=["destination_invalid"],
            raw_response={"status": "rejected", "reason": "destination_invalid"},
        )

    def mark_spend(request: WalletSpendRequest) -> WalletSpendResult:
        nonlocal spend_called
        del request
        spend_called = True
        raise AssertionError("wallet send should not be called after a rejected quote")

    orchestrator.wallet_client.quote = reject_quote  # type: ignore[method-assign]
    orchestrator.wallet_client.spend = mark_spend  # type: ignore[method-assign]

    result = orchestrator.run_dry_run(
        make_request(
            mission="Attempt a payment with a rejected quote.",
            enable_wallet_payment=True,
        )
    )

    assert result.wallet_quote is not None
    assert result.wallet_quote.status == "rejected"
    assert result.wallet_result is None
    assert spend_called is False
    assert (
        ledger_service.list_wallet_transactions_for_opportunity(result.selected_opportunity_id)
        == []
    )


def test_execution_policy_block_stops_email_and_wallet(tmp_path: Path) -> None:
    policy_guard = PolicyGuardWithCategoryOverride(
        MoneyBotPolicyGuard(make_policy_config()),
        second_category="gambling",
    )
    orchestrator, ledger_service = make_orchestrator(
        tmp_path,
        spend_enabled=True,
        policy_guard=policy_guard,
    )

    result = orchestrator.run_dry_run(
        make_request(
            mission="Block the concrete execution plan.",
            draft_recipient_email="maintainer@example.com",
            enable_wallet_payment=True,
        )
    )

    assert result.status == "block"
    assert result.stop_stage == "execution_policy"
    assert result.execution_policy_decision_id is not None
    assert result.email_draft_id is None
    assert result.wallet_result is None
    assert result.experiment_review_id is not None
    assert ledger_service.get_policy_decision(result.execution_policy_decision_id) is not None
    assert ledger_service.list_email_records_for_opportunity(result.selected_opportunity_id) == []
    assert (
        ledger_service.list_wallet_transactions_for_opportunity(result.selected_opportunity_id)
        == []
    )


def test_profitable_workflow_leaves_traceable_review_and_email_artifacts(
    tmp_path: Path,
) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=True)

    result = orchestrator.run_dry_run(
        make_request(
            mission="Run one profitable reviewed mission.",
            draft_recipient_email="maintainer@example.com",
            draft_recipient_name="Maintainer",
            enable_wallet_payment=False,
            observed_revenue_usd=30.0,
        )
    )

    assert result.experiment_review_id is not None
    review = ledger_service.get_experiment_review(result.experiment_review_id)
    review_evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.EXPERIMENT_REVIEW,
        related_id=result.experiment_review_id,
    )
    snapshot_payload = json.loads(Path(review_evidence[0].archive_path).read_text(encoding="utf-8"))

    assert result.status == "completed"
    assert result.wallet_result is None
    assert result.email_draft_id is not None
    assert review is not None
    assert review.decision is ReviewDecisionType.CONTINUE
    assert ledger_service.list_email_records_for_opportunity(result.selected_opportunity_id)
    assert snapshot_payload["wallet_transaction_ids"] == []
    assert result.email_draft_id in snapshot_payload["email_draft_ids"]


def test_approved_workflow_produces_submission_package_and_reconciliation(tmp_path: Path) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        make_request(
            source_documents=[
                make_source_document(
                    extra_text=(
                        "Required fields: name, email\n"
                        "Attachments: screenshot\n"
                        "Submit at https://example.com/submit\n"
                        "Deadline: 2026-01-05"
                    )
                )
            ],
            submission_field_values={"name": "Maintainer", "email": "maintainer@example.com"},
            submission_artifacts=[
                DeliverableArtifact(
                    artifact_name="screenshot",
                    content_text="real screenshot evidence",
                    evidence_archive_id="artifact_manual",
                )
            ],
            observed_revenue_usd=25.0,
        )
    )

    assert result.status == "completed"
    assert result.submission_package_id is not None
    assert result.deliverable_quality_id is not None
    assert result.payout_reconciliation_id is not None
    assert result.strategy_summary_id is not None


def test_execution_stops_when_submission_package_has_unresolved_items(tmp_path: Path) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        make_request(
            source_documents=[
                make_source_document(
                    extra_text="Please complete the required fields before submitting."
                )
            ]
        )
    )

    assert result.status == "needs_review"
    assert result.stop_stage == "submission_package"
    assert result.submission_package_id is not None
    assert result.experiment_review_id is not None
    assert ledger_service.get_experiment_review(result.experiment_review_id) is not None


def test_missing_payout_creates_reconciliation_and_review_linkage(tmp_path: Path) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(make_request())

    assert result.payout_reconciliation_id is not None
    assert result.experiment_review_id is not None
    assert result.status == "completed"


def test_followup_review_of_costly_execution_with_missing_evidence_requires_human_review(
    tmp_path: Path,
) -> None:
    orchestrator, ledger_service = make_orchestrator(tmp_path, spend_enabled=True)
    workflow_result = orchestrator.run_dry_run(
        make_request(
            mission="Run one costly ambiguous mission.",
            enable_wallet_payment=True,
            observed_revenue_usd=0.0,
        )
    )
    assert workflow_result.budget_plan_id is not None

    review_result = orchestrator.reviewer.review(
        ExperimentReviewRequest(
            opportunity_id=workflow_result.selected_opportunity_id,
            budget_plan_id=workflow_result.budget_plan_id,
            review_reason="followup_missing_evidence",
            current_date=datetime(2026, 1, 3, tzinfo=UTC),
            revenue_usd=0.0,
            time_spent_hours=2.0,
            success_metric_met=False,
            stop_condition_triggered=False,
            evidence_archive_ids=[],
        )
    )
    review_evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.EXPERIMENT_REVIEW,
        related_id=review_result.experiment_review_id,
    )
    snapshot_payload = json.loads(Path(review_evidence[0].archive_path).read_text(encoding="utf-8"))

    assert review_result.decision is ReviewDecisionType.HUMAN_REVIEW
    assert snapshot_payload["spend_request_ids"]
    assert snapshot_payload["wallet_transaction_ids"]


def test_followup_review_of_incident_flagged_execution_stops(tmp_path: Path) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=True)
    workflow_result = orchestrator.run_dry_run(
        make_request(
            mission="Run one incident-flagged mission.",
            enable_wallet_payment=True,
            observed_revenue_usd=0.0,
        )
    )
    assert workflow_result.budget_plan_id is not None

    review_result = orchestrator.reviewer.review(
        ExperimentReviewRequest(
            opportunity_id=workflow_result.selected_opportunity_id,
            budget_plan_id=workflow_result.budget_plan_id,
            review_reason="followup_incident",
            current_date=datetime(2026, 1, 3, tzinfo=UTC),
            revenue_usd=0.0,
            time_spent_hours=2.0,
            success_metric_met=False,
            stop_condition_triggered=True,
            evidence_archive_ids=workflow_result.evidence_archive_ids,
            incident_flags=["legal_red_flag"],
        )
    )

    assert review_result.decision is ReviewDecisionType.STOP


def test_execution_policy_needs_review_stops_email_and_wallet(tmp_path: Path) -> None:
    policy_guard = PolicyGuardWithCategoryOverride(
        MoneyBotPolicyGuard(make_policy_config()),
        second_category="affiliate_marketing",
    )
    orchestrator, ledger_service = make_orchestrator(
        tmp_path,
        spend_enabled=True,
        policy_guard=policy_guard,
    )

    result = orchestrator.run_dry_run(
        make_request(
            mission="Require review for the concrete execution plan.",
            draft_recipient_email="maintainer@example.com",
            enable_wallet_payment=True,
        )
    )

    assert result.status == PolicyDecisionType.NEEDS_REVIEW.value
    assert result.stop_stage == "execution_policy"
    assert result.execution_policy_decision_id is not None
    assert result.email_draft_id is None
    assert result.wallet_result is None
    assert result.experiment_review_id is not None
    assert ledger_service.get_policy_decision(result.execution_policy_decision_id) is not None


def test_wallet_fail_closed_case_is_rejected(tmp_path: Path) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=False)

    result = orchestrator.run_dry_run(
        make_request(mission="Attempt a small approved payment.", enable_wallet_payment=True)
    )

    event_types = {item.event_type for item in result.timeline}

    assert result.wallet_result is not None
    assert result.wallet_result.status == "rejected"
    assert "wallet_transaction" not in event_types


def test_tiny_capped_payment_path_succeeds(tmp_path: Path) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=True)

    result = orchestrator.run_dry_run(
        make_request(mission="Run a tiny capped payment path.", enable_wallet_payment=True)
    )

    event_types = {item.event_type for item in result.timeline}

    assert result.wallet_result is not None
    assert result.wallet_result.status == "sent"
    assert "wallet_transaction" in event_types
