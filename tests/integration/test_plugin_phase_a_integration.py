"""Integration coverage for the PLUGINS1 Phase A wave."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from openclaw_moneybot.plugins.inbox_observer_plugin import (
    InboxMessageInput,
    InboxObservationRequest,
    InboxObserverPlugin,
)
from openclaw_moneybot.plugins.operator_profile_store import (
    OperatorProfileStore,
    OperatorProfileStoreWriteRequest,
)
from openclaw_moneybot.plugins.rules_snapshot_gateway import (
    RulesSnapshotCaptureRequest,
    RulesSnapshotGateway,
)
from openclaw_moneybot.plugins.wallet_governor_service.backend import (
    FakeWalletBackend,
    FakeWalletBackendState,
)
from openclaw_moneybot.plugins.wallet_observer_plugin import (
    WalletObserverPlugin,
    WalletTransactionObservationRequest,
)
from openclaw_moneybot.shared import (
    ArchiveConfig,
    InboxObserverConfig,
    OperatorProfileStoreConfig,
    RulesSnapshotGatewayConfig,
    WalletObserverConfig,
)
from openclaw_moneybot.shared.types import (
    CounterpartyRiskTier,
    PayoutFollowupRecommendation,
)
from openclaw_moneybot.skills.account_eligibility_checker import (
    AccountEligibilityChecker,
    AccountEligibilityRequest,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.payout_followup_planner import (
    PayoutFollowupPlanner,
    PayoutFollowupPlanRequest,
)
from openclaw_moneybot.skills.revenue_reconciler import (
    ReconciliationObservation,
    RevenueReconciler,
    RevenueReconciliationRequest,
)
from openclaw_moneybot.skills.terms_change_monitor import (
    TermsChangeMonitor,
    TermsChangeMonitorRequest,
)

from .helpers import (
    make_prewrite_record,
    seed_budget_plan,
    seed_opportunity,
    seed_policy_decision,
    seed_spend_request,
    seed_tos_legal_check,
    seed_wallet_transaction,
)


class RichFakeWalletBackend(FakeWalletBackend):
    def __init__(
        self,
        state: FakeWalletBackendState,
        *,
        transaction_payload: dict[str, object],
    ) -> None:
        super().__init__(state)
        self.transaction_payload = transaction_payload

    def get_transaction(self, txid: str) -> dict[str, object]:
        return {"txid": txid, **self.transaction_payload}


def test_operator_profile_store_can_feed_eligibility_checks(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    store = OperatorProfileStore(
        OperatorProfileStoreConfig(
            enabled=True,
            profile_path=tmp_path / "config" / "operator_profile.json",
        ),
        ledger_service,
    )
    store.upsert(
        OperatorProfileStoreWriteRequest(
            fields={"region": "united states", "supported_assets": ["btc"]},
            provenance={"region": "manual_config", "supported_assets": "manual_config"},
            idempotency_key="profile:eligibility",
        )
    )

    result = AccountEligibilityChecker(
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    ).evaluate(
        AccountEligibilityRequest(
            opportunity_id="opp_001",
            opportunity_name="Example",
            rules_text="US only. Bitcoin payout.",
            operator_profile=store.get_operator_profile(),
        )
    )

    assert result.decision.value == "eligible"


def test_rules_snapshot_gateway_can_feed_terms_change_monitor(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    gateway = RulesSnapshotGateway(
        RulesSnapshotGatewayConfig(enabled=True, allowed_hosts=["example.com"]),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    )
    first = gateway.capture(
        RulesSnapshotCaptureRequest(
            opportunity_id="opp_001",
            source_url="https://example.com/rules",
            content_text="Original payout is $25",
            content_type="text/plain",
            idempotency_key="rules:first",
        )
    )
    second = gateway.capture(
        RulesSnapshotCaptureRequest(
            opportunity_id="opp_001",
            source_url="https://example.com/rules",
            content_text="Updated payout is $10",
            content_type="text/plain",
            idempotency_key="rules:second",
        )
    )

    result = TermsChangeMonitor(
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    ).evaluate(
        TermsChangeMonitorRequest(
            opportunity_id="opp_001",
            prior_rules_text=str(first.ledger_record.payload["normalized_text"]),
            current_rules_text=str(second.ledger_record.payload["normalized_text"]),
            prior_evidence_archive_ids=first.evidence_archive_ids,
            current_evidence_archive_ids=second.evidence_archive_ids,
        )
    )

    assert result.change_detected is True
    assert result.requires_budget_recheck is True


def test_wallet_observer_can_feed_reconciliation(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    seed_opportunity(ledger_service)
    seed_policy_decision(ledger_service)
    seed_tos_legal_check(ledger_service)
    seed_budget_plan(ledger_service)
    ledger_event_id = make_prewrite_record(
        ledger_service,
        related_id="ledger_001",
    )
    spend_request = seed_spend_request(
        ledger_service,
        ledger_record_id=ledger_event_id,
    )
    wallet_transaction = seed_wallet_transaction(
        ledger_service,
        spend_request_id=spend_request.spend_request_id,
    )
    observer = WalletObserverPlugin(
        WalletObserverConfig(enabled=True),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        RichFakeWalletBackend(
            FakeWalletBackendState(balance_sats=2_000_000),
            transaction_payload={
                "confirmations": 1,
                "amount_sats": wallet_transaction.amount_sats,
                "fee_sats": wallet_transaction.fee_sats,
            },
        ),
    )
    observation = observer.observe_transaction(
        WalletTransactionObservationRequest(
            wallet_transaction_id=wallet_transaction.wallet_transaction_id,
            related_record_id=spend_request.opportunity_id or "wallet",
        )
    )

    reconciliation = RevenueReconciler(
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    ).reconcile(
        RevenueReconciliationRequest(
            opportunity_id=spend_request.opportunity_id or "opp_001",
            expected_amount=5.0,
            currency_or_asset="USD",
            current_date=datetime(2026, 1, 5, tzinfo=UTC),
            expected_date=datetime(2026, 1, 2, tzinfo=UTC),
            observations=[
                ReconciliationObservation(
                    observation_id="obs_wallet_001",
                    source_type="wallet_observer",
                    reference_id=observation.txid or "unknown",
                    amount=5.0,
                    currency_or_asset="USD",
                    observed_at=datetime(2026, 1, 5, tzinfo=UTC),
                )
            ],
        )
    )

    assert observation.found is True
    assert reconciliation.status.value == "matched"


def test_inbox_observer_can_feed_followup_planning(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    observer = InboxObserverPlugin(
        InboxObserverConfig(enabled=True, mailbox_address="bot@moneybot.local"),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    )
    observed = observer.observe(
        InboxObservationRequest(
            mailbox_address="bot@moneybot.local",
            messages=[
                InboxMessageInput(
                    message_id="msg_001",
                    thread_id="thread_001",
                    sender_email="payer@example.com",
                    subject="Payout sent",
                    body="Payment sent for opp_001",
                    received_at=datetime(2026, 1, 5, tzinfo=UTC),
                    known_reference_ids=["opp_001"],
                )
            ],
        )
    )

    followup = PayoutFollowupPlanner(
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    ).plan(
        PayoutFollowupPlanRequest(
            opportunity_id="opp_001",
            reconciliation_status="late",
            has_supporting_evidence=bool(observed.messages[0].evidence_archive_ids),
            counterparty_risk_tier=CounterpartyRiskTier.MEDIUM,
            days_since_expected=4,
        )
    )

    assert observed.messages[0].classification.value == "payout_notice"
    assert followup.recommendation is PayoutFollowupRecommendation.DRAFT_FOLLOWUP
