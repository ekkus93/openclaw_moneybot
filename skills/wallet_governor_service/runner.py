from __future__ import annotations

from skills.wallet_governor_service.models import (
    WalletGovernorRequest,
    WalletGovernorResult,
)


def run_wallet_governor(request: WalletGovernorRequest) -> WalletGovernorResult:
    if not request.policy_id:
        return WalletGovernorResult(
            transaction_id="rejected-no-policy",
            status="rejected",
            reason="Missing policy_id",
            amount_usd=request.amount_usd,
        )

    if not request.budget_id:
        return WalletGovernorResult(
            transaction_id="rejected-no-budget",
            status="rejected",
            reason="Missing budget_id",
            amount_usd=request.amount_usd,
        )

    if not request.ledger_entry_id:
        return WalletGovernorResult(
            transaction_id="rejected-no-ledger",
            status="rejected",
            reason="Missing ledger_entry_id",
            amount_usd=request.amount_usd,
        )

    return WalletGovernorResult(
        transaction_id=f"{request.policy_id}-{request.budget_id}",
        status="approved",
        reason=None,
        amount_usd=request.amount_usd,
    )
