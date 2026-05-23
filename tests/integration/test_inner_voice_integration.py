"""Integration coverage for inner voice review, debate logging, and Arbiter escalation."""

from __future__ import annotations

from pathlib import Path

import httpx

from openclaw_moneybot.plugins.inner_voice_plugin import (
    ArbiterService,
    DebateResponderOutput,
    DebateResponderRequest,
    InnerVoiceCoordinator,
    InnerVoiceDebateRequest,
    InnerVoicePlugin,
    InnerVoiceReviewRequest,
)
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
) -> tuple[InnerVoicePlugin, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = InnerVoicePlugin(
        InnerVoiceConfig(
            enabled=True,
            provider=ProviderName.OLLAMA,
            model_name="ollama-test",
            base_url="http://127.0.0.1:11434",
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
