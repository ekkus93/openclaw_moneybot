"""Local-only wallet governor service logic."""

from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from pydantic import JsonValue

from openclaw_moneybot.plugins.wallet_governor_service.backend import (
    WalletBackend,
    WalletBackendError,
)
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
    EvidenceRecord,
    LedgerRecord,
    MoneyBotPolicyConfig,
    PolicyDecision,
    SpendRequest,
    SpendRequestStatus,
    WalletGovernorConfig,
    WalletTransactionRecord,
    WalletTransactionStatus,
)
from openclaw_moneybot.shared.types import (
    ActionType,
    BudgetDecisionType,
    PolicyDecisionType,
    RecordType,
    TosDecisionType,
)
from openclaw_moneybot.skills.ledger_skill.models import SpendAuthorizationBundle
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver.hashing import verify_file_hash
from openclaw_moneybot.utils.ids import make_id
from openclaw_moneybot.utils.time import utc_now

SATOSHIS_PER_BTC = Decimal("100000000")
BTC_ADDRESS_PREFIXES = ("bc1", "tb1", "bcrt1", "1", "3")
PROHIBITED_SEND_TERMS = ("send_all", "send all", "sweep", "max", "all funds")
PLACEHOLDER_DESTINATIONS = {"example", "placeholder", "todo", "changeme", "test"}
ALLOWED_SPEND_CATEGORIES = {
    "purchase",
    "infrastructure",
    "domain",
    "hosting",
    "listing_fee",
    "software_tool",
    "software_credit",
    "bounty_submission_fee",
    "experiment_material",
}
BLOCKED_SPEND_CATEGORIES = {
    "gambling",
    "prediction markets",
    "prediction_market",
    "securities trading",
    "securities_trading",
    "options trading",
    "options_trading",
    "forex trading",
    "forex_trading",
    "futures trading",
    "futures_trading",
    "leveraged products",
    "leveraged_products",
    "autonomous crypto trading",
    "autonomous_crypto_trading",
    "defi/yield farming",
    "defi",
    "yield_farming",
    "nft trading/minting/speculation",
    "nft_speculation",
    "token speculation",
    "token_speculation",
    "airdrop farming",
    "airdrop_farming",
    "money transmission",
    "money_transmission",
    "escrow",
    "exchange/broker behavior",
    "exchange_behavior",
    "broker_behavior",
    "mixing/tumbling",
    "mixing",
    "tumbling",
    "kyc evasion",
    "kyc_evasion",
    "fake accounts",
    "fake_accounts",
    "account farming",
    "account_farming",
    "fake reviews",
    "fake_reviews",
    "spam",
    "phishing",
    "malware",
    "credential harvesting",
    "credential_harvesting",
    "scraping against terms",
    "scraping_against_terms",
    "paywall bypass",
    "paywall_bypass",
    "handling other people's funds",
    "handling_other_peoples_funds",
    "impersonation",
    "deceptive claims",
    "deceptive_claims",
}
ELIGIBLE_SPEND_STATUSES = {SpendRequestStatus.PROPOSED, SpendRequestStatus.APPROVED}
TERMINAL_SPEND_STATUSES = {
    SpendRequestStatus.REJECTED,
    SpendRequestStatus.SENT,
    SpendRequestStatus.CONFIRMED,
    SpendRequestStatus.FAILED,
    SpendRequestStatus.CANCELLED,
}
EXECUTABLE_POLICY_ACTIONS = {
    ActionType.SPEND,
    ActionType.WALLET_TRANSFER,
    ActionType.PURCHASE,
}
WALLET_TOOL_MARKERS = ("wallet",)


def _btc_from_sats(amount_sats: int) -> str:
    btc = Decimal(amount_sats) / SATOSHIS_PER_BTC
    return str(btc.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))


