from __future__ import annotations

from skills.tos_legal_checker.models import (
    TosLegalCheckRequest,
    TosLegalCheckResult,
)


def analyze(req: TosLegalCheckRequest) -> TosLegalCheckResult:
    red_flags: list[str] = []
    required_mitigations: list[str] = []
    required_records: list[str] = []
    evidence_archive_ids = req.evidence_archive_ids or []

    if not req.proposed_action.strip():
        return _reject(
            req,
            ["empty_proposed_action"],
            required_mitigations,
            required_records,
            evidence_archive_ids,
        )

    text = (req.evidence_text or "").lower()

    red_flags.extend(_check_bots_and_automation(text))
    red_flags.extend(_check_gambling_and_trading(text))
    red_flags.extend(_check_deception(text))
    red_flags.extend(_check_money_transmission(text))

    if "kyc" in text or "identity verification" in text:
        required_mitigations.append("requires_identity_verification")

    if red_flags:
        return _reject(
            req,
            red_flags,
            required_mitigations,
            required_records,
            evidence_archive_ids,
        )

    if not evidence_archive_ids:
        required_mitigations.append("missing_evidence_ids")

    if not required_mitigations:
        required_records.append("record_tos_check")
        return _proceed(
            req,
            required_mitigations,
            required_records,
            evidence_archive_ids,
        )

    return _needs_review(
        req,
        red_flags,
        required_mitigations,
        required_records,
        evidence_archive_ids,
    )


def _check_bots_and_automation(text: str) -> list[str]:
    flags: list[str] = []
    if "bot" in text and "prohibited" in text:
        flags.append("bots_prohibited")
    if "automat" in text and "prohibited" in text:
        flags.append("automation_prohibited")
    if "spam" in text and "prohibited" in text:
        flags.append("spam_prohibited")
    return flags


def _check_gambling_and_trading(text: str) -> list[str]:
    flags: list[str] = []
    for term in ["gambling", "bet", "casino", "prediction", "crypto trading"]:
        if term in text:
            flags.append("regulated_activity_detected")
            break
    return flags


def _check_deception(text: str) -> list[str]:
    flags: list[str] = []
    if any(word in text for word in ["fake", "deceptive", "impersonat"]):
        flags.append("deceptive_behavior_detected")
    return flags


def _check_money_transmission(text: str) -> list[str]:
    flags: list[str] = []
    if any(
        phrase in text
        for phrase in ["handling funds", "money transmission"]
    ):
        flags.append("money_transmission_risk")
    return flags


def _reject(
    req: TosLegalCheckRequest,
    red_flags: list[str],
    required_mitigations: list[str],
    required_records: list[str],
    evidence_archive_ids: list[str],
) -> TosLegalCheckResult:
    return TosLegalCheckResult(
        tos_check_id=req.opportunity_id + "-tos-reject",
        decision="reject",
        confidence="high",
        platform_terms_summary=None,
        legal_risk_summary="Prohibited patterns detected",
        tos_risk_summary="Terms or evidence indicate prohibited behavior",
        red_flags=red_flags,
        required_mitigations=required_mitigations,
        required_records=required_records,
        source_quotes_or_snippets=None,
        evidence_archive_ids=evidence_archive_ids,
        handoff_to_policy_guard=None,
    )


def _proceed(
    req: TosLegalCheckRequest,
    required_mitigations: list[str],
    required_records: list[str],
    evidence_archive_ids: list[str],
) -> TosLegalCheckResult:
    return TosLegalCheckResult(
        tos_check_id=req.opportunity_id + "-tos-proceed",
        decision="proceed",
        confidence="medium",
        platform_terms_summary=None,
        legal_risk_summary=None,
        tos_risk_summary=None,
        red_flags=[],
        required_mitigations=required_mitigations,
        required_records=required_records,
        source_quotes_or_snippets=None,
        evidence_archive_ids=evidence_archive_ids,
        handoff_to_policy_guard=None,
    )


def _needs_review(
    req: TosLegalCheckRequest,
    red_flags: list[str],
    required_mitigations: list[str],
    required_records: list[str],
    evidence_archive_ids: list[str],
) -> TosLegalCheckResult:
    return TosLegalCheckResult(
        tos_check_id=req.opportunity_id + "-tos-review",
        decision="human_review",
        confidence="low",
        platform_terms_summary=None,
        legal_risk_summary="Unclear terms or requirements",
        tos_risk_summary="Needs human review",
        red_flags=red_flags,
        required_mitigations=required_mitigations,
        required_records=required_records,
        source_quotes_or_snippets=None,
        evidence_archive_ids=evidence_archive_ids,
        handoff_to_policy_guard=None,
    )
