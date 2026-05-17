"""Deterministic preflight validation for wallet-governor client requests."""

from __future__ import annotations

from openclaw_moneybot.shared import MoneyBotPolicyConfig, WalletGovernorConfig
from openclaw_moneybot.shared.types import BudgetDecisionType, PolicyDecisionType, TosDecisionType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.wallet_governor_client.models import WalletSpendRequest
from openclaw_moneybot.utils.time import utc_now

ALLOWED_SPEND_CATEGORIES = {
    "domain",
    "hosting",
    "listing_fee",
    "software_credit",
    "purchase",
    "other",
}
BTC_ADDRESS_PREFIXES = ("bc1", "tb1", "bcrt1", "1", "3")


def validate_destination(asset: str, destination: str) -> bool:
    """Perform a minimal destination plausibility check."""
    if asset == "BTC":
        return destination.startswith(BTC_ADDRESS_PREFIXES) and len(destination) >= 14
    return bool(destination.strip())


def validate_spend_request(
    request: WalletSpendRequest,
    config: WalletGovernorConfig,
    policy_config: MoneyBotPolicyConfig,
    ledger_service: LedgerService,
) -> list[str]:
    """Return fail-closed rejection reasons for the request."""
    reasons: list[str] = []
    if not config.spend_enabled:
        reasons.append("spend disabled")
    if request.asset not in config.allowed_assets:
        reasons.append("unsupported asset")
    if request.category not in ALLOWED_SPEND_CATEGORIES:
        reasons.append("unsupported spend category")
    if request.category in policy_config.blocked_categories:
        reasons.append("blocked spend category")
    if request.amount_usd > policy_config.max_single_spend_usd:
        reasons.append("amount exceeds single-spend cap")
    if not validate_destination(request.asset, request.destination):
        reasons.append("invalid destination")
    if not request.evidence_archive_ids:
        reasons.append("missing evidence reference")
    if "send all" in request.purpose.lower():
        reasons.append("send-all language is prohibited")

    policy = ledger_service.get_policy_decision(request.policy_decision_id)
    if policy is None:
        reasons.append("missing policy approval")
    elif policy.decision is not PolicyDecisionType.ALLOW:
        reasons.append("policy decision is not allow")

    budget = ledger_service.get_budget_plan(request.budget_plan_id)
    if budget is None:
        reasons.append("missing budget plan")
    else:
        if budget.decision is not BudgetDecisionType.EXECUTE_REQUEST:
            reasons.append("budget plan is not executable")
        if not budget.wallet_spend_request_allowed:
            reasons.append("budget plan does not allow wallet spend")
        if request.amount_usd > budget.recommended_budget_usd:
            reasons.append("amount exceeds budget plan")
        tos_check_id = request.tos_legal_check_id or budget.tos_legal_check_id
        tos_check = ledger_service.get_tos_legal_check(tos_check_id)
        if tos_check is None:
            reasons.append("missing tos approval")
        elif tos_check.decision not in {TosDecisionType.PROCEED, TosDecisionType.HUMAN_REVIEW}:
            reasons.append("tos decision does not allow spend")
    today = utc_now().date().isoformat()
    daily_total = ledger_service.get_daily_spend_total(today)
    weekly_total = ledger_service.get_weekly_spend_total(today)
    if daily_total + request.amount_usd > policy_config.max_daily_spend_usd:
        reasons.append("amount exceeds daily spend cap")
    if weekly_total + request.amount_usd > policy_config.max_weekly_spend_usd:
        reasons.append("amount exceeds weekly spend cap")
    return reasons
