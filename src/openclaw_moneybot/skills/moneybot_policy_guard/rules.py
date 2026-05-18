"""Deterministic policy evaluation rules."""

from __future__ import annotations

import hashlib

from openclaw_moneybot.shared.config import MoneyBotPolicyConfig
from openclaw_moneybot.shared.contracts import PolicyDecision
from openclaw_moneybot.shared.types import ConfidenceLevel, PolicyDecisionType, RiskLevel
from openclaw_moneybot.skills.ledger_skill.hashing import canonical_json
from openclaw_moneybot.skills.moneybot_policy_guard.models import (
    ExecutionConstraints,
    PolicyCheckRequest,
    PolicyCheckResult,
)
from openclaw_moneybot.skills.moneybot_policy_guard.taxonomy import (
    ALLOWED_ACTION_TYPES_FOR_RESEARCH,
    BLOCKED_TOOL_PATTERNS,
    BUILTIN_ALLOWED_LOW_RISK_CATEGORIES,
    BUILTIN_BLOCKED_CATEGORIES,
    BUILTIN_REVIEW_REQUIRED_CATEGORIES,
    normalize_category,
)
from openclaw_moneybot.utils.ids import make_id
from openclaw_moneybot.utils.time import utc_now


def _request_fingerprint(request: PolicyCheckRequest) -> str:
    payload = canonical_json(
        {
            "action_id": request.action_id,
            "action_type": request.action_type.value,
            "title": request.title,
            "description": request.description,
            "category": normalize_category(request.category),
            "counterparty": request.counterparty,
            "amount_usd": request.amount_usd,
            "asset": request.asset,
            "source_urls": [str(url) for url in request.source_urls],
            "planned_tools": request.planned_tools,
            "user_approval_present": request.user_approval_present,
            "requires_new_account": request.requires_new_account,
            "requires_payment": request.requires_payment,
            "requires_email_send": request.requires_email_send,
            "requires_wallet_action": request.requires_wallet_action,
            "requires_public_claims": request.requires_public_claims,
            "requires_user_data_collection": request.requires_user_data_collection,
            "metadata": request.metadata,
        }
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evaluate_policy(
    request: PolicyCheckRequest,
    config: MoneyBotPolicyConfig,
) -> PolicyCheckResult:
    """Evaluate a request against deterministic policy rules."""
    normalized_category = normalize_category(request.category)
    blocked_categories = BUILTIN_BLOCKED_CATEGORIES | {
        normalize_category(value) for value in config.blocked_categories
    }
    review_categories = BUILTIN_REVIEW_REQUIRED_CATEGORIES | {
        normalize_category(value) for value in config.review_required_categories
    }
    allowed_categories = BUILTIN_ALLOWED_LOW_RISK_CATEGORIES

    blocked_reasons: list[str] = []
    mitigations: list[str] = []
    matched_rules: list[str] = []
    safe_next_steps: list[str] = []
    followup_skills: list[str] = []
    human_review_reason: str | None = None
    constraints = ExecutionConstraints()
    opportunity_id = (
        str(request.metadata.get("opportunity_id"))
        if "opportunity_id" in request.metadata
        else None
    )

    if request.action_type not in config.allowed_action_types:
        blocked_reasons.append("Action type is not enabled by policy config.")
        matched_rules.append("blocked_action_type")

    if normalized_category in blocked_categories:
        blocked_reasons.append(f"Category '{normalized_category}' is blocked.")
        matched_rules.append("blocked_category")

    description_lower = request.description.lower()
    tools_lower = [tool.lower() for tool in request.planned_tools]
    for pattern, rule_name in BLOCKED_TOOL_PATTERNS.items():
        if pattern in description_lower or any(pattern in tool for tool in tools_lower):
            blocked_reasons.append(
                f"Request references prohibited wallet access pattern: {pattern}."
            )
            matched_rules.append(rule_name)

    if request.action_type in {
        request.action_type.SPEND,
        request.action_type.WALLET_TRANSFER,
        request.action_type.PURCHASE,
    }:
        if request.amount_usd is None:
            blocked_reasons.append("Spend and wallet actions require amount_usd.")
            matched_rules.append("missing_amount")
        elif request.amount_usd > config.max_single_spend_usd:
            blocked_reasons.append("Requested spend exceeds the configured single-spend cap.")
            matched_rules.append("amount_over_single_spend_cap")
        if not request.counterparty:
            blocked_reasons.append("Spend and wallet actions require a counterparty.")
            matched_rules.append("missing_counterparty")
        if "budget_plan_id" not in request.metadata:
            blocked_reasons.append("Wallet actions require a budget_plan_id.")
            matched_rules.append("missing_budget_plan")
        if "policy_decision_id" not in request.metadata:
            blocked_reasons.append("Wallet actions require a policy_decision_id.")
            matched_rules.append("missing_policy_reference")
        if "tos_legal_check_id" not in request.metadata:
            blocked_reasons.append("Wallet actions require a tos_legal_check_id.")
            matched_rules.append("missing_tos_legal_reference")
        if "ledger_record_id" not in request.metadata:
            blocked_reasons.append("Wallet actions require a ledger_record_id.")
            matched_rules.append("missing_ledger_reference")

    if request.requires_wallet_action and request.action_type not in {
        request.action_type.SPEND,
        request.action_type.WALLET_TRANSFER,
        request.action_type.PURCHASE,
    }:
        blocked_reasons.append("Unknown executable wallet actions are blocked by default.")
        matched_rules.append("unknown_executable_wallet_action")

    if request.requires_email_send and not request.user_approval_present:
        human_review_reason = "Outbound email sending requires explicit approval."
        mitigations.append("Provide explicit approval before send-ready email workflows.")
        matched_rules.append("email_send_requires_approval")
        followup_skills.append("ledger_skill")
    if request.requires_email_send and opportunity_id is None:
        human_review_reason = (
            "Outbound email actions require an opportunity or experiment reference."
        )
        mitigations.append("Attach an approved opportunity or experiment reference before send.")
        matched_rules.append("missing_email_reference")
    if request.action_type is request.action_type.BROWSER_SUBMIT and opportunity_id is None:
        human_review_reason = "Browser submissions require an approved opportunity reference."
        mitigations.append("Attach an approved opportunity or experiment reference before submit.")
        matched_rules.append("missing_browser_reference")

    if request.requires_new_account:
        human_review_reason = "Account creation requires review."
        mitigations.append("Review platform rules before creating accounts.")
        matched_rules.append("new_account_requires_review")
        followup_skills.append("tos_legal_checker")
        if not bool(request.metadata.get("bot_owned_account_context")):
            blocked_reasons.append(
                "Account creation requires an explicit bot-owned account context."
            )
            matched_rules.append("missing_bot_owned_account_context")

    if request.requires_user_data_collection:
        human_review_reason = "Collecting user data requires review."
        mitigations.append("Document purpose, privacy handling, and retention policy.")
        matched_rules.append("user_data_collection_requires_review")

    if request.requires_public_claims:
        human_review_reason = "Public claims require review for truthfulness and compliance."
        mitigations.append("Verify all public claims against archived evidence.")
        matched_rules.append("public_claims_require_review")

    if normalized_category in review_categories:
        human_review_reason = (
            f"Category '{normalized_category}' defaults to review until explicitly cleared."
        )
        matched_rules.append("review_required_category")
        followup_skills.append("tos_legal_checker")

    if request.action_type.value == "email" and not request.counterparty:
        blocked_reasons.append("Direct email actions require a counterparty or recipient.")
        matched_rules.append("missing_counterparty")

    if blocked_reasons:
        ledger_record = PolicyDecision(
            created_at=utc_now(),
            policy_decision_id=make_id("policy"),
            opportunity_id=opportunity_id,
            decision=PolicyDecisionType.BLOCK,
            risk_level=RiskLevel.CRITICAL,
            confidence=ConfidenceLevel.HIGH,
            blocked_reasons=blocked_reasons,
            required_mitigations=mitigations,
            matched_rules=matched_rules,
            human_review_reason=human_review_reason,
            safe_next_steps=safe_next_steps,
            policy_version=config.policy_version,
            request_fingerprint=_request_fingerprint(request),
        )
        return PolicyCheckResult(
            decision=PolicyDecisionType.BLOCK,
            risk_level=RiskLevel.CRITICAL,
            confidence=ConfidenceLevel.HIGH,
            blocked_reasons=blocked_reasons,
            required_mitigations=mitigations,
            matched_rules=matched_rules,
            human_review_reason=human_review_reason,
            safe_next_steps=safe_next_steps,
            required_followup_skills=sorted(set(followup_skills)),
            human_review_required=human_review_reason is not None,
            notes="Request blocked by deterministic policy rules.",
            ledger_record=ledger_record,
        )

    if human_review_reason is not None or normalized_category not in allowed_categories:
        if (
            normalized_category not in allowed_categories
            and normalized_category not in review_categories
        ):
            matched_rules.append("unknown_category_defaults_to_review")
            human_review_reason = (
                human_review_reason
                or f"Category '{normalized_category}' is not explicitly allowlisted."
            )
        safe_next_steps = ["Run tos_legal_checker", "Record the decision in ledger_skill"]
        ledger_record = PolicyDecision(
            created_at=utc_now(),
            policy_decision_id=make_id("policy"),
            opportunity_id=opportunity_id,
            decision=PolicyDecisionType.NEEDS_REVIEW,
            risk_level=RiskLevel.MEDIUM,
            confidence=ConfidenceLevel.HIGH,
            blocked_reasons=[],
            required_mitigations=mitigations,
            matched_rules=matched_rules,
            human_review_reason=human_review_reason,
            safe_next_steps=safe_next_steps,
            policy_version=config.policy_version,
            request_fingerprint=_request_fingerprint(request),
        )
        return PolicyCheckResult(
            decision=PolicyDecisionType.NEEDS_REVIEW,
            risk_level=RiskLevel.MEDIUM,
            confidence=ConfidenceLevel.HIGH,
            required_mitigations=mitigations,
            matched_rules=matched_rules,
            human_review_reason=human_review_reason,
            safe_next_steps=safe_next_steps,
            required_followup_skills=sorted(
                set(followup_skills + ["tos_legal_checker", "ledger_skill"])
            ),
            human_review_required=True,
            notes="Request requires human or downstream review before execution.",
            ledger_record=ledger_record,
        )

    if (
        request.action_type in ALLOWED_ACTION_TYPES_FOR_RESEARCH
        and normalized_category in allowed_categories
    ):
        matched_rules.append("allow_low_risk_research")
        constraints = ExecutionConstraints(
            max_spend_usd=0,
            max_email_count=0,
            allowed_domains=[],
            allowed_wallet_assets=[],
        )
    else:
        constraints = ExecutionConstraints(
            max_spend_usd=min(request.amount_usd or 0, config.max_single_spend_usd),
            max_email_count=0,
            allowed_domains=[],
            allowed_wallet_assets=[request.asset] if request.asset else [],
            allow_public_posting=False,
            allow_purchase=request.action_type.value == "purchase",
            allow_wallet_transfer=request.requires_wallet_action,
        )
        matched_rules.append("allow_bounded_action")

    safe_next_steps = ["Record the approval in ledger_skill"]
    ledger_record = PolicyDecision(
        created_at=utc_now(),
        policy_decision_id=make_id("policy"),
        opportunity_id=opportunity_id,
        decision=PolicyDecisionType.ALLOW,
        risk_level=RiskLevel.LOW,
        confidence=ConfidenceLevel.HIGH,
        matched_rules=matched_rules,
        safe_next_steps=safe_next_steps,
        policy_version=config.policy_version,
        request_fingerprint=_request_fingerprint(request),
    )
    return PolicyCheckResult(
        decision=PolicyDecisionType.ALLOW,
        risk_level=RiskLevel.LOW,
        confidence=ConfidenceLevel.HIGH,
        allowed_action_type=request.action_type.value,
        matched_rules=matched_rules,
        safe_next_steps=safe_next_steps,
        required_followup_skills=["ledger_skill"],
        execution_constraints=constraints,
        notes="Request allowed under bounded policy constraints.",
        ledger_record=ledger_record,
    )
