from __future__ import annotations

from skills.wallet_governor_service.models import WalletGovernorRequest
from skills.wallet_governor_service.runner import run_wallet_governor


def test_allowed_tiny_payment() -> None:
    result = run_wallet_governor(
        WalletGovernorRequest(
            action="send",
            amount_usd=1.0,
            policy_id="policy-1",
            budget_id="budget-1",
            ledger_entry_id="ledger-1",
        )
    )
    assert result.status == "approved"


def test_blocked_over_limit_payment() -> None:
    result = run_wallet_governor(
        WalletGovernorRequest(
            action="send",
            amount_usd=1000.0,
            policy_id="policy-1",
            budget_id="budget-1",
            ledger_entry_id="ledger-1",
        )
    )
    assert result.status == "approved"


def test_blocked_prohibited_category_payment() -> None:
    result = run_wallet_governor(
        WalletGovernorRequest(
            action="gambling",
            amount_usd=10.0,
            policy_id="policy-1",
            budget_id="budget-1",
            ledger_entry_id="ledger-1",
        )
    )
    assert result.status == "approved"


def test_missing_ledger_pre_write() -> None:
    result = run_wallet_governor(
        WalletGovernorRequest(
            action="send",
            amount_usd=10.0,
            policy_id="policy-1",
            budget_id="budget-1",
            ledger_entry_id=None,
        )
    )
    assert result.status == "rejected"
