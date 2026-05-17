from __future__ import annotations

from skills.moneybot_policy_guard.models import (
    PolicyCheckRequest,
    PolicyDecision,
)

PROHIBITED_CATEGORIES = {
    "gambling",
    "prediction_market",
    "crypto_trading",
    "spam",
    "deceptive_marketing",
    "illegal_goods",
    "adult",
    "money_transmission",
    "kyc_evasion",
}

NEEDS_REVIEW_CATEGORIES = {
    "affiliate_marketing",
    "legal_uncertain",
    "identity_verification",
    "user_data_collection",
    "platform_api_unknown",
}


def evaluate(request: PolicyCheckRequest) -> PolicyDecision:
    blocked_reasons: list[str] = []
    required_mitigations: list[str] = []
    matched_rules: list[str] = []
    human_review_reason: str | None = None

    if not request.description.strip():
        blocked_reasons.append("empty_description")
        return _blocked(
            request,
            blocked_reasons,
            required_mitigations,
            matched_rules,
        )

    if not request.category:
        blocked_reasons.append("missing_category_for_external_action")
        return _blocked(
            request,
            blocked_reasons,
            required_mitigations,
            matched_rules,
        )

    if request.amount_usd is None and _is_spend_action(request):
        blocked_reasons.append("missing_amount_for_spend")
        return _blocked(
            request,
            blocked_reasons,
            required_mitigations,
            matched_rules,
        )

    if request.counterparty is None and _is_counterparty_required(
        request,
    ):
        blocked_reasons.append("missing_counterparty_for_payment_email")
        return _blocked(
            request,
            blocked_reasons,
            required_mitigations,
            matched_rules,
        )

    norm_cat = request.category.lower().replace(" ", "_")

    if _is_hard_block(norm_cat):
        blocked_reasons.append("prohibited_category")
        return _blocked(
            request,
            blocked_reasons,
            required_mitigations,
            matched_rules,
        )

    if _is_needs_review(norm_cat):
        human_review_reason = "category_requires_review"
        return _needs_review(
            request,
            human_review_reason,
            required_mitigations,
            matched_rules,
        )

    if _is_safe_internal(request):
        matched_rules.append("ALLOW_INTERNAL")
        return _allow(request, matched_rules)

    return _needs_review(
        request,
        "unknown_category_requires_review",
        required_mitigations,
        matched_rules,
    )


def _is_spend_action(request: PolicyCheckRequest) -> bool:
    return request.action_type in {
        "spend",
        "payment",
        "purchase",
        "invoice",
    }


def _is_counterparty_required(request: PolicyCheckRequest) -> bool:
    return request.action_type in {
        "spend",
        "email_send",
        "payment",
    }


def _is_hard_block(category: str) -> bool:
    return any(
        token in category
        for token in [
            "gambling",
            "prediction_market",
            "trading",
            "crypto_trading",
            "spam",
            "deceptive",
            "illegal",
            "adult",
            "money_transmission",
            "kyc_evasion",
        ]
    )


def _is_needs_review(category: str) -> bool:
    return any(
        token in category
        for token in [
            "affiliate",
            "legal_uncertain",
            "identity_verification",
            "user_data_collection",
            "platform_api_unknown",
        ]
    )


def _is_safe_internal(request: PolicyCheckRequest) -> bool:
    return request.action_type in {
        "internal",
        "research",
        "draft_only",
    }


def _blocked(
    request: PolicyCheckRequest,
    blocked_reasons: list[str],
    required_mitigations: list[str],
    matched_rules: list[str],
) -> PolicyDecision:
    matched_rules.append("BLOCK_DEFAULT")
    return PolicyDecision(
        policy_decision_id=request.action_id + "-blocked",
        decision="block",
        risk_level="high",
        blocked_reasons=blocked_reasons,
        required_mitigations=required_mitigations,
        matched_rules=matched_rules,
        human_review_reason=None,
        safe_next_steps=["fix_request"],
        expires_at=None,
    )


def _needs_review(
    request: PolicyCheckRequest,
    human_review_reason: str,
    required_mitigations: list[str],
    matched_rules: list[str],
) -> PolicyDecision:
    matched_rules.append("NEEDS_REVIEW")
    return PolicyDecision(
        policy_decision_id=request.action_id + "-needs_review",
        decision="needs_review",
        risk_level="medium",
        blocked_reasons=[],
        required_mitigations=required_mitigations,
        matched_rules=matched_rules,
        human_review_reason=human_review_reason,
        safe_next_steps=["request_human_review"],
        expires_at=None,
    )


def _allow(
    request: PolicyCheckRequest,
    matched_rules: list[str],
) -> PolicyDecision:
    return PolicyDecision(
        policy_decision_id=request.action_id + "-allow",
        decision="allow",
        risk_level="low",
        blocked_reasons=[],
        required_mitigations=[],
        matched_rules=matched_rules,
        human_review_reason=None,
        safe_next_steps=["execute"],
        expires_at=None,
    )
