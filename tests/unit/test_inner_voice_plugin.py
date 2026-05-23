"""Unit tests for the inner voice plugin, debate coordinator, and Arbiter."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from openclaw_moneybot.plugins.inner_voice_plugin import (
    ArbiterResolutionRequest,
    ArbiterService,
    DebateResponderOutput,
    DebateResponderRequest,
    InnerVoiceCoordinator,
    InnerVoiceDebateError,
    InnerVoiceDebateRequest,
    InnerVoiceObjection,
    InnerVoicePlugin,
    InnerVoicePluginError,
    InnerVoiceReviewRequest,
    build_metrics_snapshot,
)
from openclaw_moneybot.shared import ArbiterConfig, ArchiveConfig, InnerVoiceConfig
from openclaw_moneybot.shared.types import (
    ArbiterFinalResolution,
    ArbiterPrevailingSide,
    DebateEndedReason,
    DebateSpeaker,
    DebateTurnType,
    InnerVoiceDisposition,
    InnerVoiceObjectionSeverity,
    InnerVoiceStage,
    InnerVoiceSubjectType,
    ProviderName,
    RecordType,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_review_request() -> InnerVoiceReviewRequest:
    return InnerVoiceReviewRequest(
        review_id="review_001",
        stage=InnerVoiceStage.TOS_LEGAL_CHECK,
        subject_type=InnerVoiceSubjectType.OPPORTUNITY,
        subject_id="opp_001",
        claim_summary="The opportunity is safe and eligible to proceed.",
        structured_context={"mission": "test"},
        constraints_summary=["no direct wallet access"],
        review_goal="Challenge the current conclusion.",
        max_objections=4,
    )


def make_inner_voice_plugin(
    tmp_path: Path,
    *,
    provider: ProviderName,
    handler: httpx.BaseTransport,
) -> tuple[InnerVoicePlugin, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    config = InnerVoiceConfig(
        enabled=True,
        provider=provider,
        model_name="test-model",
        base_url=(
            "https://api.openai.com/v1"
            if provider is ProviderName.OPENAI
            else "http://127.0.0.1:11434"
            if provider is ProviderName.OLLAMA
            else "http://127.0.0.1:8080/v1"
        ),
        api_key_env_var="OPENAI_API_KEY",
        allow_hosted_provider=provider is ProviderName.OPENAI,
    )
    plugin = InnerVoicePlugin(
        config,
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=handler,
    )
    return plugin, ledger_service


def make_arbiter_service(
    tmp_path: Path,
    *,
    provider: ProviderName,
    handler: httpx.BaseTransport,
) -> tuple[ArbiterService, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    config = ArbiterConfig(
        provider=provider,
        model_name="arbiter-model",
        base_url=(
            "https://api.openai.com/v1"
            if provider is ProviderName.OPENAI
            else "http://127.0.0.1:11434"
            if provider is ProviderName.OLLAMA
            else "http://127.0.0.1:8080/v1"
        ),
        api_key_env_var="OPENAI_API_KEY",
        allow_hosted_provider=provider is ProviderName.OPENAI,
    )
    service = ArbiterService(
        config,
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=handler,
    )
    return service, ledger_service


def test_openai_inner_voice_review_shapes_request_and_persists_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.openai.com"
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.read().decode("utf-8"))
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["messages"][1]["content"].find("Challenge the current conclusion.") >= 0
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": (
                                '{"overall_assessment":"Needs more evidence.",'
                                '"recommended_disposition":"needs_review",'
                                '"confidence_adjustment":-0.3,'
                                '"objections":[{"title":"Missing proof","severity":"high",'
                                '"reason":"No payout evidence yet."}],'
                                '"missing_evidence":["payout confirmation"],'
                                '"stale_information_risks":[],'
                                '"overlooked_constraints":["terms may have changed"],'
                                '"counterarguments":["Could still succeed with more proof"],'
                                '"recommended_followups":["capture rules snapshot"]}'
                            )
                        },
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            },
        )

    plugin, ledger_service = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OPENAI,
        handler=httpx.MockTransport(handler),
    )

    result = plugin.review(make_review_request(), required=True)

    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.INNER_VOICE_REVIEW,
        related_id="review_001",
    )
    assert result.recommended_disposition is InnerVoiceDisposition.NEEDS_REVIEW
    assert result.objections[0] == InnerVoiceObjection(
        title="Missing proof",
        severity=InnerVoiceObjectionSeverity.HIGH,
        reason="No payout evidence yet.",
    )
    assert len(evidence) == 2


def test_ollama_inner_voice_review_shapes_request(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        payload = json.loads(request.read().decode("utf-8"))
        assert payload["format"] == "json"
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"overall_assessment":"Low risk.",'
                        '"recommended_disposition":"proceed",'
                        '"confidence_adjustment":0,'
                        '"objections":[],'
                        '"missing_evidence":[],'
                        '"stale_information_risks":[],'
                        '"overlooked_constraints":[],'
                        '"counterarguments":[],'
                        '"recommended_followups":[]}'
                    )
                },
                "done_reason": "stop",
                "prompt_eval_count": 12,
                "eval_count": 8,
            },
        )

    plugin, _ = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OLLAMA,
        handler=httpx.MockTransport(handler),
    )

    result = plugin.review(make_review_request())

    assert result.recommended_disposition is InnerVoiceDisposition.PROCEED
    assert result.raw_response_summary["prompt_tokens"] == 12


def test_llama_server_arbiter_shapes_request_and_parses_result(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.read().decode("utf-8"))
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": (
                                '{"final_resolution":"adopt_inner_voice",'
                                '"prevailing_side":"inner_voice",'
                                '"resolution_summary":"The inner voice identified '
                                'the stronger blocker.",'
                                '"rationale_summary":"The evidence gap is material.",'
                                '"required_followups":["capture payment proof"],'
                                '"unresolved_risks":["counterparty uncertainty"]}'
                            )
                        },
                    }
                ],
                "usage": {"prompt_tokens": 15, "completion_tokens": 25},
            },
        )

    service, _ = make_arbiter_service(
        tmp_path,
        provider=ProviderName.LLAMA_SERVER,
        handler=httpx.MockTransport(handler),
    )

    result = service.resolve(
        ArbiterResolutionRequest(
            arbiter_review_id="arbiter_001",
            debate_id="debate_001",
            stage=InnerVoiceStage.PRE_EXECUTION,
            subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
            subject_id="plan_001",
            openclaw_position_summary="Proceed now.",
            inner_voice_position_summary="Stop until the proof is refreshed.",
            disagreement_summary="Proceed now versus wait for refreshed proof.",
            transcript_summary="openclaw: proceed\ninner_voice: wait",
            resolution_goal="Resolve the disagreement.",
            triggered_by=DebateEndedReason.MAX_ROUNDS_REACHED,
        )
    )

    assert result.final_resolution is ArbiterFinalResolution.ADOPT_INNER_VOICE
    assert result.prevailing_side is ArbiterPrevailingSide.INNER_VOICE


def test_inner_voice_review_persists_failure_on_malformed_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not-json"}, "finish_reason": "stop"}]},
        )

    plugin, ledger_service = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OPENAI,
        handler=httpx.MockTransport(handler),
    )

    with pytest.raises(InnerVoicePluginError, match="malformed JSON"):
        plugin.review(make_review_request(), required=True)

    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.INNER_VOICE_REVIEW,
        related_id="review_001",
    )
    assert any(item.evidence_type == "inner_voice_failure" for item in evidence)


class StaticResponder:
    """Simple deterministic responder used in debate tests."""

    def __init__(self, outputs: list[DebateResponderOutput]) -> None:
        self._outputs = iter(outputs)

    def respond_to_debate(self, request: DebateResponderRequest) -> DebateResponderOutput:
        return next(self._outputs)


def test_debate_converges_without_arbiter(tmp_path: Path) -> None:
    def inner_voice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"turn_type":"concession",'
                        '"message_text":"I agree after reviewing the same evidence.",'
                        '"cited_evidence_ids":["ev_1"],'
                        '"disposition_signal":"proceed",'
                        '"max_unresolved_severity":"low",'
                        '"request_arbiter":false}'
                    )
                },
                "done_reason": "stop",
            },
        )

    inner_voice, ledger_service = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OLLAMA,
        handler=httpx.MockTransport(inner_voice_handler),
    )
    arbiter, _ = make_arbiter_service(
        tmp_path,
        provider=ProviderName.LLAMA_SERVER,
        handler=httpx.MockTransport(lambda request: httpx.Response(500)),
    )
    coordinator = InnerVoiceCoordinator(
        inner_voice,
        arbiter,
        inner_voice.archiver,
        ledger_service,
    )

    outcome = coordinator.run_debate(
        InnerVoiceDebateRequest(
            stage=InnerVoiceStage.BUDGET_PLANNING,
            subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
            subject_id="plan_001",
            review_goal="Resolve the disagreement.",
            claim_summary="The plan should move forward.",
            disagreement_summary="Proceed or stop.",
            openclaw_initial_position="Proceed with the plan.",
            openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
            openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
            max_debate_rounds=2,
        ),
        openclaw=StaticResponder([]),
    )

    assert outcome.session.ended_reason is DebateEndedReason.CONVERGED
    assert outcome.arbiter_result is None
    transcript_evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.INNER_VOICE_DEBATE,
        related_id=outcome.session.debate_id,
    )
    assert any(
        item.evidence_type == "inner_voice_debate_transcript"
        for item in transcript_evidence
    )


def test_debate_max_rounds_reached_invokes_arbiter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")

    def inner_voice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"turn_type":"objection",'
                        '"message_text":"I still disagree because the evidence is stale.",'
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
                                '{"final_resolution":"needs_review",'
                                '"prevailing_side":"neither",'
                                '"resolution_summary":"More evidence is needed.",'
                                '"rationale_summary":"The disagreement centers on stale evidence.",'
                                '"required_followups":["refresh the rules snapshot"],'
                                '"unresolved_risks":["stale terms"]}'
                            )
                        },
                    }
                ]
            },
        )

    inner_voice, ledger_service = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OLLAMA,
        handler=httpx.MockTransport(inner_voice_handler),
    )
    arbiter, _ = make_arbiter_service(
        tmp_path,
        provider=ProviderName.OPENAI,
        handler=httpx.MockTransport(arbiter_handler),
    )
    coordinator = InnerVoiceCoordinator(
        inner_voice,
        arbiter,
        inner_voice.archiver,
        ledger_service,
    )

    outcome = coordinator.run_debate(
        InnerVoiceDebateRequest(
            stage=InnerVoiceStage.PRE_EXECUTION,
            subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
            subject_id="plan_001",
            review_goal="Resolve the disagreement.",
            claim_summary="The plan should move forward.",
            disagreement_summary="Proceed or stop.",
            openclaw_initial_position="Proceed with the plan now.",
            openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
            openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
            max_debate_rounds=1,
        ),
        openclaw=StaticResponder([]),
    )

    assert outcome.session.ended_reason is DebateEndedReason.MAX_ROUNDS_REACHED
    assert outcome.arbiter_result is not None
    assert outcome.arbiter_result.final_resolution is ArbiterFinalResolution.NEEDS_REVIEW


def test_openclaw_arbiter_request_invokes_arbiter(tmp_path: Path) -> None:
    def inner_voice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"turn_type":"objection",'
                        '"message_text":"I disagree but I can continue debating.",'
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
                        "message": {
                            "content": (
                                '{"final_resolution":"adopt_openclaw",'
                                '"prevailing_side":"openclaw",'
                                '"resolution_summary":"The current evidence supports proceeding.",'
                                '"rationale_summary":"The blocker is not material.",'
                                '"required_followups":[],'
                                '"unresolved_risks":[]}'
                            )
                        },
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    inner_voice, ledger_service = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OLLAMA,
        handler=httpx.MockTransport(inner_voice_handler),
    )
    arbiter, _ = make_arbiter_service(
        tmp_path,
        provider=ProviderName.LLAMA_SERVER,
        handler=httpx.MockTransport(arbiter_handler),
    )
    coordinator = InnerVoiceCoordinator(
        inner_voice,
        arbiter,
        inner_voice.archiver,
        ledger_service,
    )
    openclaw = StaticResponder(
        [
            DebateResponderOutput(
                turn_type=DebateTurnType.REQUEST_ARBITER,
                message_text="I request Arbiter resolution.",
                disposition_signal=InnerVoiceDisposition.PROCEED,
                request_arbiter=True,
            )
        ]
    )

    outcome = coordinator.run_debate(
        InnerVoiceDebateRequest(
            stage=InnerVoiceStage.PRE_EXECUTION,
            subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
            subject_id="plan_001",
            review_goal="Resolve the disagreement.",
            claim_summary="The plan should move forward.",
            disagreement_summary="Proceed or stop.",
            openclaw_initial_position="Proceed with the plan now.",
            openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
            openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
            max_debate_rounds=2,
        ),
        openclaw=openclaw,
    )

    assert outcome.session.ended_reason is DebateEndedReason.REQUEST_ARBITER
    assert outcome.session.arbiter_requested_by is DebateSpeaker.OPENCLAW
    assert outcome.arbiter_result is not None


def test_arbiter_failure_results_in_debate_error_and_failed_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")

    def inner_voice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"turn_type":"objection",'
                        '"message_text":"I still disagree because the evidence is stale.",'
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
        return httpx.Response(200, json={"choices": [{"message": {"content": "not-json"}}]})

    inner_voice, ledger_service = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OLLAMA,
        handler=httpx.MockTransport(inner_voice_handler),
    )
    arbiter, _ = make_arbiter_service(
        tmp_path,
        provider=ProviderName.OPENAI,
        handler=httpx.MockTransport(arbiter_handler),
    )
    coordinator = InnerVoiceCoordinator(
        inner_voice,
        arbiter,
        inner_voice.archiver,
        ledger_service,
    )

    with pytest.raises(InnerVoiceDebateError):
        coordinator.run_debate(
            InnerVoiceDebateRequest(
                stage=InnerVoiceStage.PRE_EXECUTION,
                subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
                subject_id="plan_001",
                review_goal="Resolve the disagreement.",
                claim_summary="The plan should move forward.",
                disagreement_summary="Proceed or stop.",
                openclaw_initial_position="Proceed with the plan now.",
                openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
                openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
                max_debate_rounds=1,
            ),
            openclaw=StaticResponder([]),
        )

    debate_records = ledger_service.get_related_events(related_id="plan_001")
    assert debate_records or ledger_service.get_opportunity("plan_001") is None


def test_build_metrics_snapshot_summarizes_debate_and_arbiter_results(tmp_path: Path) -> None:
    call_count = 0

    def inner_voice_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            content = (
                '{"overall_assessment":"The review found no material blocker.",'
                '"recommended_disposition":"proceed",'
                '"confidence_adjustment":0,'
                '"objections":[{"title":"Need receipt","severity":"low",'
                '"reason":"Receipt proof is still pending.","evidence_basis":"ev_1"}],'
                '"missing_evidence":["receipt"],'
                '"stale_information_risks":[],'
                '"overlooked_constraints":[],'
                '"counterarguments":[],'
                '"recommended_followups":["collect receipt"]}'
            )
        else:
            content = (
                '{"turn_type":"concession",'
                '"message_text":"I agree after reviewing the same evidence.",'
                '"cited_evidence_ids":["ev_1"],'
                '"disposition_signal":"proceed",'
                '"max_unresolved_severity":"low",'
                '"request_arbiter":false}'
            )
        return httpx.Response(
            200,
            json={
                "message": {"content": content},
                "done_reason": "stop",
            },
        )

    inner_voice, ledger_service = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OLLAMA,
        handler=httpx.MockTransport(inner_voice_handler),
    )
    arbiter, _ = make_arbiter_service(
        tmp_path,
        provider=ProviderName.LLAMA_SERVER,
        handler=httpx.MockTransport(lambda request: httpx.Response(500)),
    )
    coordinator = InnerVoiceCoordinator(
        inner_voice,
        arbiter,
        inner_voice.archiver,
        ledger_service,
    )
    review = inner_voice.review(
        make_review_request().model_copy(update={"review_id": "review_metrics"})
    )
    outcome = coordinator.run_debate(
        InnerVoiceDebateRequest(
            stage=InnerVoiceStage.BUDGET_PLANNING,
            subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
            subject_id="plan_001",
            review_goal="Resolve the disagreement.",
            claim_summary="The plan should move forward.",
            disagreement_summary="Proceed or stop.",
            openclaw_initial_position="Proceed with the plan.",
            openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
            openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
            max_debate_rounds=2,
        ),
        openclaw=StaticResponder([]),
    )

    snapshot = build_metrics_snapshot([review], [outcome], [])

    assert snapshot.invocation_count_by_stage["tos_legal_check"] == 1
    assert snapshot.debate_session_count_by_stage["budget_planning"] == 1
