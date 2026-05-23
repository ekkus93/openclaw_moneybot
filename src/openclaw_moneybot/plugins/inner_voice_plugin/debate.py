"""Bounded debate orchestration for inner voice disagreement handling."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from typing import Protocol

from openclaw_moneybot.plugins.inner_voice_plugin.arbiter import ArbiterService
from openclaw_moneybot.plugins.inner_voice_plugin.errors import (
    ArbiterResolutionError,
    InnerVoiceDebateError,
    InnerVoicePluginError,
)
from openclaw_moneybot.plugins.inner_voice_plugin.models import (
    ArbiterResolutionRequest,
    ArbiterResolutionResult,
    DebateResponderOutput,
    DebateResponderRequest,
    InnerVoiceDebateOutcome,
    InnerVoiceDebateRequest,
    InnerVoiceDebateSession,
    InnerVoiceDebateTurn,
    InnerVoiceFailureDetails,
    InnerVoiceMetricsSnapshot,
    ProviderResponseSummary,
)
from openclaw_moneybot.plugins.inner_voice_plugin.prompting import (
    archive_text,
    format_debate_transcript,
    render_json,
    sanitize_text,
    summarize_transcript,
)
from openclaw_moneybot.plugins.inner_voice_plugin.service import InnerVoicePlugin
from openclaw_moneybot.plugins.support import record_plugin_audit_event
from openclaw_moneybot.shared.types import (
    DebateEndedReason,
    DebateSpeaker,
    DebateTurnType,
    InnerVoiceDisposition,
    RecordType,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    EvidenceArchiveRequest,
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.support import record_structured_result
from openclaw_moneybot.utils.ids import make_id
from openclaw_moneybot.utils.time import utc_now


class DebateResponder(Protocol):
    """A participant that can produce one bounded debate turn."""

    def respond_to_debate(self, request: DebateResponderRequest) -> DebateResponderOutput:
        """Return one structured debate turn."""
        ...


class InnerVoiceCoordinator:
    """Run a bounded debate and escalate to the Arbiter when required."""

    def __init__(
        self,
        inner_voice: InnerVoicePlugin,
        arbiter: ArbiterService,
        archiver: ReceiptAndEvidenceArchiver,
        ledger_service: LedgerService,
    ) -> None:
        self.inner_voice = inner_voice
        self.arbiter = arbiter
        self.archiver = archiver
        self.ledger_service = ledger_service

    def run_debate(
        self,
        request: InnerVoiceDebateRequest,
        *,
        openclaw: DebateResponder,
        resolution_guard: (
            Callable[
                [
                    InnerVoiceDebateRequest,
                    Sequence[InnerVoiceDebateTurn],
                    InnerVoiceDisposition | None,
                    ArbiterResolutionResult | None,
                ],
                str | None,
            ]
            | None
        ) = None,
    ) -> InnerVoiceDebateOutcome:
        """Run a bounded debate session and resolve it through convergence or Arbiter."""

        if request.stage not in self.inner_voice.config.run_after_stages:
            msg = f"debate stage {request.stage.value} is not enabled in run_after_stages"
            raise ValueError(msg)
        debate_id = request.debate_id or make_id("debate")
        max_rounds = request.max_debate_rounds or self.inner_voice.config.max_debate_rounds
        turns: list[InnerVoiceDebateTurn] = []
        initial_turn = InnerVoiceDebateTurn(
            debate_id=debate_id,
            round_index=1,
            turn_index=1,
            speaker=DebateSpeaker.OPENCLAW,
            turn_type=DebateTurnType.PROPOSAL,
            message_text=request.openclaw_initial_position,
            cited_evidence_ids=[],
            disposition_signal=request.openclaw_initial_disposition,
            max_unresolved_severity=request.openclaw_initial_max_unresolved_severity,
            request_arbiter=False,
            created_at=utc_now().isoformat(timespec="seconds"),
        )
        turns.append(initial_turn)

        ended_reason = DebateEndedReason.FAILURE
        converged = False
        arbiter_requested_by: DebateSpeaker | None = None
        arbiter_review_id: str | None = None
        resolved_disposition: InnerVoiceDisposition | None = None
        arbiter_result = None
        resolution_outcome = "needs_review"
        orchestrator_escalation_reason: str | None = None

        record_plugin_audit_event(
            self.ledger_service,
            related_record_id=debate_id,
            event_name="inner_voice_debate_started",
            payload={
                "stage": request.stage.value,
                "subject_type": request.subject_type.value,
                "subject_id": request.subject_id,
                "max_rounds": max_rounds,
            },
        )
        try:
            for round_index in range(1, max_rounds + 1):
                inner_voice_output = self.inner_voice.respond_to_debate(
                    DebateResponderRequest(
                        debate_id=debate_id,
                        stage=request.stage,
                        subject_type=request.subject_type,
                        subject_id=request.subject_id,
                        speaker=DebateSpeaker.INNER_VOICE,
                        round_index=round_index,
                        max_rounds=max_rounds,
                        claim_summary=request.claim_summary,
                        disagreement_summary=request.disagreement_summary,
                        evidence_summary=request.evidence_summary,
                        constraints_summary=request.constraints_summary,
                        policy_summary=request.policy_summary,
                        tos_summary=request.tos_summary,
                        budget_summary=request.budget_summary,
                        prior_turns=turns,
                        latest_counterparty_message=turns[-1].message_text,
                    )
                )
                inner_voice_turn = self.inner_voice.make_debate_turn(
                    debate_id=debate_id,
                    round_index=round_index,
                    turn_index=len(turns) + 1,
                    speaker=DebateSpeaker.INNER_VOICE,
                    output=inner_voice_output,
                    created_at=utc_now().isoformat(timespec="seconds"),
                )
                turns.append(inner_voice_turn)
                if inner_voice_turn.request_arbiter:
                    ended_reason = DebateEndedReason.REQUEST_ARBITER
                    arbiter_requested_by = DebateSpeaker.INNER_VOICE
                    break
                if self._has_converged(turns[-2], turns[-1]):
                    converged = True
                    ended_reason = DebateEndedReason.CONVERGED
                    resolved_disposition = turns[-1].disposition_signal
                    if resolved_disposition is not None:
                        resolution_outcome = resolved_disposition.value
                    break
                if round_index >= max_rounds:
                    ended_reason = DebateEndedReason.MAX_ROUNDS_REACHED
                    break

                openclaw_output = openclaw.respond_to_debate(
                    DebateResponderRequest(
                        debate_id=debate_id,
                        stage=request.stage,
                        subject_type=request.subject_type,
                        subject_id=request.subject_id,
                        speaker=DebateSpeaker.OPENCLAW,
                        round_index=round_index + 1,
                        max_rounds=max_rounds,
                        claim_summary=request.claim_summary,
                        disagreement_summary=request.disagreement_summary,
                        evidence_summary=request.evidence_summary,
                        constraints_summary=request.constraints_summary,
                        policy_summary=request.policy_summary,
                        tos_summary=request.tos_summary,
                        budget_summary=request.budget_summary,
                        prior_turns=turns,
                        latest_counterparty_message=turns[-1].message_text,
                    )
                )
                openclaw_turn = InnerVoiceDebateTurn(
                    debate_id=debate_id,
                    round_index=round_index + 1,
                    turn_index=len(turns) + 1,
                    speaker=DebateSpeaker.OPENCLAW,
                    turn_type=openclaw_output.turn_type,
                    message_text=openclaw_output.message_text,
                    cited_evidence_ids=openclaw_output.cited_evidence_ids,
                    disposition_signal=openclaw_output.disposition_signal,
                    max_unresolved_severity=openclaw_output.max_unresolved_severity,
                    request_arbiter=openclaw_output.request_arbiter,
                    created_at=utc_now().isoformat(timespec="seconds"),
                )
                turns.append(openclaw_turn)
                if openclaw_turn.request_arbiter:
                    ended_reason = DebateEndedReason.REQUEST_ARBITER
                    arbiter_requested_by = DebateSpeaker.OPENCLAW
                    break
                if self._has_converged(turns[-2], turns[-1]):
                    converged = True
                    ended_reason = DebateEndedReason.CONVERGED
                    resolved_disposition = turns[-1].disposition_signal
                    if resolved_disposition is not None:
                        resolution_outcome = resolved_disposition.value
                    break
            transcript_archive_ids = self._archive_debate_transcript(
                debate_id=debate_id,
                stage=request.stage.value,
                subject_id=request.subject_id,
                turns=turns,
                ended_reason=ended_reason,
            )
            if not converged:
                arbiter_review_id = make_id("arbiter")
                record_plugin_audit_event(
                    self.ledger_service,
                    related_record_id=debate_id,
                    event_name="inner_voice_arbiter_escalation_requested",
                    payload={
                        "debate_id": debate_id,
                        "arbiter_review_id": arbiter_review_id,
                        "requested_by": (
                            arbiter_requested_by.value
                            if arbiter_requested_by is not None
                            else "system"
                        ),
                        "triggered_by": ended_reason.value,
                    },
                )
                arbiter_result = self.arbiter.resolve(
                    ArbiterResolutionRequest(
                        arbiter_review_id=arbiter_review_id,
                        debate_id=debate_id,
                        stage=request.stage,
                        subject_type=request.subject_type,
                        subject_id=request.subject_id,
                        openclaw_review_id=request.openclaw_review_id,
                        inner_voice_review_id=request.inner_voice_review_id,
                        openclaw_position_summary=self._latest_position(
                            turns,
                            DebateSpeaker.OPENCLAW,
                        ),
                        inner_voice_position_summary=self._latest_position(
                            turns,
                            DebateSpeaker.INNER_VOICE,
                        ),
                        disagreement_summary=request.disagreement_summary,
                        transcript_archive_ids=transcript_archive_ids,
                        transcript_summary=summarize_transcript(
                            [turn.model_dump(mode="json") for turn in turns]
                        ),
                        evidence_summary=request.evidence_summary,
                        constraints_summary=request.constraints_summary,
                        policy_summary=request.policy_summary,
                        tos_summary=request.tos_summary,
                        budget_summary=request.budget_summary,
                        resolution_goal=request.review_goal,
                        triggered_by=ended_reason,
                    ),
                    required=True,
                )
                resolution_outcome = arbiter_result.final_resolution.value
            if resolution_guard is not None:
                orchestrator_escalation_reason = resolution_guard(
                    request,
                    turns,
                    resolved_disposition,
                    arbiter_result,
                )
                if orchestrator_escalation_reason is not None:
                    ended_reason = DebateEndedReason.ORCHESTRATOR_ESCALATION
                    record_plugin_audit_event(
                        self.ledger_service,
                        related_record_id=debate_id,
                        event_name="inner_voice_orchestrator_escalated",
                        payload={
                            "stage": request.stage.value,
                            "subject_type": request.subject_type.value,
                            "subject_id": request.subject_id,
                            "reason": orchestrator_escalation_reason,
                            "resolution_outcome": resolution_outcome,
                        },
                    )
            summary_archive_id = self._archive_debate_summary(
                debate_id=debate_id,
                stage=request.stage.value,
                turns=turns,
                ended_reason=ended_reason,
                transcript_archive_ids=transcript_archive_ids,
                openclaw_review_id=request.openclaw_review_id,
                inner_voice_review_id=request.inner_voice_review_id,
                arbiter_review_id=arbiter_result.arbiter_review_id if arbiter_result else None,
                arbiter_final_resolution=(
                    arbiter_result.final_resolution.value if arbiter_result is not None else None
                ),
                arbiter_prevailing_side=(
                    arbiter_result.prevailing_side.value if arbiter_result is not None else None
                ),
                resolved_disposition=(
                    resolved_disposition.value if resolved_disposition is not None else None
                ),
                orchestrator_escalation_reason=orchestrator_escalation_reason,
            )
            session = InnerVoiceDebateSession(
                debate_id=debate_id,
                stage=request.stage,
                subject_type=request.subject_type,
                subject_id=request.subject_id,
                initiated_by=DebateSpeaker.OPENCLAW,
                openclaw_review_id=request.openclaw_review_id,
                inner_voice_review_id=request.inner_voice_review_id,
                max_rounds_configured=max_rounds,
                completed_rounds=max(turn.round_index for turn in turns),
                ended_reason=ended_reason,
                converged=converged,
                arbiter_requested_by=arbiter_requested_by,
                arbiter_review_id=(
                    arbiter_result.arbiter_review_id if arbiter_result is not None else None
                ),
                transcript_archive_ids=transcript_archive_ids,
                summary_archive_id=summary_archive_id,
            )
            ledger_record = record_structured_result(
                self.ledger_service,
                record_id=debate_id,
                record_type=RecordType.INNER_VOICE_DEBATE,
                related_record_id=request.subject_id,
                payload={
                    "stage": request.stage.value,
                    "subject_type": request.subject_type.value,
                    "subject_id": request.subject_id,
                    "openclaw_review_id": request.openclaw_review_id,
                    "inner_voice_review_id": request.inner_voice_review_id,
                    "ended_reason": ended_reason.value,
                    "converged": converged,
                    "completed_rounds": session.completed_rounds,
                    "final_resolution_source": "debate" if converged else "arbiter",
                    "resolution_outcome": resolution_outcome,
                    "arbiter_requested_by": arbiter_requested_by.value
                    if arbiter_requested_by is not None
                    else None,
                    "arbiter_review_id": session.arbiter_review_id,
                    "transcript_archive_ids": transcript_archive_ids,
                    "summary_archive_id": summary_archive_id,
                    "orchestrator_escalation_reason": orchestrator_escalation_reason,
                },
            )
            record_plugin_audit_event(
                self.ledger_service,
                related_record_id=debate_id,
                event_name="inner_voice_debate_completed",
                payload={
                    "ended_reason": ended_reason.value,
                    "converged": converged,
                    "completed_rounds": session.completed_rounds,
                    "arbiter_review_id": session.arbiter_review_id,
                    "resolved_disposition": (
                        resolved_disposition.value
                        if resolved_disposition is not None
                        else (
                            arbiter_result.final_resolution.value
                            if arbiter_result is not None
                            else "needs_review"
                        )
                    ),
                    "orchestrator_escalation_reason": orchestrator_escalation_reason,
                },
            )
            return InnerVoiceDebateOutcome(
                session=session,
                turns=turns,
                final_resolution_source="debate" if converged else "arbiter",
                resolved_disposition=resolved_disposition,
                arbiter_result=arbiter_result,
                ledger_record=ledger_record,
            )
        except (InnerVoicePluginError, ArbiterResolutionError, ValueError) as error:
            if isinstance(error, ArbiterResolutionError) and arbiter_review_id is not None:
                record_plugin_audit_event(
                    self.ledger_service,
                    related_record_id=debate_id,
                    event_name="inner_voice_arbiter_invocation_failed",
                    payload={
                        "arbiter_review_id": arbiter_review_id,
                        "failure_class": error.failure_class,
                        "failure_message": str(error),
                    },
                )
            failure_class = getattr(error, "failure_class", "debate_error")
            failure = self._persist_failure(
                debate_id=debate_id,
                subject_type=request.subject_type.value,
                subject_id=request.subject_id,
                stage=request.stage.value,
                failure_class=failure_class,
                failure_message=str(error),
            )
            raise InnerVoiceDebateError(
                str(error),
                failure_class=failure.failure_class,
                failure=failure,
            ) from error

    @staticmethod
    def _has_converged(
        first: InnerVoiceDebateTurn,
        second: InnerVoiceDebateTurn,
    ) -> bool:
        if first.speaker is second.speaker:
            return False
        if first.request_arbiter or second.request_arbiter:
            return False
        if first.disposition_signal is None or second.disposition_signal is None:
            return False
        if first.disposition_signal is not second.disposition_signal:
            return False
        severe = {"high", "block"}
        first_severity = (
            first.max_unresolved_severity.value if first.max_unresolved_severity else None
        )
        second_severity = (
            second.max_unresolved_severity.value if second.max_unresolved_severity else None
        )
        return first_severity not in severe and second_severity not in severe

    def _archive_debate_transcript(
        self,
        *,
        debate_id: str,
        stage: str,
        subject_id: str,
        turns: Sequence[InnerVoiceDebateTurn],
        ended_reason: DebateEndedReason,
    ) -> list[str]:
        transcript_text = format_debate_transcript([turn.model_dump(mode="json") for turn in turns])
        if self.inner_voice.config.archive_debate_transcript:
            transcript_content = archive_text(
                transcript_text,
                raw_allowed=True,
                redaction_mode=self.inner_voice.config.archive_redaction_mode,
                max_chars=self.inner_voice.config.max_input_chars,
            )
            transcript_notes = f"Inner voice debate transcript for {stage}"
        else:
            transcript_content = render_json(
                {
                    "archival_status": "transcript_raw_archival_disabled",
                    "ended_reason": ended_reason.value,
                    "turn_count": len(turns),
                    "summary_archive_expected": True,
                }
            )
            transcript_notes = f"Inner voice debate transcript placeholder for {stage}"
        transcript_archive_id = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.INNER_VOICE_DEBATE,
                related_id=debate_id,
                evidence_type="inner_voice_debate_transcript",
                content_text=transcript_content,
                notes=transcript_notes,
                summary_hint=f"Debate transcript for {subject_id}",
            )
        ).evidence_id
        return [transcript_archive_id]

    def _archive_debate_summary(
        self,
        *,
        debate_id: str,
        stage: str,
        transcript_archive_ids: Sequence[str],
        turns: Sequence[InnerVoiceDebateTurn],
        ended_reason: DebateEndedReason,
        openclaw_review_id: str | None,
        inner_voice_review_id: str | None,
        arbiter_review_id: str | None = None,
        arbiter_final_resolution: str | None = None,
        arbiter_prevailing_side: str | None = None,
        resolved_disposition: str | None = None,
        orchestrator_escalation_reason: str | None = None,
    ) -> str:
        summary_payload: dict[str, object] = {
            "ended_reason": ended_reason.value,
            "turn_count": len(turns),
            "transcript_archive_ids": list(transcript_archive_ids),
            "openclaw_review_id": openclaw_review_id,
            "inner_voice_review_id": inner_voice_review_id,
            "transcript_summary": summarize_transcript(
                [turn.model_dump(mode="json") for turn in turns]
            ),
        }
        if arbiter_review_id is not None:
            summary_payload["arbiter_review_id"] = arbiter_review_id
        resolution_notes = {
            "resolved_disposition": resolved_disposition,
            "arbiter_final_resolution": arbiter_final_resolution,
            "arbiter_prevailing_side": arbiter_prevailing_side,
        }
        if any(value is not None for value in resolution_notes.values()):
            summary_payload["resolution_notes"] = resolution_notes
        if orchestrator_escalation_reason is not None:
            summary_payload["orchestrator_escalation_reason"] = (
                orchestrator_escalation_reason
            )
        if self.inner_voice.config.archive_debate_turn_metadata:
            summary_payload["turns"] = self._turn_metadata(turns)
        summary_archive_id = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.INNER_VOICE_DEBATE,
                related_id=debate_id,
                evidence_type="inner_voice_debate_summary",
                content_text=archive_text(
                    render_json(summary_payload),
                    raw_allowed=self.inner_voice.config.archive_debate_turn_metadata,
                    redaction_mode=self.inner_voice.config.archive_redaction_mode,
                    max_chars=self.inner_voice.config.max_input_chars,
                ),
                notes=f"Inner voice debate summary for {stage}",
                summary_hint="Debate summary snapshot",
            )
        ).evidence_id
        return summary_archive_id

    def _persist_failure(
        self,
        *,
        debate_id: str,
        subject_type: str,
        subject_id: str,
        stage: str,
        failure_class: str,
        failure_message: str,
    ) -> InnerVoiceFailureDetails:
        failure = InnerVoiceFailureDetails(
            record_id=debate_id,
            record_type=RecordType.INNER_VOICE_DEBATE,
            stage=stage,
            subject_type=subject_type,
            subject_id=subject_id,
            failure_class=failure_class,
            failure_message=failure_message,
            was_required=True,
        )
        self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.INNER_VOICE_DEBATE,
                related_id=debate_id,
                evidence_type="inner_voice_failure",
                content_text=sanitize_text(failure_message),
                notes="Inner voice debate failure summary",
                summary_hint=failure_class,
            )
        )
        record_plugin_audit_event(
            self.ledger_service,
            related_record_id=debate_id,
            event_name="inner_voice_debate_failed",
            payload={
                "stage": stage,
                "subject_type": subject_type,
                "subject_id": subject_id,
                "failure_class": failure_class,
                "failure_message": failure_message,
                "failure": failure.model_dump(mode="json"),
            },
        )
        record_structured_result(
            self.ledger_service,
            record_id=debate_id,
            record_type=RecordType.INNER_VOICE_DEBATE,
            related_record_id=subject_id,
            payload={
                "status": "failed",
                "stage": stage,
                "subject_type": subject_type,
                "subject_id": subject_id,
                "resolved_disposition": "needs_review",
                "failure_class": failure_class,
                "failure_message": failure_message,
                "failure": failure.model_dump(mode="json"),
            },
        )
        return failure

    @staticmethod
    def _latest_position(turns: Sequence[InnerVoiceDebateTurn], speaker: DebateSpeaker) -> str:
        for turn in reversed(turns):
            if turn.speaker is speaker:
                return turn.message_text
        return ""

    @staticmethod
    def _turn_metadata(turns: Sequence[InnerVoiceDebateTurn]) -> list[dict[str, object]]:
        return [
            {
                "round_index": turn.round_index,
                "turn_index": turn.turn_index,
                "speaker": turn.speaker.value,
                "turn_type": turn.turn_type.value,
                "request_arbiter": turn.request_arbiter,
                "cited_evidence_ids": turn.cited_evidence_ids,
                "disposition_signal": (
                    turn.disposition_signal.value if turn.disposition_signal is not None else None
                ),
                "max_unresolved_severity": (
                    turn.max_unresolved_severity.value
                    if turn.max_unresolved_severity is not None
                    else None
                ),
            }
            for turn in turns
        ]


def build_metrics_snapshot(
    review_results: Sequence[object],
    debate_outcomes: Sequence[InnerVoiceDebateOutcome],
    arbiter_results: Sequence[object],
) -> InnerVoiceMetricsSnapshot:
    """Build a bounded metrics snapshot from persisted results."""

    invocation_count_by_stage: Counter[str] = Counter()
    needs_review_count_by_stage: Counter[str] = Counter()
    objection_severity_counts: Counter[str] = Counter()
    prompt_sizes: list[int] = []
    response_sizes: list[int] = []

    for review in review_results:
        stage = getattr(review, "stage", None)
        if stage is not None:
            stage_value = stage.value if hasattr(stage, "value") else str(stage)
            invocation_count_by_stage[stage_value] += 1
            disposition = getattr(review, "recommended_disposition", None)
            if disposition is None:
                disposition_value = "none"
            elif hasattr(disposition, "value"):
                disposition_value = disposition.value
            else:
                disposition_value = str(disposition)
            if disposition_value == "needs_review":
                needs_review_count_by_stage[stage_value] += 1
        objections = getattr(review, "objections", [])
        for objection in objections:
            severity = getattr(objection, "severity", None)
            if severity is not None:
                severity_value = severity.value if hasattr(severity, "value") else str(severity)
                objection_severity_counts[severity_value] += 1
        prompt_chars = _summary_int_value(
            getattr(review, "raw_response_summary", {}),
            "prompt_chars",
        )
        if prompt_chars is not None:
            prompt_sizes.append(prompt_chars)
        response_chars = _summary_int_value(
            getattr(review, "raw_response_summary", {}),
            "response_chars",
        )
        if response_chars is not None:
            response_sizes.append(response_chars)
    debate_session_count_by_stage: Counter[str] = Counter()
    completed_rounds: list[int] = []
    transcript_sizes: list[int] = []
    arbiter_request_count = 0
    arbiter_invocation_count = 0
    for outcome in debate_outcomes:
        debate_session_count_by_stage[outcome.session.stage.value] += 1
        completed_rounds.append(outcome.session.completed_rounds)
        if outcome.session.arbiter_requested_by is not None:
            arbiter_request_count += 1
        if outcome.arbiter_result is not None:
            arbiter_invocation_count += 1
        for turn in outcome.turns:
            transcript_sizes.append(len(turn.message_text))

    prevailing_side_counts: Counter[str] = Counter()
    arbiter_failures = 0
    followup_count = 0
    for arbiter in arbiter_results:
        if getattr(arbiter, "final_resolution", None) is None:
            arbiter_failures += 1
            continue
        prevailing_side = getattr(arbiter, "prevailing_side", None)
        if prevailing_side is not None:
            prevailing_side_value = (
                prevailing_side.value if hasattr(prevailing_side, "value") else str(prevailing_side)
            )
            prevailing_side_counts[prevailing_side_value] += 1
        followups = getattr(arbiter, "required_followups", [])
        if isinstance(followups, Sequence):
            followup_count += len(followups)
        prompt_chars = _summary_int_value(
            getattr(arbiter, "raw_response_summary", {}),
            "prompt_chars",
        )
        if prompt_chars is not None:
            prompt_sizes.append(prompt_chars)
        response_chars = _summary_int_value(
            getattr(arbiter, "raw_response_summary", {}),
            "response_chars",
        )
        if response_chars is not None:
            response_sizes.append(response_chars)
        if hasattr(arbiter, "failure_class") or getattr(arbiter, "failure", None) is not None:
            arbiter_failures += 1

    total_debates = len(debate_outcomes) or 1
    total_arbiters = len(arbiter_results) or 1
    total_provider_results = len(review_results) + len(arbiter_results) or 1
    provider_failures = sum(
        1
        for item in [*review_results, *arbiter_results]
        if hasattr(item, "failure_class") or getattr(item, "failure", None) is not None
    )
    return InnerVoiceMetricsSnapshot(
        invocation_count_by_stage=dict(invocation_count_by_stage),
        needs_review_count_by_stage=dict(needs_review_count_by_stage),
        objection_severity_counts=dict(objection_severity_counts),
        debate_session_count_by_stage=dict(debate_session_count_by_stage),
        average_completed_debate_rounds=(
            sum(completed_rounds) / len(completed_rounds) if completed_rounds else 0.0
        ),
        arbiter_request_rate=arbiter_request_count / total_debates,
        arbiter_invocation_rate=arbiter_invocation_count / total_debates,
        arbiter_prevailing_side_counts=dict(prevailing_side_counts),
        arbiter_failure_rate=arbiter_failures / total_arbiters,
        followup_creation_rate=followup_count / total_arbiters,
        provider_failure_rate=provider_failures / total_provider_results,
        average_prompt_size_chars=(sum(prompt_sizes) / len(prompt_sizes) if prompt_sizes else 0.0),
        average_response_size_chars=(
            sum(response_sizes) / len(response_sizes) if response_sizes else 0.0
        ),
        average_transcript_size_chars=(
            sum(transcript_sizes) / len(transcript_sizes) if transcript_sizes else 0.0
        ),
    )


def _summary_int_value(summary: object, key: str) -> int | None:
    if isinstance(summary, ProviderResponseSummary):
        value = getattr(summary, key, None)
        return value if isinstance(value, int) else None
    if isinstance(summary, dict):
        value = summary.get(key)
        return value if isinstance(value, int) else None
    return None
