from __future__ import annotations

from pydantic import BaseModel


class WalletGovernorClientRequest(BaseModel):
    action: str
    amount_usd: float
    policy_id: str | None = None
    budget_id: str | None = None
    ledger_entry_id: str | None = None


class WalletGovernorClientResult(BaseModel):
    transaction_id: str
    status: str
    reason: str | None = None
    amount_usd: float
