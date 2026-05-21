"""Read-only wallet observation helpers."""

from __future__ import annotations

from openclaw_moneybot.plugins.support import (
    PluginHealthResult,
    record_plugin_audit_event,
)
from openclaw_moneybot.plugins.wallet_governor_service.backend import (
    WalletBackend,
    WalletBackendError,
)
from openclaw_moneybot.plugins.wallet_observer_plugin.models import (
    WalletBalanceObservationRequest,
    WalletBalanceObservationResult,
    WalletTransactionObservationRequest,
    WalletTransactionObservationResult,
)
from openclaw_moneybot.shared import ArchiveConfig, WalletObserverConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id


class WalletObserverPlugin:
    """Inspect wallet balance and tracked transactions without spend authority."""

    def __init__(
        self,
        config: WalletObserverConfig,
        archive_config: ArchiveConfig,
        ledger_service: LedgerService,
        backend: WalletBackend,
    ) -> None:
        if not config.read_only:
            msg = "wallet observer must remain read_only."
            raise ValueError(msg)
        self.config = config
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)
        self.ledger_service = ledger_service
        self.backend = backend

    def health(self) -> PluginHealthResult:
        """Return local plugin health metadata."""

        return PluginHealthResult(
            plugin_name="wallet_observer_plugin",
            enabled=self.config.enabled,
            read_only=True,
        )

    def observe_balance(
        self,
        request: WalletBalanceObservationRequest,
    ) -> WalletBalanceObservationResult:
        """Capture a read-only wallet balance snapshot."""

        self._require_supported_asset(request.asset)
        observation_id = make_id("wallet_observation")
        try:
            balance_sats = self.backend.get_balance_sats()
        except WalletBackendError as error:
            record_plugin_audit_event(
                self.ledger_service,
                related_record_id=request.related_record_id,
                event_name="wallet_balance_observation_failed",
                payload={"reason": str(error)},
            )
            raise
        balance_btc = self._btc_from_sats(balance_sats)
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.WALLET_OBSERVATION,
            related_id=observation_id,
            evidence_type="wallet_balance_snapshot",
            payload={
                "asset": request.asset,
                "balance_sats": balance_sats,
                "balance_btc": balance_btc,
            },
            notes="Read-only wallet balance observation",
        )
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=observation_id,
            record_type=RecordType.WALLET_OBSERVATION,
            related_record_id=request.related_record_id,
            payload={
                "kind": "balance",
                "asset": request.asset,
                "balance_sats": balance_sats,
                "balance_btc": balance_btc,
                "evidence_archive_ids": [evidence_id],
            },
        )
        return WalletBalanceObservationResult(
            observation_id=observation_id,
            asset=request.asset,
            balance_sats=balance_sats,
            balance_btc=balance_btc,
            evidence_archive_ids=[evidence_id],
            ledger_record=ledger_record,
        )

    def observe_transaction(
        self,
        request: WalletTransactionObservationRequest,
    ) -> WalletTransactionObservationResult:
        """Observe a tracked transaction without mutating wallet state."""

        observation_id = make_id("wallet_observation")
        txid = request.txid
        if txid is None and request.wallet_transaction_id is not None:
            existing = self.ledger_service.get_wallet_transaction(request.wallet_transaction_id)
            txid = None if existing is None else existing.txid
            if request.expected_amount_sats is None and existing is not None:
                request.expected_amount_sats = existing.amount_sats
            if request.expected_fee_sats is None and existing is not None:
                request.expected_fee_sats = existing.fee_sats
        if txid is None:
            ledger_record = record_structured_result(
                self.ledger_service,
                record_id=observation_id,
                record_type=RecordType.WALLET_OBSERVATION,
                related_record_id=request.related_record_id,
                payload={"kind": "transaction", "found": False, "reason": "txid_missing"},
            )
            return WalletTransactionObservationResult(
                observation_id=observation_id,
                found=False,
                confirmation_status="missing",
                ledger_record=ledger_record,
                reason="txid_missing",
            )
        try:
            transaction = self.backend.get_transaction(txid)
        except WalletBackendError as error:
            record_plugin_audit_event(
                self.ledger_service,
                related_record_id=request.related_record_id,
                event_name="wallet_transaction_observation_failed",
                payload={"txid": txid, "reason": str(error)},
            )
            ledger_record = record_structured_result(
                self.ledger_service,
                record_id=observation_id,
                record_type=RecordType.WALLET_OBSERVATION,
                related_record_id=request.related_record_id,
                payload={
                    "kind": "transaction",
                    "found": False,
                    "txid": txid,
                    "reason": "observation_failed",
                },
            )
            return WalletTransactionObservationResult(
                observation_id=observation_id,
                found=False,
                txid=txid,
                confirmation_status="unknown",
                ledger_record=ledger_record,
                reason="observation_failed",
            )

        confirmations = self._int_or_none(transaction.get("confirmations"))
        observed_amount_sats = self._int_or_none(transaction.get("amount_sats"))
        observed_fee_sats = self._int_or_none(transaction.get("fee_sats"))
        mismatch_fields: list[str] = []
        if (
            request.expected_amount_sats is not None
            and observed_amount_sats is not None
            and request.expected_amount_sats != observed_amount_sats
        ):
            mismatch_fields.append("amount_sats")
        if (
            request.expected_fee_sats is not None
            and observed_fee_sats is not None
            and request.expected_fee_sats != observed_fee_sats
        ):
            mismatch_fields.append("fee_sats")
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.WALLET_OBSERVATION,
            related_id=observation_id,
            evidence_type="wallet_transaction_snapshot",
            payload={
                "txid": txid,
                "confirmations": confirmations,
                "observed_amount_sats": observed_amount_sats,
                "observed_fee_sats": observed_fee_sats,
                "mismatch_fields": mismatch_fields,
            },
            notes="Read-only wallet transaction observation",
        )
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=observation_id,
            record_type=RecordType.WALLET_OBSERVATION,
            related_record_id=request.related_record_id,
            payload={
                "kind": "transaction",
                "found": True,
                "txid": txid,
                "confirmation_status": self._confirmation_status(confirmations),
                "confirmations": confirmations,
                "observed_amount_sats": observed_amount_sats,
                "observed_fee_sats": observed_fee_sats,
                "mismatch_fields": mismatch_fields,
                "evidence_archive_ids": [evidence_id],
            },
        )
        return WalletTransactionObservationResult(
            observation_id=observation_id,
            found=True,
            txid=txid,
            confirmation_status=self._confirmation_status(confirmations),
            confirmations=confirmations,
            observed_amount_sats=observed_amount_sats,
            observed_fee_sats=observed_fee_sats,
            mismatch_fields=mismatch_fields,
            evidence_archive_ids=[evidence_id],
            ledger_record=ledger_record,
        )

    def _require_supported_asset(self, asset: str) -> None:
        if asset not in self.config.allowed_assets:
            msg = f"Unsupported asset for wallet observation: {asset}"
            raise ValueError(msg)

    @staticmethod
    def _confirmation_status(confirmations: int | None) -> str:
        if confirmations is None:
            return "unknown"
        if confirmations > 0:
            return "confirmed"
        return "pending"

    @staticmethod
    def _btc_from_sats(amount_sats: int) -> str:
        whole = amount_sats / 100_000_000
        return f"{whole:.8f}"

    @staticmethod
    def _int_or_none(value: object) -> int | None:
        return value if isinstance(value, int) else None
