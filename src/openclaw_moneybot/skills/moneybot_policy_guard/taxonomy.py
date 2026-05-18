"""Policy taxonomy and normalization helpers."""

from __future__ import annotations

from openclaw_moneybot.shared.types import ActionType

BUILTIN_BLOCKED_CATEGORIES = {
    "gambling",
    "prediction_markets",
    "options_trading",
    "securities_trading",
    "forex_trading",
    "futures_trading",
    "leveraged_trading",
    "defi_yield_farming",
    "nft_speculation",
    "token_speculation",
    "airdrop_farming",
    "autonomous_crypto_trading",
    "crypto_speculation",
    "handling_other_peoples_funds",
    "money_transmission",
    "escrow",
    "brokerage",
    "exchange_operation",
    "mixing",
    "tumbling",
    "kyc_evasion",
    "fake_identity",
    "impersonation",
    "account_farming",
    "spam",
    "bulk_outreach",
    "fake_reviews",
    "phishing",
    "credential_harvesting",
    "malware",
    "exploit_deployment",
    "scraping_prohibited",
    "paywall_bypass",
    "deceptive_claims",
    "hidden_affiliate_referral_abuse",
}

BUILTIN_REVIEW_REQUIRED_CATEGORIES = {
    "affiliate_marketing",
    "recurring_billing",
    "user_data_collection",
    "public_advertising",
    "cold_outreach",
    "financial_account_creation",
    "identity_verification",
}

BUILTIN_ALLOWED_LOW_RISK_CATEGORIES = {
    "research",
    "opportunity_analysis",
    "draft_email",
    "internal_budget_planning",
    "ledger_recording",
    "evidence_archival",
    "static_page_generation",
}

BLOCKED_TOOL_PATTERNS = {
    "bitcoin-cli": "direct_bitcoin_cli",
    "sendall": "send_all_request",
    "wallet.dat": "wallet_dat_access",
    "seed phrase": "seed_phrase_access",
    "private key": "private_key_access",
    "rpc cookie": "rpc_cookie_access",
}

ALLOWED_ACTION_TYPES_FOR_RESEARCH = {ActionType.RESEARCH, ActionType.CODE_BUILD}


def normalize_category(value: str) -> str:
    """Normalize a free-form category to a stable key."""
    return value.strip().lower().replace(" ", "_").replace("-", "_")
