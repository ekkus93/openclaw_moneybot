"""Prompt construction and sanitization for the inner voice system."""

from __future__ import annotations

import json
import re

from openclaw_moneybot.plugins.inner_voice_plugin.models import (
    ArbiterPromptRequest,
    ArbiterResolutionOutput,
    ArbiterResolutionRequest,
    DebateResponderOutput,
    DebateResponderRequest,
    InnerVoicePromptRequest,
    InnerVoiceReviewOutput,
    InnerVoiceReviewRequest,
    model_json_schema,
)
from openclaw_moneybot.shared.types import InnerVoiceStage, ProviderName

SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9]{10,}"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]{10,}", flags=re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)([^\s,;]+)"), r"\1[REDACTED]"),
)


def sanitize_text(value: str) -> str:
    """Apply deterministic secret redaction to archived text."""

    sanitized = value
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def render_json(value: object) -> str:
    """Render a bounded JSON representation for prompt content."""

    return json.dumps(value, indent=2, sort_keys=True, default=str)


def build_inner_voice_prompt(
    request: InnerVoiceReviewRequest,
    *,
    provider: ProviderName,
    model_name: str,
    temperature: float,
    top_p: float | None,
    max_output_tokens: int,
    timeout_seconds: float,
) -> InnerVoicePromptRequest:
    """Build the deterministic inner-voice prompt envelope."""

    system_prompt = (
        "You are the inner voice of a constrained, audit-heavy experiment runner.\n"
        "Challenge assumptions, identify missing evidence, note stale or contradictory evidence,\n"
        "and return only one JSON object matching the requested schema.\n"
        "Do not invent facts, do not ask for secrets, do not propose forbidden actions, and do\n"
        "not claim to approve actions."
    )
    user_prompt = "\n".join(
        [
            "Review goal:",
            request.review_goal,
            "",
            "Stage-specific focus:",
            _stage_guidance(request.stage),
            "",
            "Claim summary:",
            request.claim_summary,
            "",
            "Structured context:",
            render_json(request.structured_context),
            "",
            "Evidence summary:",
            render_json([item.model_dump(mode="json") for item in request.evidence_summary]),
            "",
            "Constraints summary:",
            render_json(request.constraints_summary),
            "",
            "Policy summary:",
            request.policy_summary or "",
            "",
            "TOS summary:",
            request.tos_summary or "",
            "",
            "Budget summary:",
            request.budget_summary or "",
            "",
            "Max objections:",
            str(request.max_objections),
            "",
            "Return one JSON object using the provided schema.",
        ]
    )
    return InnerVoicePromptRequest(
        request_id=request.review_id,
        provider=provider,
        model_name=model_name,
        system_prompt=sanitize_text(system_prompt),
        user_prompt=sanitize_text(user_prompt),
        response_schema_json=model_json_schema(InnerVoiceReviewOutput),
        temperature=temperature,
        top_p=top_p,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
    )


def build_debate_prompt(
    request: DebateResponderRequest,
    *,
    provider: ProviderName,
    model_name: str,
    temperature: float,
    top_p: float | None,
    max_output_tokens: int,
    timeout_seconds: float,
) -> InnerVoicePromptRequest:
    """Build a bounded debate prompt for one participant turn."""

    system_prompt = (
        "You are participating in a bounded disagreement review.\n"
        "Return only one JSON object. Be concise, grounded in evidence, and do not claim hidden\n"
        "reasoning. If the disagreement cannot be resolved safely, set request_arbiter to true."
    )
    prior_turns = [
        {
            "round_index": turn.round_index,
            "turn_index": turn.turn_index,
            "speaker": turn.speaker.value,
            "turn_type": turn.turn_type.value,
            "message_text": turn.message_text,
            "disposition_signal": turn.disposition_signal.value
            if turn.disposition_signal is not None
            else None,
            "request_arbiter": turn.request_arbiter,
        }
        for turn in request.prior_turns
    ]
    user_prompt = "\n".join(
        [
            f"Speaker: {request.speaker.value}",
            f"Round: {request.round_index} / {request.max_rounds}",
            "",
            "Stage-specific focus:",
            _stage_guidance(request.stage),
            "",
            "Claim summary:",
            request.claim_summary,
            "",
            "Disagreement summary:",
            request.disagreement_summary,
            "",
            "Latest counterparty message:",
            request.latest_counterparty_message or "",
            "",
            "Prior turns:",
            render_json(prior_turns),
            "",
            "Evidence summary:",
            render_json([item.model_dump(mode="json") for item in request.evidence_summary]),
            "",
            "Constraints summary:",
            render_json(request.constraints_summary),
            "",
            "Return one JSON object using the provided schema.",
        ]
    )
    return InnerVoicePromptRequest(
        request_id=f"{request.debate_id}:{request.round_index}:{request.speaker.value}",
        provider=provider,
        model_name=model_name,
        system_prompt=sanitize_text(system_prompt),
        user_prompt=sanitize_text(user_prompt),
        response_schema_json=model_json_schema(DebateResponderOutput),
        temperature=temperature,
        top_p=top_p,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
    )