def _round_usd(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


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
        self._response_fingerprints: dict[str, str] = {}

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
        return WalletLimitsResponse(
            asset=asset,
            spend_enabled=self.config.spend_enabled,
            max_single_usd=self.policy_config.max_single_spend_usd,
            max_daily_usd=self.policy_config.max_daily_spend_usd,
            max_weekly_usd=self.policy_config.max_weekly_spend_usd,
            remaining_daily_usd=self.ledger_service.get_remaining_daily_limit(
                today,
                self.policy_config.max_daily_spend_usd,
            ),
            remaining_weekly_usd=self.ledger_service.get_remaining_weekly_limit(
                today,
                self.policy_config.max_weekly_spend_usd,
            ),
        )

    def quote(self, request: WalletQuoteRequest) -> WalletQuoteResponse:
        """Return a deterministic BTC quote."""
        try:
            self._require_supported_asset(request.asset)
        except ValueError:
            return WalletQuoteResponse(
                status="rejected",
                asset=request.asset,
                amount_usd=request.amount_usd,
                reason="unsupported_asset",
                rejection_reasons=["unsupported_asset"],
            )
        destination_error = self._destination_error(
            request.asset,
            request.destination,
            purpose=None,
        )
        if destination_error is not None:
            return WalletQuoteResponse(
                status="rejected",
                asset=request.asset,
                amount_usd=request.amount_usd,
                reason=destination_error,
                rejection_reasons=[destination_error],
            )
        amount_sats = self._usd_to_sats(request.amount_usd, request.btc_usd_rate)
        try:
            fee_sats = self.backend.estimate_fee_sats(amount_sats)
        except WalletBackendError:
            return WalletQuoteResponse(
                status="rejected",
                asset=request.asset,
                amount_usd=request.amount_usd,
                reason="fee_quote_failed",
                rejection_reasons=["fee_quote_failed"],
            )
        estimated_fee_usd = self._sats_to_usd(fee_sats, request.btc_usd_rate)
        total_usd_estimate = _round_usd(request.amount_usd + estimated_fee_usd)
        return WalletQuoteResponse(
            status="ok",
            asset=request.asset,
            amount_btc=_btc_from_sats(amount_sats),
            amount_sats=amount_sats,
            fee_btc=_btc_from_sats(fee_sats),
            fee_sats=fee_sats,
            amount_usd=request.amount_usd,
            estimated_fee_usd=estimated_fee_usd,
            total_usd_estimate=total_usd_estimate,
            total_usd=total_usd_estimate,
        )

    def quote_json(self, payload: dict[str, object]) -> dict[str, object]:
        """Validate and quote a request from HTTP JSON."""
        request = WalletQuoteRequest.model_validate(payload)
        return self.quote(request).model_dump(mode="json")

    def capped_send(self, request: WalletSendRequest) -> WalletSendResponse:
        """Attempt a governed BTC send with service-side authorization checks."""
        request_fingerprint = json.dumps(
            request.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        cached = self._responses.get(request.idempotency_key)
        if cached is not None:
            if self._response_fingerprints[request.idempotency_key] != request_fingerprint:
                return self._store_rejection(
                    request,
                    "idempotency_conflict",
                    related_record_id=request.spend_request_id,
                    cache_response=False,
                )
            return cached

        related_record_id = request.spend_request_id or request.idempotency_key
        self._record_audit_event(
            "wallet_send_request_received",
            related_record_id,
            {
                "idempotency_key": request.idempotency_key,
                "request_summary": self._request_summary(request),
            },
            idempotency_key=f"audit:wallet_send_request_received:{request.idempotency_key}",
        )
        self._record_audit_event(
            "wallet_send_validation_started",
            related_record_id,
            {
                "idempotency_key": request.idempotency_key,
                "spend_request_id": request.spend_request_id,
            },
            idempotency_key=f"audit:wallet_send_validation_started:{request.idempotency_key}",
        )
        bundle = (
            None
            if request.spend_request_id is None
            else self.ledger_service.get_spend_authorization_bundle(request.spend_request_id)
        )
        if not self.config.spend_enabled:
            return self._store_rejection(
                request,
                "spend_disabled",
                bundle=bundle,
                related_record_id=related_record_id,
                cache_fingerprint=request_fingerprint,
            )

        if request.spend_request_id is None:
            return self._store_rejection(
                request,
                "spend_request_missing",
                related_record_id=related_record_id,
                cache_fingerprint=request_fingerprint,
            )

        try:
            self._require_supported_asset(request.asset)
        except ValueError:
            return self._store_rejection(
                request,
                "unsupported_asset",
                bundle=bundle,
                related_record_id=related_record_id,
                cache_fingerprint=request_fingerprint,
            )

        if bundle is None:
            return self._store_rejection(
                request,
                "spend_request_not_found",
                related_record_id=related_record_id,
                cache_fingerprint=request_fingerprint,
            )

        validation_error = self._validate_bundle(request, bundle)
        if validation_error is not None:
            return self._store_rejection(
                request,
                validation_error,
                bundle=bundle,
                cache_fingerprint=request_fingerprint,
            )

        quote = self.quote(
            WalletQuoteRequest(
                asset=request.asset,
                amount_usd=request.amount_usd,
                btc_usd_rate=request.btc_usd_rate,
                destination=request.destination,
            )
        )
        if quote.status != "ok":
            return self._store_rejection(
                request,
                quote.reason or "fee_quote_failed",
                bundle=bundle,
                cache_fingerprint=request_fingerprint,
            )
        assert quote.total_usd_estimate is not None
        assert quote.amount_sats is not None
        assert quote.amount_btc is not None
        assert quote.fee_sats is not None
        assert quote.fee_btc is not None

        limit_rejection = self._limit_rejection_code(quote.total_usd_estimate)
        if limit_rejection is not None:
            return self._store_rejection(
                request,
                limit_rejection,
                bundle=bundle,
                cache_fingerprint=request_fingerprint,
            )

        try:
            balance_sats = self.backend.get_balance_sats()
        except WalletBackendError:
            return self._store_failure(
                request,
                "backend_error",
                bundle=bundle,
                cache_fingerprint=request_fingerprint,
            )
        if quote.amount_sats + quote.fee_sats > balance_sats:
            return self._store_rejection(
                request,
                "insufficient_balance",
                bundle=bundle,
                cache_fingerprint=request_fingerprint,
            )

        self.ledger_service.update_spend_request_status(
            request.spend_request_id,
            SpendRequestStatus.APPROVED.value,
            idempotency_key=f"wallet:spend-status:approved:{request.idempotency_key}",
        )
        self.ledger_service.update_spend_request_status(
            request.spend_request_id,
            SpendRequestStatus.SENDING.value,
            idempotency_key=f"wallet:spend-status:sending:{request.idempotency_key}",
        )
        self._record_audit_event(
            "wallet_backend_send_started",
            request.spend_request_id,
            {
                "idempotency_key": request.idempotency_key,
                "amount_usd": request.amount_usd,
                "estimated_fee_usd": quote.estimated_fee_usd,
                "total_usd_estimate": quote.total_usd_estimate,
            },
            idempotency_key=f"audit:wallet_backend_send_started:{request.idempotency_key}",
        )

        unlock_succeeded = False
        lock_failure = False
        try:
            self.backend.unlock(self.max_unlock_seconds)
            unlock_succeeded = True
            txid = self.backend.send_to_address(request.destination, quote.amount_sats)
        except WalletBackendError:
            reason = "wallet_unlock_failed" if not unlock_succeeded else "wallet_send_failed"
            response = self._store_failure(
                request,
                reason,
                bundle=bundle,
                cache_fingerprint=request_fingerprint,
            )
            self._record_audit_event(
                "wallet_backend_send_failed",
                request.spend_request_id,
                {
                    "idempotency_key": request.idempotency_key,
                    "reason_code": reason,
                    "request_summary": self._request_summary(request),
                    "response_summary": self._response_summary(response),
                },
                idempotency_key=f"audit:wallet_backend_send_failed:{request.idempotency_key}",
            )
            return response
        finally:
            if unlock_succeeded:
                try:
                    self.backend.lock()
                except WalletBackendError:
                    lock_failure = True
                    self._record_audit_event(
                        "wallet_lock_failed",
                        request.spend_request_id or request.idempotency_key,
                        {
                            "idempotency_key": request.idempotency_key,
                            "reason_code": "wallet_lock_failed",
                            "request_summary": self._request_summary(request),
                        },
                        idempotency_key=f"audit:wallet_lock_failed:{request.idempotency_key}",
                    )

        wallet_transaction_id = make_id("wallet_tx")
        transaction = WalletTransactionRecord(
            created_at=utc_now(),
            wallet_transaction_id=wallet_transaction_id,
            spend_request_id=request.spend_request_id,
            txid=txid,
            amount_btc=quote.amount_btc,
            fee_btc=quote.fee_btc,
            amount_usd_estimate=request.amount_usd,
            fee_usd_estimate=quote.estimated_fee_usd,
            total_usd_estimate=quote.total_usd_estimate,
            status=WalletTransactionStatus.SENT,
            destination=request.destination,
            purpose=request.purpose,
        )
        self.ledger_service.record_wallet_transaction(
            transaction,
            idempotency_key=f"wallet:tx:{request.idempotency_key}",
        )
        self.ledger_service.update_spend_request_status(
            request.spend_request_id,
            SpendRequestStatus.SENT.value,
            idempotency_key=f"wallet:spend-status:sent:{request.idempotency_key}",
        )
        response = WalletSendResponse(
            status="sent",
            spend_request_id=request.spend_request_id,
            wallet_transaction_id=wallet_transaction_id,
            txid=txid,
            amount_btc=quote.amount_btc,
            fee_btc=quote.fee_btc,
            amount_usd=request.amount_usd,
            warnings=["wallet_lock_failed"] if lock_failure else [],
        )
        self._record_audit_event(
            "wallet_backend_send_succeeded",
            request.spend_request_id,
            {
                "idempotency_key": request.idempotency_key,
                "wallet_transaction_id": wallet_transaction_id,
                "txid": txid,
                "request_summary": self._request_summary(request),
                "response_summary": self._response_summary(response),
            },
            idempotency_key=f"audit:wallet_backend_send_succeeded:{request.idempotency_key}",
        )
        self._responses[request.idempotency_key] = response
        self._response_fingerprints[request.idempotency_key] = request_fingerprint
        return response

    def capped_send_json(self, payload: dict[str, object]) -> dict[str, object]:
        """Validate and send from HTTP JSON."""
        request = WalletSendRequest.model_validate(payload)
        return self.capped_send(request).model_dump(mode="json")

    def _validate_bundle(
        self,
        request: WalletSendRequest,
        bundle: SpendAuthorizationBundle,
    ) -> str | None:
        spend_request = bundle.spend_request
        if spend_request.status not in ELIGIBLE_SPEND_STATUSES:
            return "spend_request_status_invalid"
        if bundle.prior_wallet_transactions:
            return "spend_request_status_invalid"
        if not bundle.ledger_record_exists:
            return "spend_request_missing"
        if request.policy_decision_id != spend_request.policy_decision_id:
            return "policy_id_mismatch"
        if request.budget_plan_id != spend_request.budget_plan_id:
            return "budget_id_mismatch"
        if request.ledger_record_id != spend_request.ledger_record_id:
            return "ledger_record_mismatch"
        if request.amount_usd != spend_request.amount_usd:
            return "amount_mismatch"
        if request.destination != spend_request.destination:
            return "destination_mismatch"
        if request.category != spend_request.category:
            return "category_mismatch"
        if request.counterparty != spend_request.counterparty:
            return "counterparty_mismatch"
        if request.purpose != spend_request.purpose:
            return "purpose_mismatch"
        if request.opportunity_id != spend_request.opportunity_id:
            return "opportunity_id_mismatch"
        if request.experiment_id != spend_request.experiment_id:
            return "experiment_id_mismatch"
        if set(request.evidence_archive_ids) != set(spend_request.evidence_archive_ids):
            return "evidence_ids_mismatch"

        policy_error = self._policy_authorization_error(bundle.policy_decision, spend_request)
        if policy_error is not None:
            return policy_error

        budget = bundle.budget_plan
        if budget is None:
            return "budget_missing"
        if budget.decision is not BudgetDecisionType.EXECUTE_REQUEST:
            return "budget_not_executable"
        if not budget.wallet_spend_request_allowed:
            return "budget_wallet_spend_not_allowed"
        if (
            request.amount_usd > budget.recommended_budget_usd
            or request.amount_usd > budget.max_loss_usd
        ):
            return "budget_amount_exceeded"
        if budget.opportunity_id != spend_request.opportunity_id:
            return "budget_not_executable"
        if not budget.success_metric.strip() or not budget.stop_condition.strip():
            return "budget_not_executable"
        if (
            budget.approved_spend_categories
            and request.category not in budget.approved_spend_categories
        ):
            return "budget_wallet_spend_not_allowed"

        tos_legal_check = bundle.tos_legal_check
        if tos_legal_check is None:
            return "tos_missing"
        if tos_legal_check.decision is not TosDecisionType.PROCEED:
            return "tos_not_proceed"
        if tos_legal_check.opportunity_id != spend_request.opportunity_id:
            return "tos_not_proceed"
        if not tos_legal_check.evidence_archive_ids:
            return "evidence_missing"

        category = request.category.strip().lower()
        if not category:
            return "category_missing"
        if category in BLOCKED_SPEND_CATEGORIES or category in set(
            self.policy_config.blocked_categories
        ):
            return "category_blocked"
        if category not in ALLOWED_SPEND_CATEGORIES:
            return "category_unknown"

        if not spend_request.evidence_archive_ids:
            return "evidence_missing"
        evidence_by_id = {record.evidence_id: record for record in bundle.evidence_records}
        found_evidence_ids = set(evidence_by_id)
        required_evidence_ids = set(spend_request.evidence_archive_ids) | set(
            tos_legal_check.evidence_archive_ids
        )
        required_evidence_ids.update(budget.required_evidence_ids)
        if not required_evidence_ids.issubset(found_evidence_ids):
            return "evidence_missing"
        for evidence_id in required_evidence_ids:
            evidence_error = self._validate_evidence_artifact(
                bundle,
                evidence_by_id[evidence_id],
            )
            if evidence_error is not None:
                return evidence_error

        return self._destination_error(request.asset, request.destination, request.purpose)

    def _policy_authorization_error(
        self,
        policy: PolicyDecision | None,
        spend_request: SpendRequest,
    ) -> str | None:
        if policy is None:
            return "policy_missing"
        if policy.decision is not PolicyDecisionType.ALLOW:
            return "policy_not_allow"
        if (
            policy.action_type is None
            or policy.category is None
            or policy.amount_usd is None
            or not policy.sanitized_input
        ):
            return "policy_metadata_missing"
        if policy.action_type not in EXECUTABLE_POLICY_ACTIONS:
            return "policy_not_executable"
        if not policy.requires_wallet_action or not policy.requires_payment:
            return "policy_not_executable"
        if policy.opportunity_id != spend_request.opportunity_id:
            return "policy_context_mismatch"
        if policy.experiment_id != spend_request.experiment_id:
            return "policy_context_mismatch"
        if (
            policy.spend_request_id is not None
            and policy.spend_request_id != spend_request.spend_request_id
        ):
            return "policy_context_mismatch"
        if policy.amount_usd < spend_request.amount_usd:
            return "policy_amount_exceeded"
        if (
            policy.counterparty is not None
            and policy.counterparty != spend_request.counterparty
        ):
            return "policy_counterparty_mismatch"
        if policy.category.strip().lower() != spend_request.category.strip().lower():
            return "policy_category_mismatch"
        normalized_tools = [tool.lower() for tool in policy.planned_tools]
        if not normalized_tools or not any(
            any(marker in tool for marker in WALLET_TOOL_MARKERS)
            for tool in normalized_tools
        ):
            return "policy_not_executable"
        return None

    def _is_related_evidence(
        self,
        bundle: SpendAuthorizationBundle,
        evidence: EvidenceRecord,
    ) -> bool:
        allowed_pairs = {
            (RecordType.OPPORTUNITY, bundle.spend_request.opportunity_id),
            (RecordType.BUDGET_PLAN, bundle.spend_request.budget_plan_id),
            (RecordType.SPEND_REQUEST, bundle.spend_request.spend_request_id),
            (
                RecordType.TOS_LEGAL_CHECK,
                (
                    None
                    if bundle.tos_legal_check is None
                    else bundle.tos_legal_check.tos_legal_check_id
                ),
            ),
        }
        return (evidence.related_record_type, evidence.related_record_id) in allowed_pairs

    def _validate_evidence_artifact(
        self,
        bundle: SpendAuthorizationBundle,
        evidence: EvidenceRecord,
    ) -> str | None:
        if not self._is_related_evidence(bundle, evidence):
            return "evidence_unrelated"
        archive_root = self.config.archive_root
        if archive_root is None:
            return "evidence_path_invalid"
        resolved_root = archive_root.expanduser().resolve(strict=False)
        raw_path = Path(evidence.archive_path).expanduser()
        resolved_path = (
            raw_path.resolve(strict=False)
            if raw_path.is_absolute()
            else (resolved_root / raw_path).resolve(strict=False)
        )
        if not (resolved_root == resolved_path or resolved_root in resolved_path.parents):
            return "evidence_path_invalid"
        if not resolved_path.exists() or not resolved_path.is_file():
            return "evidence_missing"
        if not verify_file_hash(resolved_path, evidence.content_sha256):
            return "evidence_hash_mismatch"
        metadata_path_value = evidence.metadata.get("metadata_path")
        if isinstance(metadata_path_value, str):
            metadata_path = Path(metadata_path_value).expanduser()
            resolved_metadata_path = (
                metadata_path.resolve(strict=False)
                if metadata_path.is_absolute()
                else (resolved_root / metadata_path).resolve(strict=False)
            )
            if not (
                resolved_root == resolved_metadata_path
                or resolved_root in resolved_metadata_path.parents
            ):
                return "evidence_path_invalid"
            if not resolved_metadata_path.exists() or not resolved_metadata_path.is_file():
                return "evidence_missing"
        return None

    def _store_rejection(
        self,
        request: WalletSendRequest,
        reason: str,
        *,
        bundle: SpendAuthorizationBundle | None = None,
        related_record_id: str | None = None,
        cache_fingerprint: str | None = None,
        cache_response: bool = True,
    ) -> WalletSendResponse:
        spend_request_id = (
            request.spend_request_id if related_record_id is None else related_record_id
        ) or request.idempotency_key
        self._update_spend_status_for_outcome(
            bundle,
            post_send_failure=False,
            idempotency_key=request.idempotency_key,
            reason=reason,
        )
        response = WalletSendResponse(
            status="rejected",
            spend_request_id=spend_request_id,
            amount_usd=request.amount_usd,
            reason=reason,
            rejection_reasons=[reason],
        )
        self._record_audit_event(
            "wallet_send_rejected",
            spend_request_id,
            {
                "idempotency_key": request.idempotency_key,
                "reason_code": reason,
                "request_summary": self._request_summary(request),
                "response_summary": self._response_summary(response),
            },
            idempotency_key=f"audit:wallet_send_rejected:{request.idempotency_key}:{reason}",
        )
        if cache_response:
            self._responses[request.idempotency_key] = response
            if cache_fingerprint is not None:
                self._response_fingerprints[request.idempotency_key] = cache_fingerprint
        return response

    def _store_failure(
        self,
        request: WalletSendRequest,
        reason: str,
        *,
        bundle: SpendAuthorizationBundle | None = None,
        cache_fingerprint: str | None = None,
    ) -> WalletSendResponse:
        self._update_spend_status_for_outcome(
            bundle,
            post_send_failure=True,
            idempotency_key=request.idempotency_key,
            reason=reason,
        )
        response = WalletSendResponse(
            status="error",
            spend_request_id=request.spend_request_id,
            amount_usd=request.amount_usd,
            reason=reason,
            rejection_reasons=[reason],
        )
        self._responses[request.idempotency_key] = response
        if cache_fingerprint is not None:
            self._response_fingerprints[request.idempotency_key] = cache_fingerprint
        return response

    def _update_spend_status_for_outcome(
        self,
        bundle: SpendAuthorizationBundle | None,
        *,
        post_send_failure: bool,
        idempotency_key: str,
        reason: str,
    ) -> None:
        if bundle is None:
            return
        current_status = bundle.spend_request.status
        if current_status in TERMINAL_SPEND_STATUSES:
            return
        next_status = (
            SpendRequestStatus.FAILED
            if post_send_failure or current_status is SpendRequestStatus.SENDING
            else SpendRequestStatus.REJECTED
        )
        self.ledger_service.update_spend_request_status(
            bundle.spend_request.spend_request_id,
            next_status.value,
            idempotency_key=f"wallet:spend-status:{next_status.value}:{idempotency_key}:{reason}",
        )

    def _limit_rejection_code(self, total_usd_estimate: float) -> str | None:
        if total_usd_estimate > self.policy_config.max_single_spend_usd:
            return "amount_exceeds_single_limit"
        today = utc_now().date().isoformat()
        daily_remaining = self.ledger_service.get_remaining_daily_limit(
            today,
            self.policy_config.max_daily_spend_usd,
        )
        weekly_remaining = self.ledger_service.get_remaining_weekly_limit(
            today,
            self.policy_config.max_weekly_spend_usd,
        )
        if total_usd_estimate > daily_remaining:
            return "amount_exceeds_daily_limit"
        if total_usd_estimate > weekly_remaining:
            return "amount_exceeds_weekly_limit"
        return None

    def _record_audit_event(
        self,
        event_name: str,
        related_record_id: str,
        payload: dict[str, JsonValue],
        *,
        idempotency_key: str,
    ) -> None:
        record = LedgerRecord(
            created_at=utc_now(),
            record_id=make_id("audit"),
            record_type=RecordType.AUDIT_EVENT,
            related_record_id=related_record_id,
            payload={"event_name": event_name, **payload},
        )
        self.ledger_service.record_ledger_record(record, idempotency_key=idempotency_key)

    @staticmethod
    def _request_summary(request: WalletSendRequest) -> dict[str, JsonValue]:
        return {
            "spend_request_id": request.spend_request_id,
            "opportunity_id": request.opportunity_id,
            "experiment_id": request.experiment_id,
            "budget_plan_id": request.budget_plan_id,
            "policy_decision_id": request.policy_decision_id,
            "ledger_record_id": request.ledger_record_id,
            "amount_usd": request.amount_usd,
            "asset": request.asset,
            "destination": request.destination,
            "counterparty": request.counterparty,
            "purpose": request.purpose,
            "category": request.category,
            "evidence_archive_ids": [item for item in request.evidence_archive_ids],
        }

    @staticmethod
    def _response_summary(response: WalletSendResponse) -> dict[str, JsonValue]:
        return {
            "status": response.status,
            "spend_request_id": response.spend_request_id,
            "wallet_transaction_id": response.wallet_transaction_id,
            "txid": response.txid,
            "amount_usd": response.amount_usd,
            "reason": response.reason,
            "rejection_reasons": [item for item in response.rejection_reasons],
            "warnings": [item for item in response.warnings],
        }

    def _require_supported_asset(self, asset: str) -> None:
        if asset not in self.config.allowed_assets:
            msg = f"Unsupported asset: {asset}"
            raise ValueError(msg)

    def _destination_error(
        self,
        asset: str,
        destination: str,
        purpose: str | None,
    ) -> str | None:
        normalized_destination = destination.strip().lower()
        if not normalized_destination:
            return "destination_missing"
        if any(token in normalized_destination for token in PLACEHOLDER_DESTINATIONS):
            return "destination_invalid"
        if any(term in normalized_destination for term in PROHIBITED_SEND_TERMS):
            return "send_all_blocked"
        if purpose is not None and any(term in purpose.lower() for term in PROHIBITED_SEND_TERMS):
            return "send_all_blocked"
        if not self._validate_destination(asset, destination):
            return "destination_invalid"
        return None

    @staticmethod
    def _validate_destination(asset: str, destination: str) -> bool:
        if asset == "BTC":
            return destination.startswith(BTC_ADDRESS_PREFIXES) and len(destination) >= 14
        return bool(destination.strip())

    @staticmethod
    def _usd_to_sats(amount_usd: float, btc_usd_rate: float) -> int:
        btc = Decimal(str(amount_usd)) / Decimal(str(btc_usd_rate))
        sats = btc * SATOSHIS_PER_BTC
        return int(sats.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    @staticmethod
    def _sats_to_usd(amount_sats: int, btc_usd_rate: float) -> float:
        btc_amount = Decimal(amount_sats) / SATOSHIS_PER_BTC
        usd_amount = btc_amount * Decimal(str(btc_usd_rate))
        return _round_usd(float(usd_amount))
