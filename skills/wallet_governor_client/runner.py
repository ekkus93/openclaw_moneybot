from __future__ import annotations

from skills.wallet_governor_client.models import (
    WalletGovernorClientRequest,
    WalletGovernorClientResult,
)


def run_wallet_governor_client(
    request: WalletGovernorClientRequest,
) -> WalletGovernorClientResult:
    if not request.policy_id:
        return WalletGovernorClientResult(
            transaction_id="rejected-no-policy",
            status="rejected",
            reason="Missing policy_id",
            amount_usd=request.amount_usd,
        )

    if not request.budget_id:
        return WalletGovernorClientResult(
            transaction_id="rejected-no-budget",
            status="rejected",
            reason="Missing budget_id",
            amount_usd=request.amount_usd,
        )

    if not request.ledger_entry_id:
        return WalletGovernorClientResult(
            transaction_id="rejected-no-ledger",
            status="rejected",
            reason="Missing ledger_entry_id",
            amount_usd=request.amount_usd,
        )

    return WalletGovernorClientResult(
        transaction_id=f"{request.policy_id}-{request.budget_id}",
        status="approved",
        reason=None,
        amount_usd=request.amount_usd,
    )
