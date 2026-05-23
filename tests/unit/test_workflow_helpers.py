"""Unit tests for workflow disagreement helper logic."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from openclaw_moneybot.orchestration.workflow import MoneyBotOrchestrator
from openclaw_moneybot.plugins.inner_voice_plugin import (
    ArbiterResolutionResult,
    DebateResponder,
    DebateResponderOutput,
    InnerVoiceCoordinator,
    InnerVoiceDebateError,
    InnerVoiceDebateOutcome,
    InnerVoiceDebateRequest,
    InnerVoiceDebateSession,
    InnerVoiceDebateTurn,
    ProviderResponseSummary,
)
from openclaw_moneybot.plugins.inner_voice_plugin.models import InnerVoiceFailureDetails
from openclaw_moneybot.shared.contracts import LedgerRecord
from openclaw_moneybot.shared.types import (
    ArbiterFinalResolution,
    ArbiterPrevailingSide,
    DebateEndedReason,
    DebateSpeaker,
    DebateTurnType,
    InnerVoiceDisposition,
    InnerVoiceStage,
    InnerVoiceSubjectType,
    ProviderName,
    RecordType,
)

_HELPERS_SPEC = importlib.util.spec_from_file_location(
    "integration_helpers",
    Path(__file__).resolve().parents[1] / "integration" / "helpers.py",
)
assert _HELPERS_SPEC is not None and _HELPERS_SPEC.loader is not None
_HELPERS_MODULE = importlib.util.module_from_spec(_HELPERS_SPEC)
_HELPERS_SPEC.loader.exec_module(_HELPERS_MODULE)
make_orchestrator = cast(Any, _HELPERS_MODULE.make_orchestrator)


class UnusedResponder(DebateResponder):
    def respond_to_debate(self, request: object) -> DebateResponderOutput:
        raise AssertionError("responder should not be used in this test")


class FailingCoordinator:
    def __init__(self, error: InnerVoiceDebateError) -> None:
        self.error = error

    def run_debate(
        self,
        request: InnerVoiceDebateRequest,
        *,
        openclaw: DebateResponder,
        resolution_guard: object | None = None,
    ) -> InnerVoiceDebateOutcome:
        raise self.error


def make_outcome(
    *,
    final_resolution_source: str = "debate",
    arbiter_result: ArbiterResolutionResult | None = None,
    resolved_disposition: InnerVoiceDisposition | None = InnerVoiceDisposition.PROCEED,
) -> InnerVoiceDebateOutcome:
    return InnerVoiceDebateOutcome(
        session=InnerVoiceDebateSession(
            debate_id="debate_001",
            stage=InnerVoiceStage.PRE_EXECUTION,
            subject_type=InnerVoiceSubjectType.SPEND_REQUEST,
            subject_id="spend_001",
            initiated_by=DebateSpeaker.OPENCLAW,
            max_rounds_configured=2,
            completed_rounds=2,
            ended_reason=DebateEndedReason.REQUEST_ARBITER,
            transcript_archive_ids=["ev_1"],
            arbiter_review_id=None if arbiter_result is None else arbiter_result.arbiter_review_id,
        ),
        turns=[
            InnerVoiceDebateTurn(
                debate_id="debate_001",
                round_index=1,
                turn_index=1,
                speaker=DebateSpeaker.OPENCLAW,
                turn_type=DebateTurnType.PROPOSAL,
                message_text="Proceed",
                cited_evidence_ids=[],
                disposition_signal=InnerVoiceDisposition.PROCEED,
                created_at="2026-01-01T00:00:00Z",
            ),
            InnerVoiceDebateTurn(
                debate_id="debate_001",
                round_index=1,
                turn_index=2,
                speaker=DebateSpeaker.INNER_VOICE,
                turn_type=DebateTurnType.OBJECTION,
                message_text="Needs review",
                cited_evidence_ids=[],
                disposition_signal=InnerVoiceDisposition.NEEDS_REVIEW,
                created_at="2026-01-01T00:00:01Z",
            ),
        ],
        final_resolution_source=final_resolution_source,
        resolved_disposition=resolved_disposition,
        arbiter_result=arbiter_result,
        ledger_record=LedgerRecord.model_construct(
            record_id="record_debate",
            created_at=datetime.now(UTC),
            record_type=RecordType.INNER_VOICE_DEBATE,
            payload={},
        ),
    )


def make_arbiter_result(
    final_resolution: ArbiterFinalResolution,
) -> ArbiterResolutionResult:
    return ArbiterResolutionResult(
        arbiter_review_id="arbiter_001",
        debate_id="debate_001",
        provider=ProviderName.OPENAI,
        model_name="arbiter-model",
        stage=InnerVoiceStage.PRE_EXECUTION,
        subject_type=InnerVoiceSubjectType.SPEND_REQUEST,
        subject_id="spend_001",
        final_resolution=final_resolution,
        prevailing_side=ArbiterPrevailingSide.NEITHER,
        resolution_summary="summary",
        rationale_summary="rationale",
        required_followups=(
            ["followup"]
            if final_resolution is ArbiterFinalResolution.PROCEED_WITH_FOLLOWUPS
            else []
        ),
        unresolved_risks=[],
        raw_response_summary=ProviderResponseSummary(
            provider=ProviderName.OPENAI,
            model_name="arbiter-model",
            response_chars=10,
        ),
        ledger_record=LedgerRecord.model_construct(
            record_id="record_arbiter",
            created_at=datetime.now(UTC),
            record_type=RecordType.ARBITER_REVIEW,
            payload={},
        ),
    )


def test_resolve_model_disagreement_rejects_when_coordinator_missing(tmp_path: Path) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=False)

    with pytest.raises(ValueError, match="not configured"):
        orchestrator.resolve_model_disagreement(
            InnerVoiceDebateRequest(
                stage=InnerVoiceStage.PRE_EXECUTION,
                subject_type=InnerVoiceSubjectType.SPEND_REQUEST,
                subject_id="spend_001",
                review_goal="Resolve",
                claim_summary="Claim",
                disagreement_summary="Disagree",
                openclaw_initial_position="Proceed",
            ),
            openclaw=UnusedResponder(),
        )


def test_resolve_model_disagreement_rejects_irrelevant_stage_subject_pair(
    tmp_path: Path,
) -> None:
    orchestrator, _ = make_orchestrator(
        tmp_path,
        spend_enabled=False,
        inner_voice_coordinator=cast(InnerVoiceCoordinator, object()),
    )

    with pytest.raises(ValueError, match="not relevant"):
        orchestrator.resolve_model_disagreement(
            InnerVoiceDebateRequest(
                stage=InnerVoiceStage.POST_REVIEW,
                subject_type=InnerVoiceSubjectType.SPEND_REQUEST,
                subject_id="spend_001",
                review_goal="Resolve",
                claim_summary="Claim",
                disagreement_summary="Disagree",
                openclaw_initial_position="Proceed",
            ),
            openclaw=UnusedResponder(),
        )


def test_settle_model_disagreement_reraises_for_non_required_paths(tmp_path: Path) -> None:
    error = InnerVoiceDebateError("boom", failure_class="debate_error")
    orchestrator, _ = make_orchestrator(
        tmp_path,
        spend_enabled=False,
        inner_voice_coordinator=cast(InnerVoiceCoordinator, FailingCoordinator(error)),
    )

    with pytest.raises(InnerVoiceDebateError, match="boom"):
        orchestrator.settle_model_disagreement(
            InnerVoiceDebateRequest(
                stage=InnerVoiceStage.BUDGET_PLANNING,
                subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
                subject_id="plan_001",
                review_goal="Resolve",
                claim_summary="Claim",
                disagreement_summary="Disagree",
                openclaw_initial_position="Proceed",
            ),
            openclaw=UnusedResponder(),
        )


def test_settle_model_disagreement_uses_failure_record_id_when_present(
    tmp_path: Path,
) -> None:
    error = InnerVoiceDebateError(
        "boom",
        failure_class="debate_error",
        failure=InnerVoiceFailureDetails(
            record_id="debate_failure_001",
            record_type=RecordType.INNER_VOICE_DEBATE,
            stage="pre_execution",
            subject_type="spend_request",
            subject_id="spend_001",
            failure_class="debate_error",
            failure_message="boom",
            was_required=True,
        ),
    )
    orchestrator, _ = make_orchestrator(
        tmp_path,
        spend_enabled=False,
        inner_voice_coordinator=cast(InnerVoiceCoordinator, FailingCoordinator(error)),
    )

    interpretation = orchestrator.settle_model_disagreement(
        InnerVoiceDebateRequest(
            stage=InnerVoiceStage.PRE_EXECUTION,
            subject_type=InnerVoiceSubjectType.SPEND_REQUEST,
            subject_id="spend_001",
            review_goal="Resolve",
            claim_summary="Claim",
            disagreement_summary="Disagree",
            openclaw_initial_position="Proceed",
        ),
        openclaw=UnusedResponder(),
    )

    assert interpretation.debate_id == "debate_failure_001"


@pytest.mark.parametrize(
    ("debate_id", "expected"),
    [("debate_req_001", "debate_req_001"), (None, "debate_unavailable")],
)
def test_settle_model_disagreement_falls_back_when_failure_details_absent(
    tmp_path: Path,
    debate_id: str | None,
    expected: str,
) -> None:
    error = InnerVoiceDebateError("boom", failure_class="debate_error")
    orchestrator, _ = make_orchestrator(
        tmp_path,
        spend_enabled=False,
        inner_voice_coordinator=cast(InnerVoiceCoordinator, FailingCoordinator(error)),
    )

    interpretation = orchestrator.settle_model_disagreement(
        InnerVoiceDebateRequest(
            debate_id=debate_id,
            stage=InnerVoiceStage.PRE_EXECUTION,
            subject_type=InnerVoiceSubjectType.SPEND_REQUEST,
            subject_id="spend_001",
            review_goal="Resolve",
            claim_summary="Claim",
            disagreement_summary="Disagree",
            openclaw_initial_position="Proceed",
        ),
        openclaw=UnusedResponder(),
    )

    assert interpretation.debate_id == expected


def test_interpret_model_disagreement_requires_arbiter_result_for_arbiter_source(
    tmp_path: Path,
) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=False)

    with pytest.raises(ValueError, match="missing an Arbiter result"):
        orchestrator.interpret_model_disagreement(
            make_outcome(final_resolution_source="arbiter", arbiter_result=None)
        )


@pytest.mark.parametrize(
    ("stage", "subject_type", "expected"),
    [
        (InnerVoiceStage.OPPORTUNITY_RANKING, InnerVoiceSubjectType.OPPORTUNITY, True),
        (InnerVoiceStage.TOS_LEGAL_CHECK, InnerVoiceSubjectType.OPPORTUNITY, True),
        (InnerVoiceStage.BUDGET_PLANNING, InnerVoiceSubjectType.EXPERIMENT_PLAN, True),
        (InnerVoiceStage.PRE_EXECUTION, InnerVoiceSubjectType.EXPERIMENT_PLAN, True),
        (InnerVoiceStage.PRE_EXECUTION, InnerVoiceSubjectType.EXECUTION_STEP, True),
        (InnerVoiceStage.PRE_EXECUTION, InnerVoiceSubjectType.SPEND_REQUEST, True),
        (InnerVoiceStage.POST_REVIEW, InnerVoiceSubjectType.EXPERIMENT_REVIEW, True),
        (InnerVoiceStage.POST_REVIEW, InnerVoiceSubjectType.OPPORTUNITY, False),
        (InnerVoiceStage.BUDGET_PLANNING, InnerVoiceSubjectType.OPPORTUNITY, False),
    ],
)
def test_debate_subject_relevance_matrix(
    stage: InnerVoiceStage,
    subject_type: InnerVoiceSubjectType,
    expected: bool,
) -> None:
    assert MoneyBotOrchestrator._debate_subject_is_relevant(stage, subject_type) is expected


@pytest.mark.parametrize(
    ("subject_type", "expected"),
    [
        (InnerVoiceSubjectType.SPEND_REQUEST, True),
        (InnerVoiceSubjectType.EXECUTION_STEP, True),
        (InnerVoiceSubjectType.EXPERIMENT_PLAN, False),
    ],
)
def test_requires_fail_closed_debate_path(
    subject_type: InnerVoiceSubjectType,
    expected: bool,
) -> None:
    request = InnerVoiceDebateRequest(
        stage=InnerVoiceStage.PRE_EXECUTION,
        subject_type=subject_type,
        subject_id="subject_001",
        review_goal="Resolve",
        claim_summary="Claim",
        disagreement_summary="Disagree",
        openclaw_initial_position="Proceed",
    )
    assert MoneyBotOrchestrator._requires_fail_closed_debate_path(request) is expected


def test_debate_orchestrator_escalation_reason_none_for_non_required_or_non_followup(
    tmp_path: Path,
) -> None:
    orchestrator, _ = make_orchestrator(tmp_path, spend_enabled=False)
    non_required_request = InnerVoiceDebateRequest(
        stage=InnerVoiceStage.BUDGET_PLANNING,
        subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
        subject_id="plan_001",
        review_goal="Resolve",
        claim_summary="Claim",
        disagreement_summary="Disagree",
        openclaw_initial_position="Proceed",
    )
    required_request = InnerVoiceDebateRequest(
        stage=InnerVoiceStage.PRE_EXECUTION,
        subject_type=InnerVoiceSubjectType.SPEND_REQUEST,
        subject_id="spend_001",
        review_goal="Resolve",
        claim_summary="Claim",
        disagreement_summary="Disagree",
        openclaw_initial_position="Proceed",
    )
    turns = make_outcome().turns

    assert (
        orchestrator._debate_orchestrator_escalation_reason(
            non_required_request,
            turns,
            InnerVoiceDisposition.PROCEED_WITH_FOLLOWUPS,
            None,
        )
        is None
    )
    assert (
        orchestrator._debate_orchestrator_escalation_reason(
            required_request,
            turns,
            InnerVoiceDisposition.PROCEED,
            None,
        )
        is None
    )


@pytest.mark.parametrize(
    ("arbiter_result", "expected"),
    [
        (None, InnerVoiceDisposition.PROCEED),
        (ArbiterFinalResolution.ADOPT_OPENCLAW, InnerVoiceDisposition.PROCEED),
        (ArbiterFinalResolution.ADOPT_INNER_VOICE, InnerVoiceDisposition.NEEDS_REVIEW),
        (
            ArbiterFinalResolution.PROCEED_WITH_FOLLOWUPS,
            InnerVoiceDisposition.PROCEED_WITH_FOLLOWUPS,
        ),
        (ArbiterFinalResolution.NEEDS_REVIEW, InnerVoiceDisposition.NEEDS_REVIEW),
    ],
)
def test_resolved_disposition_from_outcome_parts(
    arbiter_result: ArbiterFinalResolution | None,
    expected: InnerVoiceDisposition,
) -> None:
    result = (
        None
        if arbiter_result is None
        else make_arbiter_result(arbiter_result)
    )
    assert (
        MoneyBotOrchestrator._resolved_disposition_from_outcome_parts(
            turns=make_outcome().turns,
            resolved_disposition=InnerVoiceDisposition.PROCEED,
            arbiter_result=result,
        )
        is expected
    )


def test_latest_disposition_from_turns_returns_newest_matching_speaker_or_none() -> None:
    turns = make_outcome().turns

    assert (
        MoneyBotOrchestrator._latest_disposition_from_turns(turns, DebateSpeaker.OPENCLAW)
        is InnerVoiceDisposition.PROCEED
    )
    assert (
        MoneyBotOrchestrator._latest_disposition_from_turns(turns, DebateSpeaker.INNER_VOICE)
        is InnerVoiceDisposition.NEEDS_REVIEW
    )
    assert (
        MoneyBotOrchestrator._latest_disposition_from_turns(
            [
                InnerVoiceDebateTurn(
                    debate_id="debate_none",
                    round_index=1,
                    turn_index=1,
                    speaker=DebateSpeaker.OPENCLAW,
                    turn_type=DebateTurnType.PROPOSAL,
                    message_text="No disposition",
                    cited_evidence_ids=[],
                    created_at="2026-01-01T00:00:00Z",
                )
            ],
            DebateSpeaker.OPENCLAW,
        )
        is None
    )
