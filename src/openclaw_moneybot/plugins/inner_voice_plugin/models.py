"""Models for inner voice review, debate, and Arbiter resolution."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import Field, HttpUrl, JsonValue

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord
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
)


class EvidenceSummary(MoneyBotModel):
    """A bounded evidence summary passed into reviews."""

    evidence_id: str
    evidence_type: str = Field(min_length=1, max_length=128)
    source_url: HttpUrl | None = None
    captured_at: str
    summary: str = Field(min_length=1, max_length=10_000)
    freshness_hint: str | None = Field(default=None, max_length=256)


class InnerVoicePromptRequest(MoneyBotModel):
    """Normalized prompt envelope for one provider call."""

    request_id: str
    provider: ProviderName
    model_name: str
    system_prompt: str
    user_prompt: str
    response_schema_json: dict[str, JsonValue] = Field(default_factory=dict)
    temperature: float = Field(ge=0.0, le=1.0)
    top_p: float | None = Field(default=None, gt=0.0, le=1.0)
    max_output_tokens: int = Field(gt=0)
    timeout_seconds: float = Field(gt=0)


class ArbiterPromptRequest(InnerVoicePromptRequest):
    """Normalized prompt envelope for Arbiter resolution."""


class InnerVoiceRawResponse(MoneyBotModel):
    """Raw provider response normalized behind one contract."""

    provider: ProviderName
    model_name: str
    response_text: str
    parsed_json: dict[str, JsonValue] | None = None
    finish_reason: str | None = None
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    raw_payload: dict[str, JsonValue] = Field(default_factory=dict)


class InnerVoiceReviewRequest(MoneyBotModel):
    """A structured request for one inner-voice critique pass."""

    review_id: str
    stage: InnerVoiceStage
    subject_type: InnerVoiceSubjectType
    subject_id: str
    claim_summary: str = Field(min_length=1, max_length=10_000)
    structured_context: dict[str, JsonValue] = Field(default_factory=dict)
    evidence_summary: list[EvidenceSummary] = Field(default_factory=list)
    constraints_summary: list[str] = Field(default_factory=list)
    policy_summary: str | None = Field(default=None, max_length=8_000)
    tos_summary: str | None = Field(default=None, max_length=8_000)
    budget_summary: str | None = Field(default=None, max_length=8_000)
    review_goal: str = Field(min_length=1, max_length=2_000)
    max_objections: int = Field(default=8, gt=0, le=20)


class InnerVoiceObjection(MoneyBotModel):
    """One structured inner-voice objection."""

    title: str = Field(min_length=1, max_length=256)
    severity: InnerVoiceObjectionSeverity
    reason: str = Field(min_length=1, max_length=4_000)
    evidence_basis: str | None = Field(default=None, max_length=2_000)
    suggested_resolution: str | None = Field(default=None, max_length=2_000)


class InnerVoiceReviewOutput(MoneyBotModel):
    """Provider-emitted critique content before governed persistence is added."""

    overall_assessment: str = Field(min_length=1, max_length=6_000)
    recommended_disposition: InnerVoiceDisposition
    confidence_adjustment: float | None = Field(default=None, ge=-1.0, le=0.0)
    objections: list[InnerVoiceObjection] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    stale_information_risks: list[str] = Field(default_factory=list)
    overlooked_constraints: list[str] = Field(default_factory=list)
    counterarguments: list[str] = Field(default_factory=list)
    recommended_followups: list[str] = Field(default_factory=list)


class InnerVoiceReviewResult(InnerVoiceReviewOutput):
    """The full persisted inner-voice review result."""

    review_id: str
    provider: ProviderName
    model_name: str
    stage: InnerVoiceStage
    subject_type: InnerVoiceSubjectType
    subject_id: str
    raw_response_summary: dict[str, JsonValue] = Field(default_factory=dict)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord


class DebateResponderRequest(MoneyBotModel):
    """A request for one debate turn from a participant."""

    debate_id: str
    stage: InnerVoiceStage
    subject_type: InnerVoiceSubjectType
    subject_id: str
    speaker: DebateSpeaker
    round_index: int = Field(gt=0)
    max_rounds: int = Field(gt=0)
    claim_summary: str = Field(min_length=1, max_length=10_000)
    disagreement_summary: str = Field(min_length=1, max_length=10_000)
    evidence_summary: list[EvidenceSummary] = Field(default_factory=list)
    constraints_summary: list[str] = Field(default_factory=list)
    policy_summary: str | None = Field(default=None, max_length=8_000)
    tos_summary: str | None = Field(default=None, max_length=8_000)
    budget_summary: str | None = Field(default=None, max_length=8_000)
    prior_turns: list[InnerVoiceDebateTurn] = Field(default_factory=list)
    latest_counterparty_message: str | None = Field(default=None, max_length=10_000)


class DebateResponderOutput(MoneyBotModel):
    """A structured debate turn generated by one participant."""

    turn_type: DebateTurnType
    message_text: str = Field(min_length=1, max_length=10_000)
    cited_evidence_ids: list[str] = Field(default_factory=list)
    disposition_signal: InnerVoiceDisposition | None = None
    max_unresolved_severity: InnerVoiceObjectionSeverity | None = None
    request_arbiter: bool = False


class InnerVoiceDebateTurn(DebateResponderOutput):
    """One persisted debate turn."""

    debate_id: str
    round_index: int = Field(gt=0)
    turn_index: int = Field(gt=0)
    speaker: DebateSpeaker
    created_at: str


class InnerVoiceDebateSession(MoneyBotModel):
    """A bounded debate session between OpenClaw and the inner voice."""

    debate_id: str
    stage: InnerVoiceStage
    subject_type: InnerVoiceSubjectType
    subject_id: str
    initiated_by: DebateSpeaker
    max_rounds_configured: int = Field(gt=0)
    completed_rounds: int = Field(ge=0)
    ended_reason: DebateEndedReason
    converged: bool = False
    arbiter_requested_by: DebateSpeaker | None = None
    arbiter_review_id: str | None = None
    transcript_archive_ids: list[str] = Field(default_factory=list)
    summary_archive_id: str | None = None


class InnerVoiceDebateRequest(MoneyBotModel):
    """Request for a bounded debate session."""

    debate_id: str | None = None
    stage: InnerVoiceStage
    subject_type: InnerVoiceSubjectType
    subject_id: str
    review_goal: str = Field(min_length=1, max_length=2_000)
    claim_summary: str = Field(min_length=1, max_length=10_000)
    disagreement_summary: str = Field(min_length=1, max_length=10_000)
    openclaw_initial_position: str = Field(min_length=1, max_length=10_000)
    openclaw_initial_disposition: InnerVoiceDisposition | None = None
    openclaw_initial_max_unresolved_severity: InnerVoiceObjectionSeverity | None = None
    openclaw_review_id: str | None = None
    inner_voice_review_id: str | None = None
    evidence_summary: list[EvidenceSummary] = Field(default_factory=list)
    constraints_summary: list[str] = Field(default_factory=list)
    policy_summary: str | None = Field(default=None, max_length=8_000)
    tos_summary: str | None = Field(default=None, max_length=8_000)
    budget_summary: str | None = Field(default=None, max_length=8_000)
    max_debate_rounds: int | None = Field(default=None, gt=0, le=10)


class ArbiterResolutionRequest(MoneyBotModel):
    """The structured disagreement bundle given to the Arbiter."""

    arbiter_review_id: str
    debate_id: str
    stage: InnerVoiceStage
    subject_type: InnerVoiceSubjectType
    subject_id: str
    openclaw_review_id: str | None = None
    inner_voice_review_id: str | None = None
    openclaw_position_summary: str = Field(min_length=1, max_length=10_000)
    inner_voice_position_summary: str = Field(min_length=1, max_length=10_000)
    disagreement_summary: str = Field(min_length=1, max_length=10_000)
    transcript_archive_ids: list[str] = Field(default_factory=list)
    transcript_summary: str = Field(min_length=1, max_length=20_000)
    evidence_summary: list[EvidenceSummary] = Field(default_factory=list)
    constraints_summary: list[str] = Field(default_factory=list)
    policy_summary: str | None = Field(default=None, max_length=8_000)
    tos_summary: str | None = Field(default=None, max_length=8_000)
    budget_summary: str | None = Field(default=None, max_length=8_000)
    resolution_goal: str = Field(min_length=1, max_length=2_000)
    triggered_by: DebateEndedReason


class ArbiterResolutionOutput(MoneyBotModel):
    """Provider-emitted Arbiter content before governed persistence is added."""

    final_resolution: ArbiterFinalResolution
    prevailing_side: ArbiterPrevailingSide
    resolution_summary: str = Field(min_length=1, max_length=6_000)
    rationale_summary: str = Field(min_length=1, max_length=6_000)
    required_followups: list[str] = Field(default_factory=list)
    unresolved_risks: list[str] = Field(default_factory=list)


class ArbiterResolutionResult(ArbiterResolutionOutput):
    """The full persisted Arbiter resolution result."""

    arbiter_review_id: str
    debate_id: str
    provider: ProviderName
    model_name: str
    stage: InnerVoiceStage
    subject_type: InnerVoiceSubjectType
    subject_id: str
    raw_response_summary: dict[str, JsonValue] = Field(default_factory=dict)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord


class InnerVoiceDebateOutcome(MoneyBotModel):
    """The result of one bounded debate session."""

    session: InnerVoiceDebateSession
    turns: list[InnerVoiceDebateTurn] = Field(default_factory=list)
    final_resolution_source: str
    resolved_disposition: InnerVoiceDisposition | None = None
    arbiter_result: ArbiterResolutionResult | None = None
    ledger_record: LedgerRecord


class InnerVoiceMetricsSnapshot(MoneyBotModel):
    """A compact snapshot of rollout and diagnostic metrics."""

    invocation_count_by_stage: dict[str, int] = Field(default_factory=dict)
    needs_review_count_by_stage: dict[str, int] = Field(default_factory=dict)
    objection_severity_counts: dict[str, int] = Field(default_factory=dict)
    debate_session_count_by_stage: dict[str, int] = Field(default_factory=dict)
    average_completed_debate_rounds: float = 0.0
    arbiter_request_rate: float = 0.0
    arbiter_invocation_rate: float = 0.0
    arbiter_prevailing_side_counts: dict[str, int] = Field(default_factory=dict)
    arbiter_failure_rate: float = 0.0
    followup_creation_rate: float = 0.0
    provider_failure_rate: float = 0.0
    average_prompt_size_chars: float = 0.0
    average_response_size_chars: float = 0.0
    average_transcript_size_chars: float = 0.0


def model_json_schema(model: type[MoneyBotModel]) -> dict[str, JsonValue]:
    """Return a JSON-safe schema for prompt instructions."""

    schema = model.model_json_schema()
    if not isinstance(schema, Mapping):
        return {}
    return schema
