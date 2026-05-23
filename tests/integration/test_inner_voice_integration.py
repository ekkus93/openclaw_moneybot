"""Integration coverage for inner voice review, debate logging, and Arbiter escalation."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from openclaw_moneybot.plugins.inner_voice_plugin import (
    ArbiterService,
    DebateResponderOutput,
    DebateResponderRequest,
    InnerVoiceCoordinator,
    InnerVoiceDebateRequest,
    InnerVoicePlugin,
    InnerVoiceReviewRequest,
    build_metrics_snapshot,
    list_arbiter_reviews,
    list_inner_voice_debates,
    list_inner_voice_reviews,
    persist_metrics_snapshot,
)
from openclaw_moneybot.plugins.inner_voice_plugin.errors import (
    ArbiterResolutionError,
    InnerVoiceDebateError,
)
from openclaw_moneybot.plugins.inner_voice_plugin.models import ArbiterResolutionRequest
from openclaw_moneybot.shared import ArbiterConfig, ArchiveConfig, InnerVoiceConfig
from openclaw_moneybot.shared.types import (
    ArbiterFinalResolution,
    DebateEndedReason,
    DebateTurnType,
    InnerVoiceDisposition,
    InnerVoiceObjectionSeverity,
    InnerVoiceStage,
    InnerVoiceSubjectType,
    ProviderName,
    RecordType,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


class StaticResponder:
    def __init__(self, output: DebateResponderOutput) -> None:
        self.output = output

    def respond_to_debate(self, request: DebateResponderRequest) -> DebateResponderOutput:
        return self.output


def make_inner_voice_plugin(
    tmp_path: Path,
    handler: httpx.BaseTransport,
    *,
    archive_debate_transcript: bool = True,
    archive_debate_turn_metadata: bool = True,
) -> tuple[InnerVoicePlugin, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = InnerVoicePlugin(
        InnerVoiceConfig(
            enabled=True,
            provider=ProviderName.OLLAMA,
            model_name="ollama-test",
            base_url="http://127.0.0.1:11434",
            archive_debate_transcript=archive_debate_transcript,
            archive_debate_turn_metadata=archive_debate_turn_metadata,
        ),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=handler,
    )
    return plugin, ledger_service


def make_arbiter(
    tmp_path: Path,
    handler: httpx.BaseTransport,
    ledger_service: LedgerService,
) -> ArbiterService:
    return ArbiterService(
        ArbiterConfig(
            provider=ProviderName.LLAMA_SERVER,
            model_name="arbiter-test",
            base_url="http://127.0.0.1:8080/v1",
            allow_hosted_provider=False,
            allow_non_local_provider=False,
        ),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=handler,
    )


def test_inner_voice_review_archives_prompt_and_response(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"overall_assessment":"Needs more evidence.",'
                        '"recommended_disposition":"needs_review",'
                        '"confidence_adjustment":-0.2,'
                        '"objections":[],'
                        '"missing_evidence":["proof"],'
                        '"stale_information_risks":[],'
                        '"overlooked_constraints":[],'
                        '"counterarguments":[],'
                        '"recommended_followups":["collect proof"]}'
                    )
                },
                "done_reason": "stop",
            },
        )

    plugin, ledger_service = make_inner_voice_plugin(tmp_path, httpx.MockTransport(handler))

    result = plugin.review(
        InnerVoiceReviewRequest(
            review_id="review_001",
            stage=InnerVoiceStage.TOS_LEGAL_CHECK,
            subject_type=InnerVoiceSubjectType.OPPORTUNITY,
            subject_id="opp_001",
            claim_summary="Proceed now.",
            review_goal="Challenge the current conclusion.",
        )
    )

    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.INNER_VOICE_REVIEW,
        related_id=result.review_id,
    )
    assert len(evidence) == 2
    assert result.recommended_disposition is InnerVoiceDisposition.NEEDS_REVIEW


def test_debate_transcript_and_arbiter_linkage_are_persisted(tmp_path: Path) -> None:
    def inner_voice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"turn_type":"objection",'
                        '"message_text":"The evidence is still stale.",'
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
                        "message": {
                            "content": (
                                '{"final_resolution":"block_pending_checks",'
                                '"prevailing_side":"inner_voice",'
                                '"resolution_summary":"Wait for refreshed evidence.",'
                                '"rationale_summary":"The disagreement turns on stale proof.",'
                                '"required_followups":["refresh evidence"],'
                                '"unresolved_risks":["stale proof"]}'
                            )
                        },
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    plugin, ledger_service = make_inner_voice_plugin(
        tmp_path,
        httpx.MockTransport(inner_voice_handler),
    )
    arbiter = make_arbiter(tmp_path, httpx.MockTransport(arbiter_handler), ledger_service)
    coordinator = InnerVoiceCoordinator(plugin, arbiter, plugin.archiver, ledger_service)

    outcome = coordinator.run_debate(
        InnerVoiceDebateRequest(
            stage=InnerVoiceStage.PRE_EXECUTION,
            subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
            subject_id="plan_001",
            review_goal="Resolve the disagreement.",
            claim_summary="The plan should move forward.",
            disagreement_summary="Proceed or stop.",
            openclaw_initial_position="Proceed with the current plan.",
            openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
            openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
            max_debate_rounds=1,
        ),
        openclaw=StaticResponder(
            DebateResponderOutput(
                turn_type=DebateTurnType.REBUTTAL,
                message_text="Proceed anyway.",
                disposition_signal=InnerVoiceDisposition.PROCEED,
            )
        ),
    )

    debate_evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.INNER_VOICE_DEBATE,
        related_id=outcome.session.debate_id,
    )
    arbiter_evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.ARBITER_REVIEW,
        related_id=outcome.arbiter_result.arbiter_review_id if outcome.arbiter_result else "",
    )

    assert outcome.session.ended_reason is DebateEndedReason.MAX_ROUNDS_REACHED
    assert outcome.arbiter_result is not None
    assert outcome.arbiter_result.final_resolution is ArbiterFinalResolution.BLOCK_PENDING_CHECKS
    assert any(item.evidence_type == "inner_voice_debate_transcript" for item in debate_evidence)
    assert any(item.evidence_type == "arbiter_response" for item in arbiter_evidence)


def test_observability_helpers_query_real_review_debate_and_arbiter_records(
    tmp_path: Path,
) -> None:
    def review_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"overall_assessment":"Need refreshed proof.",'
                        '"recommended_disposition":"needs_review",'
                        '"confidence_adjustment":-0.2,'
                        '"objections":[],'
                        '"missing_evidence":["refreshed proof"],'
                        '"stale_information_risks":[],'
                        '"overlooked_constraints":[],'
                        '"counterarguments":[],'
                        '"recommended_followups":["refresh proof"]}'
                    )
                },
                "done_reason": "stop",
            },
        )

    def debate_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"turn_type":"objection",'
                        '"message_text":"The evidence still looks stale.",'
                        '"cited_evidence_ids":["ev_1"],'
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
                                '{"final_resolution":"block_pending_checks",'
                                '"prevailing_side":"inner_voice",'
                                '"resolution_summary":"Wait for the refreshed proof.",'
                                '"rationale_summary":"The stale evidence concern is material.",'
                                '"required_followups":["refresh proof"],'
                                '"unresolved_risks":["stale proof"]}'
                            )
                        },
                    }
                ]
            },
        )

    plugin, ledger_service = make_inner_voice_plugin(
        tmp_path,
        httpx.MockTransport(review_handler),
    )
    review = plugin.review(
        InnerVoiceReviewRequest(
            review_id="review_obs_001",
            stage=InnerVoiceStage.TOS_LEGAL_CHECK,
            subject_type=InnerVoiceSubjectType.OPPORTUNITY,
            subject_id="opp_obs_001",
            claim_summary="Proceed now.",
            review_goal="Challenge the current conclusion.",
        )
    )
    plugin.review(
        InnerVoiceReviewRequest(
            review_id="review_obs_002",
            stage=InnerVoiceStage.TOS_LEGAL_CHECK,
            subject_type=InnerVoiceSubjectType.OPPORTUNITY,
            subject_id="opp_other_001",
            claim_summary="Proceed now.",
            review_goal="Challenge the current conclusion.",
        )
    )
    debate_plugin = InnerVoicePlugin(
        plugin.config,
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=httpx.MockTransport(debate_handler),
    )
    arbiter = make_arbiter(tmp_path, httpx.MockTransport(arbiter_handler), ledger_service)
    coordinator = InnerVoiceCoordinator(
        debate_plugin,
        arbiter,
        debate_plugin.archiver,
        ledger_service,
    )
    outcome = coordinator.run_debate(
        InnerVoiceDebateRequest(
            stage=InnerVoiceStage.PRE_EXECUTION,
            subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
            subject_id="plan_obs_001",
            review_goal="Resolve the disagreement.",
            claim_summary="The plan should move forward.",
            disagreement_summary="Proceed or stop.",
            openclaw_initial_position="Proceed with the current plan.",
            openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
            openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
            max_debate_rounds=1,
        ),
        openclaw=StaticResponder(
            DebateResponderOutput(
                turn_type=DebateTurnType.REBUTTAL,
                message_text="Proceed anyway.",
                disposition_signal=InnerVoiceDisposition.PROCEED,
            )
        ),
    )

    review_records = list_inner_voice_reviews(
        ledger_service,
        subject_id="opp_obs_001",
        stage=InnerVoiceStage.TOS_LEGAL_CHECK,
        outcome="needs_review",
    )
    debate_records = list_inner_voice_debates(
        ledger_service,
        subject_id="plan_obs_001",
        stage=InnerVoiceStage.PRE_EXECUTION,
        outcome="block_pending_checks",
    )
    arbiter_records = list_arbiter_reviews(
        ledger_service,
        subject_id="plan_obs_001",
        stage=InnerVoiceStage.PRE_EXECUTION,
        outcome="block_pending_checks",
    )

    assert len(review_records) == 1
    assert review_records[0].record_id == review.review_id
    assert len(debate_records) == 1
    assert debate_records[0].payload["resolution_outcome"] == "block_pending_checks"
    assert debate_records[0].payload["summary_archive_id"] == outcome.session.summary_archive_id
    assert len(arbiter_records) == 1
    assert outcome.arbiter_result is not None
    assert arbiter_records[0].record_id == outcome.arbiter_result.arbiter_review_id
    assert (
        list_inner_voice_reviews(
            ledger_service,
            subject_id="opp_other_001",
            outcome="proceed",
        )
        == []
    )


def test_metrics_snapshot_can_be_built_and_persisted_from_real_records(tmp_path: Path) -> None:
    def review_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"overall_assessment":"Need refreshed proof.",'
                        '"recommended_disposition":"needs_review",'
                        '"confidence_adjustment":-0.2,'
                        '"objections":[{"title":"Proof gap","severity":"medium",'
                        '"reason":"Refresh the archived payout proof."}],'
                        '"missing_evidence":["refreshed proof"],'
                        '"stale_information_risks":[],'
                        '"overlooked_constraints":[],'
                        '"counterarguments":[],'
                        '"recommended_followups":["refresh proof"]}'
                    )
                },
                "done_reason": "stop",
            },
        )

    def debate_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"turn_type":"objection",'
                        '"message_text":"The proof still looks stale.",'
                        '"cited_evidence_ids":["ev_1"],'
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
                                '{"final_resolution":"block_pending_checks",'
                                '"prevailing_side":"inner_voice",'
                                '"resolution_summary":"Wait for the refreshed proof.",'
                                '"rationale_summary":"The stale evidence concern is material.",'
                                '"required_followups":["refresh proof"],'
                                '"unresolved_risks":["stale proof"]}'
                            )
                        },
                    }
                ]
            },
        )

    plugin, ledger_service = make_inner_voice_plugin(
        tmp_path,
        httpx.MockTransport(review_handler),
    )
    review = plugin.review(
        InnerVoiceReviewRequest(
            review_id="review_metrics_001",
            stage=InnerVoiceStage.TOS_LEGAL_CHECK,
            subject_type=InnerVoiceSubjectType.OPPORTUNITY,
            subject_id="opp_metrics_001",
            claim_summary="Proceed now.",
            review_goal="Challenge the current conclusion.",
        )
    )
    debate_plugin = InnerVoicePlugin(
        plugin.config,
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=httpx.MockTransport(debate_handler),
    )
    arbiter = make_arbiter(tmp_path, httpx.MockTransport(arbiter_handler), ledger_service)
    coordinator = InnerVoiceCoordinator(
        debate_plugin,
        arbiter,
        debate_plugin.archiver,
        ledger_service,
    )
    outcome = coordinator.run_debate(
        InnerVoiceDebateRequest(
            stage=InnerVoiceStage.PRE_EXECUTION,
            subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
            subject_id="plan_metrics_001",
            review_goal="Resolve the disagreement.",
            claim_summary="The plan should move forward.",
            disagreement_summary="Proceed or stop.",
            openclaw_initial_position="Proceed with the current plan.",
            openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
            openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
            max_debate_rounds=1,
        ),
        openclaw=StaticResponder(
            DebateResponderOutput(
                turn_type=DebateTurnType.REBUTTAL,
                message_text="Proceed anyway.",
                disposition_signal=InnerVoiceDisposition.PROCEED,
            )
        ),
    )
    assert outcome.arbiter_result is not None
    snapshot = build_metrics_snapshot([review], [outcome], [outcome.arbiter_result])
    metrics_record = persist_metrics_snapshot(
        snapshot,
        ledger_service=ledger_service,
        archiver=plugin.archiver,
        snapshot_id="metrics_001",
    )
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.METRICS_EXPORT,
        related_id="metrics_001",
    )

    assert snapshot.invocation_count_by_stage["tos_legal_check"] == 1
    assert snapshot.debate_session_count_by_stage["pre_execution"] == 1
    assert snapshot.arbiter_invocation_rate == 1.0
    assert snapshot.followup_creation_rate == 1.0
    assert metrics_record.record_id == "metrics_001"
    assert any(item.evidence_type == "metrics_export_summary" for item in evidence)


def test_repeat_debate_runs_are_deterministic_and_preserve_prior_archives(tmp_path: Path) -> None:
    def inner_voice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"turn_type":"objection",'
                        '"message_text":"The evidence is still stale.",'
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
                        "message": {
                            "content": (
                                '{"final_resolution":"block_pending_checks",'
                                '"prevailing_side":"inner_voice",'
                                '"resolution_summary":"Wait for refreshed evidence.",'
                                '"rationale_summary":"The disagreement turns on stale proof.",'
                                '"required_followups":["refresh evidence"],'
                                '"unresolved_risks":["stale proof"]}'
                            )
                        },
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    plugin, ledger_service = make_inner_voice_plugin(
        tmp_path,
        httpx.MockTransport(inner_voice_handler),
    )
    arbiter = make_arbiter(tmp_path, httpx.MockTransport(arbiter_handler), ledger_service)
    coordinator = InnerVoiceCoordinator(plugin, arbiter, plugin.archiver, ledger_service)
    request = InnerVoiceDebateRequest(
        stage=InnerVoiceStage.PRE_EXECUTION,
        subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
        subject_id="plan_repeat_001",
        review_goal="Resolve the disagreement.",
        claim_summary="The plan should move forward.",
        disagreement_summary="Proceed or stop.",
        openclaw_initial_position="Proceed with the current plan.",
        openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
        openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
        max_debate_rounds=1,
    )

    first = coordinator.run_debate(
        request.model_copy(update={"debate_id": "debate_repeat_001"}),
        openclaw=StaticResponder(
            DebateResponderOutput(
                turn_type=DebateTurnType.REBUTTAL,
                message_text="Proceed anyway.",
                disposition_signal=InnerVoiceDisposition.PROCEED,
            )
        ),
    )
    first_transcript = ledger_service.list_evidence_for_related(
        related_type=RecordType.INNER_VOICE_DEBATE,
        related_id=first.session.debate_id,
    )[0]
    first_transcript_text = Path(first_transcript.archive_path).read_text(encoding="utf-8")
    second = coordinator.run_debate(
        request.model_copy(update={"debate_id": "debate_repeat_002"}),
        openclaw=StaticResponder(
            DebateResponderOutput(
                turn_type=DebateTurnType.REBUTTAL,
                message_text="Proceed anyway.",
                disposition_signal=InnerVoiceDisposition.PROCEED,
            )
        ),
    )

    assert first.final_resolution_source == second.final_resolution_source == "arbiter"
    assert first.arbiter_result is not None
    assert second.arbiter_result is not None
    assert first.arbiter_result.final_resolution == second.arbiter_result.final_resolution
    assert first_transcript_text == Path(first_transcript.archive_path).read_text(encoding="utf-8")
    assert ledger_service.get_related_events(related_type=RecordType.SPEND_REQUEST) == []
    assert ledger_service.get_related_events(related_type=RecordType.WALLET_TRANSACTION) == []
    assert ledger_service.get_related_events(related_type=RecordType.EMAIL_DRAFT) == []


def test_audit_events_and_placeholder_archives_remain_consistent(tmp_path: Path) -> None:
    def converged_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"turn_type":"rebuttal",'
                        '"message_text":"Proceed with the bounded plan.",'
                        '"cited_evidence_ids":["ev_1"],'
                        '"disposition_signal":"proceed",'
                        '"max_unresolved_severity":"low",'
                        '"request_arbiter":false}'
                    )
                },
                "done_reason": "stop",
            },
        )

    plugin, ledger_service = make_inner_voice_plugin(
        tmp_path,
        httpx.MockTransport(converged_handler),
        archive_debate_transcript=False,
        archive_debate_turn_metadata=False,
    )
    arbiter = make_arbiter(
        tmp_path,
        httpx.MockTransport(lambda request: httpx.Response(200, json={})),
        ledger_service,
    )
    coordinator = InnerVoiceCoordinator(plugin, arbiter, plugin.archiver, ledger_service)
    outcome = coordinator.run_debate(
        InnerVoiceDebateRequest(
            debate_id="debate_placeholder_001",
            stage=InnerVoiceStage.PRE_EXECUTION,
            subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
            subject_id="plan_placeholder_001",
            review_goal="Resolve the disagreement.",
            claim_summary="The plan should move forward.",
            disagreement_summary="Proceed or stop.",
            openclaw_initial_position="Proceed with the current plan.",
            openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
            openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
            max_debate_rounds=2,
        ),
        openclaw=StaticResponder(
            DebateResponderOutput(
                turn_type=DebateTurnType.REBUTTAL,
                message_text="Proceed with the bounded plan.",
                disposition_signal=InnerVoiceDisposition.PROCEED,
            )
        ),
    )
    debate_evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.INNER_VOICE_DEBATE,
        related_id=outcome.session.debate_id,
    )
    transcript = next(
        item for item in debate_evidence if item.evidence_type == "inner_voice_debate_transcript"
    )
    summary = next(
        item for item in debate_evidence if item.evidence_type == "inner_voice_debate_summary"
    )
    transcript_text = Path(transcript.archive_path).read_text(encoding="utf-8")
    summary_text = Path(summary.archive_path).read_text(encoding="utf-8")
    audit_events = ledger_service.get_related_events(
        related_type=RecordType.AUDIT_EVENT,
        event_type="record_audit_event",
    )
    event_names: list[str] = []
    for event in audit_events:
        payload = event.payload
        nested_payload = payload.get("payload")
        if payload.get("related_record_id") != outcome.session.debate_id or not isinstance(
            nested_payload, dict
        ):
            continue
        event_name = nested_payload.get("event_name")
        if isinstance(event_name, str):
            event_names.append(event_name)

    assert outcome.session.ended_reason is DebateEndedReason.CONVERGED
    assert "transcript_raw_archival_disabled" in transcript_text
    assert "Proceed with the bounded plan." not in transcript_text
    assert outcome.session.transcript_archive_ids[0] in summary_text
    assert '"turns"' not in summary_text
    assert event_names == [
        "inner_voice_debate_started",
        "inner_voice_debate_completed",
    ]


def test_arbiter_failure_records_expected_audit_trail(tmp_path: Path) -> None:
    def inner_voice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"turn_type":"objection",'
                        '"message_text":"The evidence is still stale.",'
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
        return httpx.Response(200, json={"choices": [{"message": {"content": "{bad-json}"}}]})

    plugin, ledger_service = make_inner_voice_plugin(
        tmp_path,
        httpx.MockTransport(inner_voice_handler),
    )
    arbiter = make_arbiter(tmp_path, httpx.MockTransport(arbiter_handler), ledger_service)
    coordinator = InnerVoiceCoordinator(plugin, arbiter, plugin.archiver, ledger_service)

    with pytest.raises(InnerVoiceDebateError, match="malformed JSON") as exc_info:
        coordinator.run_debate(
            InnerVoiceDebateRequest(
                debate_id="debate_failure_001",
                stage=InnerVoiceStage.PRE_EXECUTION,
                subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
                subject_id="plan_failure_001",
                review_goal="Resolve the disagreement.",
                claim_summary="The plan should move forward.",
                disagreement_summary="Proceed or stop.",
                openclaw_initial_position="Proceed with the current plan.",
                openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
                openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
                max_debate_rounds=1,
            ),
            openclaw=StaticResponder(
                DebateResponderOutput(
                    turn_type=DebateTurnType.REBUTTAL,
                    message_text="Proceed anyway.",
                    disposition_signal=InnerVoiceDisposition.PROCEED,
                )
            ),
        )
    audit_events = ledger_service.get_related_events(
        related_type=RecordType.AUDIT_EVENT,
        event_type="record_audit_event",
    )
    event_names: list[str] = []
    filtered_payloads: list[dict[str, object]] = []
    for event in audit_events:
        payload = event.payload
        nested_payload = payload.get("payload")
        if payload.get("related_record_id") != "debate_failure_001" or not isinstance(
            nested_payload, dict
        ):
            continue
        filtered_payloads.append(nested_payload)
        event_name = nested_payload.get("event_name")
        if isinstance(event_name, str):
            event_names.append(event_name)

    assert exc_info.value.failure is not None
    assert event_names == [
        "inner_voice_debate_started",
        "inner_voice_arbiter_escalation_requested",
        "inner_voice_arbiter_invocation_failed",
        "inner_voice_debate_failed",
    ]
    assert filtered_payloads[1]["triggered_by"] == "max_rounds_reached"
    assert filtered_payloads[2]["failure_class"] == "malformed_output"
    assert filtered_payloads[3]["subject_id"] == "plan_failure_001"


def test_mixed_quality_history_metrics_snapshot_stays_deterministic(tmp_path: Path) -> None:
    review_responses = iter(
        [
            '{"overall_assessment":"Proceed.",'
            '"recommended_disposition":"proceed",'
            '"confidence_adjustment":0,'
            '"objections":[],'
            '"missing_evidence":[],'
            '"stale_information_risks":[],'
            '"overlooked_constraints":[],'
            '"counterarguments":[],'
            '"recommended_followups":[]}',
            '{"overall_assessment":"Need more proof.",'
            '"recommended_disposition":"needs_review",'
            '"confidence_adjustment":-0.3,'
            '"objections":[],'
            '"missing_evidence":["fresh proof"],'
            '"stale_information_risks":["old context"],'
            '"overlooked_constraints":[],'
            '"counterarguments":[],'
            '"recommended_followups":["refresh proof"]}',
        ]
    )

    def review_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"message": {"content": next(review_responses)}, "done_reason": "stop"},
        )

    def debate_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"turn_type":"objection",'
                        '"message_text":"Still stale.",'
                        '"cited_evidence_ids":["ev_3"],'
                        '"disposition_signal":"needs_review",'
                        '"max_unresolved_severity":"high",'
                        '"request_arbiter":false}'
                    )
                },
                "done_reason": "stop",
            },
        )

    plugin, ledger_service = make_inner_voice_plugin(
        tmp_path,
        httpx.MockTransport(review_handler),
    )
    first_review = plugin.review(
        InnerVoiceReviewRequest(
            review_id="review_mix_001",
            stage=InnerVoiceStage.TOS_LEGAL_CHECK,
            subject_type=InnerVoiceSubjectType.OPPORTUNITY,
            subject_id="opp_mix_001",
            claim_summary="Proceed now.",
            review_goal="Challenge the current conclusion.",
        )
    )
    second_review = plugin.review(
        InnerVoiceReviewRequest(
            review_id="review_mix_002",
            stage=InnerVoiceStage.BUDGET_PLANNING,
            subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
            subject_id="plan_mix_001",
            claim_summary="Proceed now.",
            review_goal="Challenge the current conclusion.",
        )
    )
    debate_plugin = InnerVoicePlugin(
        plugin.config,
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=httpx.MockTransport(debate_handler),
    )
    good_arbiter = make_arbiter(
        tmp_path,
        httpx.MockTransport(
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
                                    '"resolution_summary":"Wait.",'
                                    '"rationale_summary":"Still stale.",'
                                    '"required_followups":["refresh proof"],'
                                    '"unresolved_risks":["stale proof"]}'
                                )
                            },
                        }
                    ]
                },
            )
        ),
        ledger_service,
    )
    outcome = InnerVoiceCoordinator(
        debate_plugin,
        good_arbiter,
        debate_plugin.archiver,
        ledger_service,
    ).run_debate(
        InnerVoiceDebateRequest(
            debate_id="debate_mix_001",
            stage=InnerVoiceStage.PRE_EXECUTION,
            subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
            subject_id="plan_mix_001",
            review_goal="Resolve the disagreement.",
            claim_summary="The plan should move forward.",
            disagreement_summary="Proceed or stop.",
            openclaw_initial_position="Proceed with the current plan.",
            openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
            openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
            max_debate_rounds=1,
        ),
        openclaw=StaticResponder(
            DebateResponderOutput(
                turn_type=DebateTurnType.REBUTTAL,
                message_text="Proceed anyway.",
                disposition_signal=InnerVoiceDisposition.PROCEED,
            )
        ),
    )
    bad_arbiter = make_arbiter(
        tmp_path,
        httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": []})),
        ledger_service,
    )
    try:
        bad_arbiter.resolve(
            ArbiterResolutionRequest(
                arbiter_review_id="arbiter_mix_fail_001",
                debate_id="debate_mix_fail_001",
                stage=InnerVoiceStage.PRE_EXECUTION,
                subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
                subject_id="plan_mix_002",
                openclaw_position_summary="Proceed",
                inner_voice_position_summary="Needs review",
                disagreement_summary="Proceed or stop.",
                transcript_archive_ids=["ev_mix_001"],
                transcript_summary="summary",
                resolution_goal="Resolve the disagreement.",
                triggered_by=DebateEndedReason.MAX_ROUNDS_REACHED,
            )
        )
    except ArbiterResolutionError as error:
        failed_arbiter = error.failure
    else:
        raise AssertionError("expected Arbiter resolution failure")

    snapshot = build_metrics_snapshot(
        [first_review, second_review],
        [outcome],
        [outcome.arbiter_result, failed_arbiter],
    )
    persisted = persist_metrics_snapshot(
        snapshot,
        ledger_service=ledger_service,
        archiver=plugin.archiver,
        snapshot_id="metrics_mix_001",
    )

    assert snapshot.provider_failure_rate == 0.25
    assert snapshot.arbiter_failure_rate == 0.5
    assert snapshot.invocation_count_by_stage["budget_planning"] == 1
    assert snapshot.needs_review_count_by_stage["budget_planning"] == 1
    assert persisted.record_id == "metrics_mix_001"
