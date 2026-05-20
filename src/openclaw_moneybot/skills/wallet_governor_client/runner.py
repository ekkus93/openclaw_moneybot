"""OpenClaw-facing wallet governor client skill."""

from __future__ import annotations

import json

import httpx
from pydantic import JsonValue

from openclaw_moneybot.shared import (
    ArchiveConfig,
    LedgerRecord,
    MoneyBotPolicyConfig,
    SpendRequest,
    WalletGovernorConfig,
)
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    EvidenceArchiveRequest,
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.wallet_governor_client.client import (
    WalletGovernorClientError,
    WalletGovernorHttpClient,
)
from openclaw_moneybot.skills.wallet_governor_client.models import (
    WalletBalanceRequest,
    WalletBalanceResult,
    WalletLimitCheck,
    WalletQuoteSkillRequest,
    WalletQuoteSkillResult,
    WalletSpendRequest,
    WalletSpendResult,
)
from openclaw_moneybot.skills.wallet_governor_client.validation import validate_spend_request
from openclaw_moneybot.utils.ids import make_id
from openclaw_moneybot.utils.time import utc_now


class WalletGovernorClientSkill:
    """Wallet-governor client with deterministic preflight validation."""

    def __init__(
        self,
        config: WalletGovernorConfig,
        policy_config: MoneyBotPolicyConfig,
        ledger_service: LedgerService,
        archive_config: ArchiveConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config
        self.policy_config = policy_config
        self.ledger_service = ledger_service
        self.http_client = WalletGovernorHttpClient(config, transport=transport)
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)

    def close(self) -> None:
        self.http_client.close()

    @staticmethod
    def _as_float(value: JsonValue) -> float:
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            return float(value)
        msg = "wallet governor value must be numeric"
        raise ValueError(msg)

    @staticmethod
    def _json_string_list(values: list[str]) -> list[JsonValue]:
        return [value for value in values]

    @staticmethod
    def _json_string(value: JsonValue | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return str(value)

    @staticmethod
    def _btc_to_usd(amount_btc: str | None, btc_usd_rate: float) -> float:
        if amount_btc is None:
            return 0.0
        return round(float(amount_btc) * btc_usd_rate, 2)

    def get_balance(self, request: WalletBalanceRequest) -> WalletBalanceResult:
        """Read balance and current spend headroom."""
        balance = self.http_client.balance(request.asset)
        limits = self.http_client.limits(request.asset)
        balance_btc = str(balance["balance_btc"])
        usd_estimate = 0.0
        if request.btc_usd_rate is not None:
            usd_estimate = float(balance_btc) * request.btc_usd_rate
        return WalletBalanceResult(
            asset=request.asset,
            confirmed_balance=balance_btc,
            unconfirmed_balance="0",
            usd_estimate=usd_estimate,
            daily_spend_remaining_usd=self._as_float(limits["remaining_daily_usd"]),
            service_limits=limits,
        )

    def quote(self, request: WalletQuoteSkillRequest) -> WalletQuoteSkillResult:
        """Quote a possible spend without sending."""
        try:
            raw_quote = self.http_client.quote_spend(request.model_dump(mode="json"))
        except WalletGovernorClientError as error:
            return WalletQuoteSkillResult(
                status="error",
                asset=request.asset,
                reason="wallet_governor_unavailable",
                amount_usd_estimate=request.amount_usd,
                estimated_fee_usd=0.0,
                limit_check=self._fail_closed_limit_check(),
                rejection_reasons=[str(error)],
                raw_response={"status": "error", "message": str(error)},
            )
        status = str(raw_quote.get("status", "error"))
        if status != "ok":
            raw_reasons = raw_quote.get("rejection_reasons", [])
            reasons = (
                [str(reason) for reason in raw_reasons if isinstance(reason, str)]
                if isinstance(raw_reasons, list)
                else []
            )
            reason = self._json_string(raw_quote.get("reason"))
            if not reasons and reason is not None:
                reasons = [reason]
            return WalletQuoteSkillResult(
                status=status,
                asset=request.asset,
                reason=(
                    reason
                    or ("wallet governor returned an error" if status == "error" else None)
                ),
                amount_usd_estimate=request.amount_usd,
                estimated_fee_usd=0.0,
                limit_check=self._fail_closed_limit_check(),
                rejection_reasons=reasons,
                raw_response=raw_quote,
            )
        limits = self.http_client.limits(request.asset)
        balance = self.http_client.balance(request.asset)
        balance_btc = float(str(balance["balance_btc"]))
        balance_usd = balance_btc * request.btc_usd_rate
        total_usd_estimate = self._as_float(
            raw_quote.get("total_usd_estimate", raw_quote.get("total_usd", request.amount_usd))
        )
        limit_check = WalletLimitCheck(
            single_spend_ok=total_usd_estimate <= self._as_float(limits["max_single_usd"]),
            daily_spend_ok=total_usd_estimate <= self._as_float(limits["remaining_daily_usd"]),
            weekly_spend_ok=total_usd_estimate <= self._as_float(limits["remaining_weekly_usd"]),
            wallet_balance_ok=total_usd_estimate <= balance_usd,
        )
        rejection_reasons: list[str] = []
        if not limit_check.single_spend_ok:
            rejection_reasons.append("single-spend limit exceeded")
        if not limit_check.daily_spend_ok:
            rejection_reasons.append("daily spend limit exceeded")
        if not limit_check.weekly_spend_ok:
            rejection_reasons.append("weekly spend limit exceeded")
        if not limit_check.wallet_balance_ok:
            rejection_reasons.append("insufficient wallet balance")
        return WalletQuoteSkillResult(
            status="ok" if not rejection_reasons else "rejected",
            asset=request.asset,
            amount_usd_estimate=request.amount_usd,
            total_usd_estimate=total_usd_estimate,
            amount_asset_estimate=str(raw_quote["amount_btc"]),
            estimated_fee_asset=str(raw_quote["fee_btc"]),
            estimated_fee_usd=self._as_float(raw_quote.get("estimated_fee_usd", 0.0)),
            limit_check=limit_check,
            rejection_reasons=rejection_reasons,
            raw_response=raw_quote,
        )

    @staticmethod
    def _fail_closed_limit_check() -> WalletLimitCheck:
        return WalletLimitCheck(
            single_spend_ok=False,
            daily_spend_ok=False,
            weekly_spend_ok=False,
            wallet_balance_ok=False,
        )

    def spend(self, request: WalletSpendRequest) -> WalletSpendResult:
        """Preflight, prewrite, send via governor, and archive the response."""
        reasons = validate_spend_request(
            request,
            self.config,
            self.policy_config,
            self.ledger_service,
        )
        spend_request_id = request.spend_request_id or make_id("spend")
        if reasons:
            return self._reject(
                request,
                spend_request_id,
                reasons,
                raw_response={"status": "rejected"},
            )

        spend_request = SpendRequest(
            created_at=utc_now(),
            spend_request_id=spend_request_id,
            opportunity_id=request.opportunity_id,
            budget_plan_id=request.budget_plan_id,
            policy_decision_id=request.policy_decision_id,
            ledger_record_id=request.ledger_event_id,
            amount_usd=request.amount_usd,
            asset=request.asset,
            destination=request.destination,
            counterparty=request.counterparty,
            purpose=request.purpose,
            category=request.category,
            evidence_archive_ids=request.evidence_archive_ids,
            status="proposed",
        )
        self.ledger_service.record_spend_request(
            spend_request,
            idempotency_key=f"wallet:spend:{request.idempotency_key}",
        )

        payload: dict[str, JsonValue] = {
            "spend_request_id": spend_request_id,
            "opportunity_id": request.opportunity_id,
            "budget_plan_id": request.budget_plan_id,
            "policy_decision_id": request.policy_decision_id,
            "ledger_record_id": request.ledger_event_id,
            "amount_usd": request.amount_usd,
            "asset": request.asset,
            "destination": request.destination,
            "counterparty": request.counterparty,
            "purpose": request.purpose,
            "category": request.category,
            "btc_usd_rate": request.btc_usd_rate,
            "send_all": False,
            "evidence_archive_ids": self._json_string_list(request.evidence_archive_ids),
            "idempotency_key": request.idempotency_key,
        }
        try:
            raw_response = self.http_client.send_small_payment(payload)
        except WalletGovernorClientError as error:
            return self._error(
                request,
                spend_request_id,
                [str(error)],
                raw_response={"status": "error", "message": str(error)},
            )

        evidence_id = self._archive_response(
            spend_request_id,
            json.dumps(raw_response, indent=2, sort_keys=True),
        )
        status = str(raw_response.get("status", "error"))
        if status == "sent":
            wallet_transaction_id = raw_response.get("wallet_transaction_id")
            ledger_recorded = isinstance(wallet_transaction_id, str) and (
                self.ledger_service.get_wallet_transaction(wallet_transaction_id) is not None
            )
            if not ledger_recorded:
                return self._error(
                    request,
                    spend_request_id,
                    ["post-send ledger recording failed"],
                    raw_response=raw_response,
                    evidence_id=evidence_id,
                )
            return WalletSpendResult(
                status="sent",
                spend_request_id=spend_request_id,
                wallet_transaction_id=str(wallet_transaction_id),
                asset=request.asset,
                amount_asset=str(raw_response.get("amount_btc")),
                amount_usd_estimate=request.amount_usd,
                fee_asset=str(raw_response.get("fee_btc")),
                fee_usd_estimate=self._btc_to_usd(
                    self._json_string(raw_response.get("fee_btc")),
                    request.btc_usd_rate,
                ),
                destination=request.destination,
                txid_or_signature=str(raw_response.get("txid")),
                receipt_required=request.receipt_expected,
                ledger_recorded=True,
                wallet_governor_decision_id=str(raw_response.get("wallet_transaction_id")),
                raw_response_evidence_id=evidence_id,
            )
        if status == "rejected":
            raw_reasons = raw_response.get("rejection_reasons", [])
            reasons_list = raw_reasons if isinstance(raw_reasons, list) else []
            rejection_reasons = [
                str(reason) for reason in reasons_list if isinstance(reason, str)
            ] or [str(raw_response.get("reason", "wallet governor rejected request"))]
            self._record_audit_event(
                "wallet_client_rejected",
                spend_request_id,
                {
                    "request_idempotency_key": request.idempotency_key,
                    "rejection_reasons": self._json_string_list(rejection_reasons),
                    "raw_response_evidence_id": evidence_id,
                },
            )
            return WalletSpendResult(
                status="rejected",
                spend_request_id=spend_request_id,
                asset=request.asset,
                amount_usd_estimate=request.amount_usd,
                destination=request.destination,
                fee_usd_estimate=self._btc_to_usd(
                    self._json_string(raw_response.get("fee_btc")),
                    request.btc_usd_rate,
                ),
                rejection_reasons=rejection_reasons,
                receipt_required=request.receipt_expected,
                ledger_recorded=True,
                raw_response_evidence_id=evidence_id,
            )
        return self._error(
            request,
            spend_request_id,
            ["wallet governor returned an error"],
            raw_response=raw_response,
            evidence_id=evidence_id,
        )

    def _reject(
        self,
        request: WalletSpendRequest,
        spend_request_id: str,
        reasons: list[str],
        *,
        raw_response: dict[str, JsonValue],
    ) -> WalletSpendResult:
        evidence_id = self._archive_response(spend_request_id, json.dumps(raw_response, indent=2))
        self._record_audit_event(
            "wallet_client_preflight_rejected",
            spend_request_id,
            {
                "request_idempotency_key": request.idempotency_key,
                "rejection_reasons": self._json_string_list(reasons),
                "raw_response_evidence_id": evidence_id,
            },
        )
        return WalletSpendResult(
            status="rejected",
            spend_request_id=spend_request_id,
            asset=request.asset,
            amount_usd_estimate=request.amount_usd,
            destination=request.destination,
            fee_usd_estimate=0.0,
            rejection_reasons=reasons,
            receipt_required=request.receipt_expected,
            ledger_recorded=True,
            raw_response_evidence_id=evidence_id,
        )

    def _error(
        self,
        request: WalletSpendRequest,
        spend_request_id: str,
        reasons: list[str],
        *,
        raw_response: dict[str, JsonValue],
        evidence_id: str | None = None,
    ) -> WalletSpendResult:
        response_evidence_id = evidence_id or self._archive_response(
            spend_request_id,
            json.dumps(raw_response, indent=2),
        )
        self._record_audit_event(
            "wallet_client_error",
            spend_request_id,
            {
                "request_idempotency_key": request.idempotency_key,
                "error_reasons": self._json_string_list(reasons),
                "raw_response_evidence_id": response_evidence_id,
            },
        )
        return WalletSpendResult(
            status="error",
            spend_request_id=spend_request_id,
            asset=request.asset,
            amount_usd_estimate=request.amount_usd,
            destination=request.destination,
            fee_usd_estimate=self._btc_to_usd(
                self._json_string(raw_response.get("fee_btc")),
                request.btc_usd_rate,
            ),
            rejection_reasons=reasons,
            receipt_required=request.receipt_expected,
            ledger_recorded=True,
            raw_response_evidence_id=response_evidence_id,
        )

    def _archive_response(self, spend_request_id: str, payload: str) -> str:
        archived = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.AUDIT_EVENT,
                related_id=spend_request_id,
                evidence_type="wallet_governor_response",
                content_text=payload,
                notes="Wallet governor client outcome payload",
            )
        )
        return archived.evidence_id

    def _record_audit_event(
        self,
        event_name: str,
        spend_request_id: str,
        payload: dict[str, JsonValue],
    ) -> None:
        record = LedgerRecord(
            created_at=utc_now(),
            record_id=make_id("audit"),
            record_type=RecordType.AUDIT_EVENT,
            related_record_id=spend_request_id,
            payload={
                "event_name": event_name,
                "spend_request_id": spend_request_id,
                **payload,
            },
        )
        self.ledger_service.record_ledger_record(
            record,
            idempotency_key=f"audit:{event_name}:{spend_request_id}",
        )
