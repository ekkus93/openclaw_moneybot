"""Local-only wallet governor service logic."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from openclaw_moneybot.plugins.wallet_governor_service.backend import WalletBackend
from openclaw_moneybot.plugins.wallet_governor_service.models import (
    WalletBalanceResponse,
    WalletHealthResponse,
    WalletLimitsResponse,
    WalletQuoteRequest,
    WalletQuoteResponse,
    WalletSendRequest,
    WalletSendResponse,
)
from openclaw_moneybot.shared import (
    MoneyBotPolicyConfig,
    SpendRequest,
    WalletGovernorConfig,
    WalletTransactionRecord,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.utils.ids import make_id
from openclaw_moneybot.utils.time import utc_now

SATOSHIS_PER_BTC = Decimal("100000000")


def _btc_from_sats(amount_sats: int) -> str:
    btc = Decimal(amount_sats) / SATOSHIS_PER_BTC
    return str(btc.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))


class WalletGovernorService:
    """Guard wallet access behind deterministic rules."""

    def __init__(
        self,
        config: WalletGovernorConfig,
        policy_config: MoneyBotPolicyConfig,
        ledger_service: LedgerService,
        backend: WalletBackend,
        *,
        max_unlock_seconds: int = 5,
    ) -> None:
        self.config = config
        self.policy_config = policy_config
        self.ledger_service = ledger_service
        self.backend = backend
        self.max_unlock_seconds = max_unlock_seconds
        self._responses: dict[str, WalletSendResponse] = {}

    def health(self) -> WalletHealthResponse:
        """Return local-only health metadata."""
        return WalletHealthResponse(
            status="ok",
            spend_enabled=self.config.spend_enabled,
            backend=self.backend.backend_name,
            allowed_assets=self.config.allowed_assets,
        )

    def balance(self, asset: str = "BTC") -> WalletBalanceResponse:
        """Return current fake or real wallet balance."""
        self._require_supported_asset(asset)
        balance_sats = self.backend.get_balance_sats()
        return WalletBalanceResponse(
            asset=asset,
            balance_btc=_btc_from_sats(balance_sats),
            balance_sats=balance_sats,
        )

    def limits(self, asset: str = "BTC") -> WalletLimitsResponse:
        """Resolve current daily and weekly spend headroom."""
        self._require_supported_asset(asset)
        today = utc_now().date().isoformat()
        daily_spend = self.ledger_service.get_daily_spend_total(today)
        weekly_spend = self.ledger_service.get_weekly_spend_total(today)
        return WalletLimitsResponse(
            asset=asset,
            spend_enabled=self.config.spend_enabled,
            max_single_usd=self.policy_config.max_single_spend_usd,
            max_daily_usd=self.policy_config.max_daily_spend_usd,
            max_weekly_usd=self.policy_config.max_weekly_spend_usd,
            remaining_daily_usd=max(self.policy_config.max_daily_spend_usd - daily_spend, 0.0),
            remaining_weekly_usd=max(self.policy_config.max_weekly_spend_usd - weekly_spend, 0.0),
        )

    def quote(self, request: WalletQuoteRequest) -> WalletQuoteResponse:
        """Return a deterministic BTC quote."""
        self._require_supported_asset(request.asset)
        amount_sats = self._usd_to_sats(request.amount_usd, request.btc_usd_rate)
        fee_sats = self.backend.estimate_fee_sats(amount_sats)
        return WalletQuoteResponse(
            asset=request.asset,
            amount_btc=_btc_from_sats(amount_sats),
            amount_sats=amount_sats,
            fee_btc=_btc_from_sats(fee_sats),
            fee_sats=fee_sats,
            amount_usd=request.amount_usd,
            total_usd=request.amount_usd,
        )

    def capped_send(self, request: WalletSendRequest) -> WalletSendResponse:
        """Attempt a governed BTC send with preflight checks and ledger writes."""
        cached = self._responses.get(request.idempotency_key)
        if cached is not None:
            return cached
        if not self.config.spend_enabled:
            return self._store_rejection(request.idempotency_key, "spend_disabled")

        self._require_supported_asset(request.asset)
        self._enforce_limits(request.amount_usd)
        quote = self.quote(
            WalletQuoteRequest(
                asset=request.asset,
                amount_usd=request.amount_usd,
                btc_usd_rate=request.btc_usd_rate,
                destination=request.destination,
            )
        )
        balance_sats = self.backend.get_balance_sats()
        if quote.amount_sats + quote.fee_sats > balance_sats:
            return self._store_rejection(request.idempotency_key, "insufficient_balance")

        spend_request_id = request.spend_request_id or make_id("spend")
        spend_request = SpendRequest(
            created_at=utc_now(),
            spend_request_id=spend_request_id,
            opportunity_id=request.opportunity_id,
            budget_plan_id=request.budget_plan_id,
            policy_decision_id=request.policy_decision_id,
            ledger_record_id=request.ledger_record_id,
            amount_usd=request.amount_usd,
            asset=request.asset,
            destination=request.destination,
            counterparty=request.counterparty,
            purpose=request.purpose,
            category=request.category,
            evidence_archive_ids=request.evidence_archive_ids,
        )
        self.ledger_service.record_spend_request(
            spend_request,
            idempotency_key=f"wallet:spend:{request.idempotency_key}",
        )

        self.backend.unlock(self.max_unlock_seconds)
        try:
            txid = self.backend.send_to_address(request.destination, quote.amount_sats)
        finally:
            self.backend.lock()

        wallet_transaction_id = make_id("wallet_tx")
        transaction = WalletTransactionRecord(
            created_at=utc_now(),
            wallet_transaction_id=wallet_transaction_id,
            spend_request_id=spend_request_id,
            txid=txid,
            amount_btc=quote.amount_btc,
            fee_btc=quote.fee_btc,
            amount_usd_estimate=request.amount_usd,
            status="sent",
            destination=request.destination,
            purpose=request.purpose,
        )
        self.ledger_service.record_wallet_transaction(
            transaction,
            idempotency_key=f"wallet:tx:{request.idempotency_key}",
        )
        response = WalletSendResponse(
            status="sent",
            spend_request_id=spend_request_id,
            wallet_transaction_id=wallet_transaction_id,
            txid=txid,
            amount_btc=quote.amount_btc,
            fee_btc=quote.fee_btc,
            amount_usd=request.amount_usd,
        )
        self._responses[request.idempotency_key] = response
        return response

    def _store_rejection(self, idempotency_key: str, reason: str) -> WalletSendResponse:
        response = WalletSendResponse(status="rejected", reason=reason)
        self._responses[idempotency_key] = response
        return response

    def _enforce_limits(self, amount_usd: float) -> None:
        if amount_usd > self.policy_config.max_single_spend_usd:
            msg = "Amount exceeds max single spend."
            raise ValueError(msg)
        today = utc_now().date().isoformat()
        daily_total = self.ledger_service.get_daily_spend_total(today)
        weekly_total = self.ledger_service.get_weekly_spend_total(today)
        if daily_total + amount_usd > self.policy_config.max_daily_spend_usd:
            msg = "Amount exceeds max daily spend."
            raise ValueError(msg)
        if weekly_total + amount_usd > self.policy_config.max_weekly_spend_usd:
            msg = "Amount exceeds max weekly spend."
            raise ValueError(msg)

    def _require_supported_asset(self, asset: str) -> None:
        if asset not in self.config.allowed_assets:
            msg = f"Unsupported asset: {asset}"
            raise ValueError(msg)

    @staticmethod
    def _usd_to_sats(amount_usd: float, btc_usd_rate: float) -> int:
        btc = Decimal(str(amount_usd)) / Decimal(str(btc_usd_rate))
        sats = btc * SATOSHIS_PER_BTC
        return int(sats.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
