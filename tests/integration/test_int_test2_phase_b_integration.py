"""Integration coverage for the INT_TEST2 Phase B handoff paths."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from openclaw_moneybot.plugins.artifact_renderer_plugin import (
    ArtifactRendererPlugin,
    ArtifactRenderRequest,
)
from openclaw_moneybot.plugins.counterparty_snapshot_plugin import (
    CounterpartySnapshotPlugin,
    CounterpartySnapshotRequest,
)
from openclaw_moneybot.plugins.download_quarantine_plugin import (
    DownloadQuarantinePlugin,
    QuarantineIngestRequest,
    QuarantinePromoteRequest,
)
from openclaw_moneybot.plugins.inbox_observer_plugin import (
    InboxAttachment,
    InboxMessageInput,
    InboxObservationRequest,
    InboxObserverPlugin,
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
    ArtifactRendererConfig,
    CounterpartySnapshotConfig,
    DownloadQuarantineConfig,
    InboxObserverConfig,
    WalletObserverConfig,
)
from openclaw_moneybot.shared.types import (
    CounterpartyRiskTier,
    PayoutFollowupRecommendation,
    ReconciliationStatus,
    RecordType,
)
from openclaw_moneybot.skills.counterparty_risk_profiler import (
    CounterpartyRiskProfiler,
    CounterpartyRiskProfileRequest,
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
from openclaw_moneybot.skills.strategy_memory_summarizer import (
    StrategyMemorySummarizer,
    StrategyMemorySummaryRequest,
)

from .helpers import (
    make_archive_config,
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


def make_renderer(
    tmp_path: Path,
    archive_config: ArchiveConfig,
    ledger_service: LedgerService,
) -> ArtifactRendererPlugin:
    template_root = tmp_path / "templates"
    template_root.mkdir()
    (template_root / "submission.json").write_text(
        json.dumps(
            {
                "output_filename": "submission.txt",
                "required_fields": ["name"],
                "body_template": "Name: {name}\n",
            }
        ),
        encoding="utf-8",
    )
    return ArtifactRendererPlugin(
        ArtifactRendererConfig(
            enabled=True,
            template_root=template_root,
            render_root=tmp_path / "rendered",
        ),
        archive_config,
        ledger_service,
    )


def test_download_quarantine_promotion_preserves_hash_and_evidence_link(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = make_archive_config(tmp_path)
    quarantine = DownloadQuarantinePlugin(
        DownloadQuarantineConfig(
            enabled=True,
            quarantine_root=tmp_path / "quarantine",
            allowed_hosts=["example.com"],
        ),
        archive_config,
        ledger_service,
    )

    staged = quarantine.ingest(
        QuarantineIngestRequest(
            related_record_id="opp_001",
            file_name="proof.txt",
            content_bytes=b"proof",
            mime_type="text/plain",
            source_url="https://example.com/proof.txt",
        )
    )
    promoted = quarantine.promote(
        QuarantinePromoteRequest(
            scan_id=staged.scan_id,
            related_type=RecordType.OPPORTUNITY,
            related_id="opp_001",
            evidence_type="safe_download",
        )
    )
    metadata = json.loads(
        (quarantine.config.quarantine_root / staged.scan_id / "metadata.json").read_text(
            encoding="utf-8"
        )
    )
    evidence = ledger_service.get_evidence_record(promoted.promoted_evidence_id or "")

    assert staged.content_sha256 is not None
    assert metadata["status"] == "promoted"
    assert metadata["promoted_evidence_id"] == promoted.promoted_evidence_id
    assert evidence is not None
    assert evidence.content_sha256 == staged.content_sha256
    assert Path(evidence.archive_path).exists() is True


def test_inbox_attachment_can_be_promoted_and_reused_downstream(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = make_archive_config(tmp_path)
    inbox = InboxObserverPlugin(
        InboxObserverConfig(enabled=True, mailbox_address="bot@moneybot.local"),
        archive_config,
        ledger_service,
    )
    quarantine = DownloadQuarantinePlugin(
        DownloadQuarantineConfig(
            enabled=True,
            quarantine_root=tmp_path / "quarantine",
            allowed_hosts=["example.com"],
        ),
        archive_config,
        ledger_service,
    )
    renderer = make_renderer(tmp_path, archive_config, ledger_service)

    observed = inbox.observe(
        InboxObservationRequest(
            mailbox_address="bot@moneybot.local",
            messages=[
                InboxMessageInput(
                    message_id="msg_001",
                    thread_id="thread_001",
                    sender_email="sender@example.com",
                    subject="Submission proof",
                    body="See attached proof for opp_001",
                    received_at=datetime(2026, 1, 5, tzinfo=UTC),
                    known_reference_ids=["opp_001"],
                    attachments=[
                        InboxAttachment(
                            filename="proof.txt",
                            size_bytes=5,
                            mime_type="text/plain",
                        )
                    ],
                )
            ],
        )
    )
    staged = quarantine.ingest(
        QuarantineIngestRequest(
            related_record_id="opp_001",
            file_name="proof.txt",
            content_bytes=b"proof",
            mime_type="text/plain",
            source_url="https://example.com/proof.txt",
        )
    )
    promoted = quarantine.promote(
        QuarantinePromoteRequest(
            scan_id=staged.scan_id,
            related_type=RecordType.OPPORTUNITY,
            related_id="opp_001",
            evidence_type="safe_download",
        )
    )
    render = renderer.render(
        ArtifactRenderRequest(
            related_record_id="opp_001",
            template_name="submission",
            field_values={"name": "Maintainer"},
            evidence_archive_ids=[promoted.promoted_evidence_id or ""],
        )
    )

    assert observed.messages[0].attachment_actions["proof.txt"] == "metadata_only"
    assert promoted.promoted_evidence_id is not None
    assert render.rendered_paths[0].exists() is True
    assert render.evidence_archive_ids


def test_rejected_quarantine_items_cannot_be_promoted_or_used_downstream(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = make_archive_config(tmp_path)
    quarantine = DownloadQuarantinePlugin(
        DownloadQuarantineConfig(
            enabled=True,
            quarantine_root=tmp_path / "quarantine",
            allowed_hosts=["example.com"],
        ),
        archive_config,
        ledger_service,
    )
    renderer = make_renderer(tmp_path, archive_config, ledger_service)
    rejected = quarantine.ingest(
        QuarantineIngestRequest(
            related_record_id="opp_001",
            file_name="payload.exe",
            content_bytes=b"MZpayload",
            mime_type="application/octet-stream",
            source_url="https://example.com/payload.exe",
        )
    )

    with pytest.raises(ValueError, match="Unknown quarantine scan"):
        quarantine.promote(
            QuarantinePromoteRequest(
                scan_id=rejected.scan_id,
                related_type=RecordType.OPPORTUNITY,
                related_id="opp_001",
                evidence_type="safe_download",
            )
        )
    with pytest.raises(ValueError, match="Unknown evidence reference"):
        renderer.render(
            ArtifactRenderRequest(
                related_record_id="opp_001",
                template_name="submission",
                field_values={"name": "Maintainer"},
                evidence_archive_ids=[rejected.scan_id],
            )
        )

    assert rejected.reason == "extension_not_allowed"
    assert ledger_service.get_related_events(related_type=RecordType.RENDERED_ARTIFACT) == []


def test_wallet_observer_and_reconciliation_match_realistic_payout_history(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = make_archive_config(tmp_path)
    seed_opportunity(ledger_service)
    seed_policy_decision(ledger_service)
    seed_tos_legal_check(ledger_service)
    seed_budget_plan(ledger_service)
    ledger_event_id = make_prewrite_record(ledger_service, related_id="ledger_001")
    spend_request = seed_spend_request(
        ledger_service,
        ledger_record_id=ledger_event_id,
        amount_usd=5.0,
    )
    wallet_transaction = seed_wallet_transaction(
        ledger_service,
        spend_request_id=spend_request.spend_request_id,
        amount_usd_estimate=5.0,
    )
    observer = WalletObserverPlugin(
        WalletObserverConfig(enabled=True),
        archive_config,
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
            related_record_id=spend_request.opportunity_id or "opp_001",
        )
    )
    reconciliation = RevenueReconciler(archive_config, ledger_service).reconcile(
        RevenueReconciliationRequest(
            opportunity_id=spend_request.opportunity_id or "opp_001",
            expected_amount=5.0,
            currency_or_asset="USD",
            current_date=datetime(2026, 1, 5, tzinfo=UTC),
            expected_date=datetime(2026, 1, 2, tzinfo=UTC),
            observations=[
                ReconciliationObservation(
                    observation_id=observation.observation_id,
                    source_type="wallet_observer",
                    reference_id=observation.txid or "unknown",
                    amount=5.0,
                    currency_or_asset="USD",
                    observed_at=datetime(2026, 1, 5, tzinfo=UTC),
                    counterparty="Example Vendor",
                    evidence_archive_id=observation.evidence_archive_ids[0],
                )
            ],
        )
    )

    assert observation.found is True
    assert observation.mismatch_fields == []
    assert reconciliation.status is ReconciliationStatus.MATCHED
    assert reconciliation.observed_amount == 5.0
    assert reconciliation.variance == 0.0
    assert reconciliation.matched_artifacts == observation.evidence_archive_ids


def test_missing_and_partial_payouts_drive_followup_plans_with_traceable_linkage(
    tmp_path: Path,
) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = make_archive_config(tmp_path)
    seed_opportunity(ledger_service)
    missing = RevenueReconciler(archive_config, ledger_service).reconcile(
        RevenueReconciliationRequest(
            opportunity_id="opp_001",
            expected_amount=25.0,
            currency_or_asset="USD",
            current_date=datetime(2026, 1, 5, tzinfo=UTC),
            expected_date=datetime(2026, 1, 2, tzinfo=UTC),
            observations=[],
        )
    )
    missing_followup = PayoutFollowupPlanner(archive_config, ledger_service).plan(
        PayoutFollowupPlanRequest(
            opportunity_id="opp_001",
            reconciliation_status=missing.status,
            has_supporting_evidence=False,
            counterparty_risk_tier=CounterpartyRiskTier.MEDIUM,
            days_since_expected=3,
            evidence_archive_ids=missing.evidence_archive_ids,
        )
    )
    partial = RevenueReconciler(archive_config, ledger_service).reconcile(
        RevenueReconciliationRequest(
            opportunity_id="opp_001",
            expected_amount=25.0,
            currency_or_asset="USD",
            current_date=datetime(2026, 1, 6, tzinfo=UTC),
            expected_date=datetime(2026, 1, 2, tzinfo=UTC),
            observations=[
                ReconciliationObservation(
                    observation_id="obs_001",
                    source_type="receipt",
                    reference_id="receipt_001",
                    amount=10.0,
                    currency_or_asset="USD",
                    observed_at=datetime(2026, 1, 6, tzinfo=UTC),
                    evidence_archive_id="artifact_001",
                )
            ],
        )
    )
    partial_followup = PayoutFollowupPlanner(archive_config, ledger_service).plan(
        PayoutFollowupPlanRequest(
            opportunity_id="opp_001",
            reconciliation_status=partial.status,
            has_supporting_evidence=True,
            counterparty_risk_tier=CounterpartyRiskTier.MEDIUM,
            days_since_expected=4,
            evidence_archive_ids=partial.evidence_archive_ids,
        )
    )

    assert missing.status is ReconciliationStatus.LATE
    assert missing_followup.recommendation is PayoutFollowupRecommendation.GATHER_MISSING_PROOF
    assert partial.status is ReconciliationStatus.UNDERPAID
    assert partial_followup.recommendation is PayoutFollowupRecommendation.DRAFT_FOLLOWUP
    assert partial_followup.evidence_archive_ids[0] == partial.evidence_archive_ids[0]


def test_counterparty_snapshot_risk_and_downstream_strategy_planning_are_traceable(
    tmp_path: Path,
) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = make_archive_config(tmp_path)
    seed_opportunity(ledger_service)
    snapshot_plugin = CounterpartySnapshotPlugin(
        CounterpartySnapshotConfig(enabled=True, allowed_hosts=["example.com"]),
        archive_config,
        ledger_service,
    )
    low_snapshot = snapshot_plugin.capture(
        CounterpartySnapshotRequest(
            opportunity_id="opp_001",
            counterparty_name="Example Vendor",
            source_url="https://example.com/public/profile",
            source_category="public_profile",
            content_type="text/plain",
            content_text=(
                "display_name: Example Vendor\n"
                "support_email: support@example.com\n"
                "payment_proof_present: yes\n"
                "payout_terms_present: yes\n"
                "support_responsive: yes\n"
                "domain_age_days: 365\n"
            ),
            captured_at=datetime(2026, 1, 1, tzinfo=UTC),
            current_time=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )
    high_snapshot = snapshot_plugin.capture(
        CounterpartySnapshotRequest(
            opportunity_id="opp_001",
            counterparty_name="Example Vendor",
            source_url="https://example.com/public/profile",
            source_category="public_profile",
            content_type="text/plain",
            content_text=(
                "display_name: Example Vendor\n"
                "payment_proof_present: no\n"
                "payout_terms_present: no\n"
                "support_responsive: no\n"
                "domain_age_days: 10\n"
            ),
            captured_at=datetime(2026, 1, 3, tzinfo=UTC),
            current_time=datetime(2026, 2, 10, tzinfo=UTC),
        )
    )
    low_risk = CounterpartyRiskProfiler(archive_config, ledger_service).profile(
        CounterpartyRiskProfileRequest(
            opportunity_id="opp_001",
            counterparty_name="Example Vendor",
            platform_domain="example.com",
            payout_history_success_rate=1.0,
            support_responsive=True,
            clear_payout_rules=True,
            clear_deadlines=True,
            suspicious_claims_present=False,
            off_platform_payment_required=False,
            unexpected_kyc_required=False,
            domain_age_days=365,
            evidence_archive_ids=low_snapshot.evidence_archive_ids,
        )
    )
    high_risk = CounterpartyRiskProfiler(archive_config, ledger_service).profile(
        CounterpartyRiskProfileRequest(
            opportunity_id="opp_001",
            counterparty_name="Example Vendor",
            platform_domain="example.com",
            payout_history_success_rate=0.0,
            support_responsive=False,
            clear_payout_rules=False,
            clear_deadlines=False,
            suspicious_claims_present=True,
            off_platform_payment_required=True,
            unexpected_kyc_required=True,
            domain_age_days=10,
            evidence_archive_ids=high_snapshot.evidence_archive_ids,
        )
    )
    followup = PayoutFollowupPlanner(archive_config, ledger_service).plan(
        PayoutFollowupPlanRequest(
            opportunity_id="opp_001",
            reconciliation_status="late",
            has_supporting_evidence=True,
            counterparty_risk_tier=high_risk.risk_tier,
            days_since_expected=5,
            evidence_archive_ids=high_risk.evidence_archive_ids,
        )
    )
    strategy_summary = StrategyMemorySummarizer(archive_config, ledger_service).summarize(
        StrategyMemorySummaryRequest(
            opportunity_id="opp_001",
            experiment_review_id="review_001",
            scope="opportunity",
            net_usd=-5.0,
            roi_percent=-100.0,
            time_spent_hours=1.0,
            reconciliation_status=ReconciliationStatus.LATE,
            counterparty_risk_tier=high_risk.risk_tier,
            evidence_archive_ids=high_risk.evidence_archive_ids,
        )
    )

    assert low_snapshot.evidence_archive_ids
    assert low_risk.risk_tier is CounterpartyRiskTier.LOW
    assert high_snapshot.previous_snapshot_id == low_snapshot.snapshot_id
    assert "payment_proof_present" in high_snapshot.changed_fields
    assert high_snapshot.evidence_tier.value == "weak"
    assert high_snapshot.freshness.value == "stale"
    assert high_risk.risk_tier is CounterpartyRiskTier.HIGH
    assert followup.recommendation is PayoutFollowupRecommendation.HUMAN_REVIEW
    assert strategy_summary.ledger_record.related_record_id == "opp_001"
    assert "Escalate high-risk counterparties before committing work." in (
        strategy_summary.heuristics_to_avoid
    )