def build_arbiter_prompt(
    request: ArbiterResolutionRequest,
    *,
    provider: ProviderName,
    model_name: str,
    temperature: float,
    top_p: float | None,
    max_output_tokens: int,
    timeout_seconds: float,
) -> ArbiterPromptRequest:
    """Build the Arbiter prompt envelope."""

    system_prompt = (
        "You are the Arbiter for a constrained, audit-heavy disagreement-resolution workflow.\n"
        "Resolve the disagreement between OpenClaw and the inner voice. Return only one JSON\n"
        "object. Do not claim authority over deterministic policy gates."
    )
    user_prompt = "\n".join(
        [
            "Resolution goal:",
            request.resolution_goal,
            "",
            "Trigger:",
            request.triggered_by.value,
            "",
            "OpenClaw position summary:",
            request.openclaw_position_summary,
            "",
            "Inner voice position summary:",
            request.inner_voice_position_summary,
            "",
            "Disagreement summary:",
            request.disagreement_summary,
            "",
            "Transcript summary:",
            request.transcript_summary,
            "",
            "Evidence summary:",
            render_json([item.model_dump(mode="json") for item in request.evidence_summary]),
            "",
            "Constraints summary:",
            render_json(request.constraints_summary),
            "",
            "Policy summary:",
            request.policy_summary or "",
            "",
            "TOS summary:",
            request.tos_summary or "",
            "",
            "Budget summary:",
            request.budget_summary or "",
            "",
            "Return one JSON object using the provided schema.",
        ]
    )
    return ArbiterPromptRequest(
        request_id=request.arbiter_review_id,
        provider=provider,
        model_name=model_name,
        system_prompt=sanitize_text(system_prompt),
        user_prompt=sanitize_text(user_prompt),
        response_schema_json=model_json_schema(ArbiterResolutionOutput),
        temperature=temperature,
        top_p=top_p,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
    )


def format_debate_transcript(turns: list[dict[str, object]]) -> str:
    """Format a readable turn-by-turn transcript for archival."""

    lines: list[str] = []
    for turn in turns:
        speaker = str(turn["speaker"])
        round_index_raw = turn["round_index"]
        turn_index_raw = turn["turn_index"]
        round_index = (
            round_index_raw if isinstance(round_index_raw, int) else int(str(round_index_raw))
        )
        turn_index = (
            turn_index_raw if isinstance(turn_index_raw, int) else int(str(turn_index_raw))
        )
        lines.append(f"[round {round_index} turn {turn_index}] {speaker}")
        lines.append(sanitize_text(str(turn["message_text"])))
        lines.append("")
    return "\n".join(lines).strip()


def summarize_transcript(turns: list[dict[str, object]]) -> str:
    """Build a bounded transcript summary for the Arbiter."""

    summary_lines: list[str] = []
    for turn in turns:
        speaker = str(turn["speaker"])
        disposition = turn.get("disposition_signal")
        disposition_text = ""
        if disposition:
            disposition_text = f" [{disposition}]"
        summary_lines.append(
            f"{speaker}{disposition_text}: {sanitize_text(str(turn['message_text']))}"
        )
    return "\n".join(summary_lines)[:20_000]


def _stage_guidance(stage: InnerVoiceStage) -> str:
    if stage is InnerVoiceStage.TOS_LEGAL_CHECK:
        return (
            "Focus on missing rules, ambiguous terms, eligibility conflicts, "
            "and contradictory evidence."
        )
    if stage is InnerVoiceStage.BUDGET_PLANNING:
        return (
            "Focus on downside risk, hidden costs, unsupported ROI assumptions, "
            "and stale market assumptions."
        )
    if stage is InnerVoiceStage.PRE_EXECUTION:
        return (
            "Focus on irreversibility, missing approvals, stale evidence, "
            "and unresolved blockers."
        )
    if stage is InnerVoiceStage.POST_REVIEW:
        return "Focus on lesson quality, unsupported conclusions, and repeated risk patterns."
    return (
        "Focus on weak assumptions, missing evidence, and whether the next step "
        "is well-supported."
    )
