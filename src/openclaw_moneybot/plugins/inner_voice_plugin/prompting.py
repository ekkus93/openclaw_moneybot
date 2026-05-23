"""Prompt construction and sanitization for the inner voice system."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from datetime import UTC, datetime

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
    (
        re.compile(r"Bearer\s+[A-Za-z0-9._\-]{10,}", flags=re.IGNORECASE),
        "Bearer [REDACTED_TOKEN]",
    ),
    (re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)([^\s,;]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(password\s*[:=]\s*)([^\s,;]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(seed phrase\s*[:=]\s*)([^\n]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(private key\s*[:=]\s*)([^\s,;]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(rpc cookie\s*[:=]\s*)([^\s,;]+)"), r"\1[REDACTED]"),
)

TRUNCATION_MARKER_TEMPLATE = "\n...[TRUNCATED:{label}:{omitted}_CHARS]"
ARCHIVE_SUMMARY_MAX_CHARS = 4_000


def sanitize_text(value: str, *, mode: str = "sanitize") -> str:
    """Apply deterministic secret redaction to archived text."""

    sanitized = value
    for pattern, replacement in SECRET_PATTERNS:
        if mode == "hash_sensitive_fields":
            sanitized = pattern.sub(
                lambda match: _hash_sensitive_match(match.group(0)),
                sanitized,
            )
        else:
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
    max_input_chars: int,
    max_evidence_items: int,
    max_chars_per_evidence: int,
    stale_evidence_days: int,
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
            _bounded_text(request.review_goal, max_chars_per_evidence, "review_goal"),
            "",
            "Stage-specific focus:",
            _stage_guidance(request.stage),
            "",
            "Claim summary:",
            _bounded_text(request.claim_summary, max_chars_per_evidence * 2, "claim_summary"),
            "",
            "Structured context:",
            _bounded_json(
                request.structured_context,
                max_chars_per_evidence * 4,
                "structured_context",
            ),
            "",
            "Evidence summary:",
            render_json(
                _prepared_evidence_items(
                    request.evidence_summary,
                    max_items=max_evidence_items,
                    max_chars_per_evidence=max_chars_per_evidence,
                    stale_evidence_days=stale_evidence_days,
                )
            ),
            "",
            "Constraints summary:",
            _bounded_json(
                request.constraints_summary,
                max_chars_per_evidence * 2,
                "constraints_summary",
            ),
            "",
            "Policy summary:",
            _bounded_text(
                request.policy_summary or "",
                max_chars_per_evidence * 2,
                "policy_summary",
            ),
            "",
            "TOS summary:",
            _bounded_text(request.tos_summary or "", max_chars_per_evidence * 2, "tos_summary"),
            "",
            "Budget summary:",
            _bounded_text(
                request.budget_summary or "",
                max_chars_per_evidence * 2,
                "budget_summary",
            ),
            "",
            "Max objections:",
            str(request.max_objections),
            "",
            "Return one JSON object using the provided schema.",
        ]
    )
    user_prompt = _fit_prompt_text(
        user_prompt,
        max_input_chars=max_input_chars,
        reserved_chars=len(system_prompt),
        label="inner_voice_prompt",
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
    max_input_chars: int,
    max_evidence_items: int,
    max_chars_per_evidence: int,
    stale_evidence_days: int,
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
            _bounded_text(request.claim_summary, max_chars_per_evidence * 2, "claim_summary"),
            "",
            "Disagreement summary:",
            _bounded_text(
                request.disagreement_summary,
                max_chars_per_evidence * 2,
                "disagreement_summary",
            ),
            "",
            "Latest counterparty message:",
            _bounded_text(
                request.latest_counterparty_message or "",
                max_chars_per_evidence * 2,
                "latest_counterparty_message",
            ),
            "",
            "Prior turns:",
            _bounded_json(prior_turns, max_chars_per_evidence * 5, "prior_turns"),
            "",
            "Evidence summary:",
            render_json(
                _prepared_evidence_items(
                    request.evidence_summary,
                    max_items=max_evidence_items,
                    max_chars_per_evidence=max_chars_per_evidence,
                    stale_evidence_days=stale_evidence_days,
                )
            ),
            "",
            "Constraints summary:",
            _bounded_json(
                request.constraints_summary,
                max_chars_per_evidence * 2,
                "constraints_summary",
            ),
            "",
            "Return one JSON object using the provided schema.",
        ]
    )
    user_prompt = _fit_prompt_text(
        user_prompt,
        max_input_chars=max_input_chars,
        reserved_chars=len(system_prompt),
        label="debate_prompt",
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
    max_input_chars: int,
    max_chars_per_evidence: int,
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
            _bounded_text(request.resolution_goal, max_chars_per_evidence, "resolution_goal"),
            "",
            "Trigger:",
            request.triggered_by.value,
            "",
            "OpenClaw position summary:",
            _bounded_text(
                request.openclaw_position_summary,
                max_chars_per_evidence * 2,
                "openclaw_position_summary",
            ),
            "",
            "Inner voice position summary:",
            _bounded_text(
                request.inner_voice_position_summary,
                max_chars_per_evidence * 2,
                "inner_voice_position_summary",
            ),
            "",
            "Disagreement summary:",
            _bounded_text(
                request.disagreement_summary,
                max_chars_per_evidence * 2,
                "disagreement_summary",
            ),
            "",
            "Transcript summary:",
            _bounded_text(
                request.transcript_summary,
                max_chars_per_evidence * 6,
                "transcript_summary",
            ),
            "",
            "Evidence summary:",
            render_json(
                _prepared_evidence_items(
                    request.evidence_summary,
                    max_items=len(request.evidence_summary),
                    max_chars_per_evidence=max_chars_per_evidence,
                    stale_evidence_days=3650,
                )
            ),
            "",
            "Constraints summary:",
            _bounded_json(
                request.constraints_summary,
                max_chars_per_evidence * 2,
                "constraints_summary",
            ),
            "",
            "Policy summary:",
            _bounded_text(
                request.policy_summary or "",
                max_chars_per_evidence * 2,
                "policy_summary",
            ),
            "",
            "TOS summary:",
            _bounded_text(request.tos_summary or "", max_chars_per_evidence * 2, "tos_summary"),
            "",
            "Budget summary:",
            _bounded_text(
                request.budget_summary or "",
                max_chars_per_evidence * 2,
                "budget_summary",
            ),
            "",
            "Return one JSON object using the provided schema.",
        ]
    )
    user_prompt = _fit_prompt_text(
        user_prompt,
        max_input_chars=max_input_chars,
        reserved_chars=len(system_prompt),
        label="arbiter_prompt",
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
    return _bounded_text("\n".join(summary_lines), 20_000, "transcript_summary")


def archive_text(
    value: str,
    *,
    raw_allowed: bool,
    redaction_mode: str,
    max_chars: int,
) -> str:
    """Prepare archive text according to raw-archive and redaction settings."""

    if not raw_allowed:
        return sanitize_text(
            _bounded_text(value, min(max_chars, ARCHIVE_SUMMARY_MAX_CHARS), "archive_summary"),
        )
    if redaction_mode == "disabled":
        return _bounded_text(value, max_chars, "archive_raw")
    return _bounded_text(
        sanitize_text(value, mode=redaction_mode),
        max_chars,
        "archive_redacted",
    )


def _stage_guidance(stage: InnerVoiceStage) -> str:
    if stage is InnerVoiceStage.OPPORTUNITY_RANKING:
        return (
            "Focus on weak legitimacy signals, missing payout evidence, unsupported fit claims, "
            "and whether the opportunity should be ranked lower or paused."
        )
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


def _bounded_json(value: object, max_chars: int, label: str) -> str:
    return _bounded_text(render_json(value), max_chars, label)


def _bounded_text(value: str, max_chars: int, label: str) -> str:
    if max_chars <= 0:
        msg = f"{label} max_chars must be positive"
        raise ValueError(msg)
    if len(value) <= max_chars:
        return value
    marker = TRUNCATION_MARKER_TEMPLATE.format(label=label, omitted=len(value) - max_chars)
    available = max_chars - len(marker)
    if available <= 0:
        msg = f"{label} cannot fit within max_input_chars"
        raise ValueError(msg)
    return f"{value[:available]}{marker}"


def _fit_prompt_text(
    value: str,
    *,
    max_input_chars: int,
    reserved_chars: int,
    label: str,
) -> str:
    available = max_input_chars - reserved_chars
    if available <= 200:
        msg = f"{label} cannot fit within max_input_chars"
        raise ValueError(msg)
    return _bounded_text(value, available, label)


def _prepared_evidence_items(
    evidence_items: Sequence[object],
    *,
    max_items: int,
    max_chars_per_evidence: int,
    stale_evidence_days: int,
) -> list[dict[str, object]]:
    prepared: list[dict[str, object]] = []
    seen: set[str] = set()
    sorted_items = sorted(
        evidence_items,
        key=lambda item: (
            str(getattr(item, "source_url", "") or ""),
            str(getattr(item, "evidence_id", "")),
        ),
    )
    for item in sorted_items:
        dedupe_key = str(getattr(item, "source_url", None) or getattr(item, "evidence_id", ""))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        captured_at = str(getattr(item, "captured_at", ""))
        freshness_hint = getattr(item, "freshness_hint", None)
        if freshness_hint is None and _is_stale(captured_at, stale_evidence_days):
            freshness_hint = "stale"
        prepared.append(
            {
                "evidence_id": str(getattr(item, "evidence_id", "")),
                "evidence_type": str(getattr(item, "evidence_type", "")),
                "source_url": getattr(item, "source_url", None),
                "captured_at": captured_at,
                "summary": _bounded_text(
                    str(getattr(item, "summary", "")),
                    max_chars_per_evidence,
                    "evidence_summary",
                ),
                "freshness_hint": freshness_hint,
            }
        )
        if len(prepared) >= max_items:
            break
    return prepared


def _is_stale(captured_at: str, stale_evidence_days: int) -> bool:
    try:
        parsed = datetime.fromisoformat(captured_at.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return False
    return (datetime.now(tz=UTC) - parsed).days >= stale_evidence_days


def _hash_sensitive_match(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"[HASHED_SECRET:{digest}]"
