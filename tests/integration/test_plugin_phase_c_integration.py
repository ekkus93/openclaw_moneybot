"""Integration coverage for the PLUGINS1 Phase C wave."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import httpx
import pytest

from openclaw_moneybot.plugins.brave_search_plugin import (
    BraveNewsSearchRequest,
    BraveSearchPlugin,
    BraveSearchPluginError,
    BraveSearchRequest,
)
from openclaw_moneybot.plugins.counterparty_snapshot_plugin import (
    CounterpartySnapshotPlugin,
    CounterpartySnapshotRequest,
)
from openclaw_moneybot.plugins.crypto_market_data_plugin import (
    CryptoMarketChartRequest,
    CryptoMarketDataPlugin,
    CryptoMarketDataPluginError,
    CryptoSpotPriceRequest,
)
from openclaw_moneybot.plugins.mastodon_discovery_plugin import (
    MastodonDiscoveryPlugin,
    MastodonDiscoveryPluginError,
    MastodonPublicTimelineRequest,
)
from openclaw_moneybot.plugins.metrics_export_plugin import (
    MetricsExportPlugin,
    MetricsExportRequest,
)
from openclaw_moneybot.shared import (
    ArchiveConfig,
    BraveSearchConfig,
    BudgetPlan,
    CounterpartySnapshotConfig,
    CryptoMarketDataConfig,
    MastodonDiscoveryConfig,
    MetricsExportConfig,
    Opportunity,
    PolicyDecision,
    TosLegalCheck,
)
from openclaw_moneybot.shared.types import (
    ActionType,
    BudgetDecisionType,
    ConfidenceLevel,
    CounterpartyRiskTier,
    PolicyDecisionType,
    ReconciliationStatus,
    RecordType,
    RiskLevel,
    TosDecisionType,
)
from openclaw_moneybot.skills.counterparty_risk_profiler import (
    CounterpartyRiskProfiler,
    CounterpartyRiskProfileRequest,
)
from openclaw_moneybot.skills.experiment_reviewer import (
    ExperimentReviewer,
    ExperimentReviewRequest,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.revenue_reconciler import (
    ReconciliationObservation,
    RevenueReconciler,
    RevenueReconciliationRequest,
)
from openclaw_moneybot.skills.strategy_memory_summarizer import (
    StrategyMemorySummarizer,
    StrategyMemorySummaryRequest,
)


def seed_opportunity(ledger_service: LedgerService) -> None:
    ledger_service.create_opportunity(
        Opportunity(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            opportunity_id="opp_001",
            name="Integration opportunity",
            category="bounty",
            status="approved",
            source_url="https://example.com/opportunity",
            rules_url="https://example.com/rules",
            required_spend_usd=5,
            estimated_revenue_usd=25,
            max_loss_usd=5,
            legal_risk_precheck=RiskLevel.LOW,
            tos_risk_precheck=RiskLevel.LOW,
        ),
        idempotency_key="opportunity:opp_001",
    )


def seed_policy_decision(ledger_service: LedgerService) -> None:
    ledger_service.record_policy_decision(
        PolicyDecision(
            created_at=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
            policy_decision_id="policy_001",
            opportunity_id="opp_001",
            action_type=ActionType.SPEND,
            category="purchase",
            requires_payment=True,
            requires_wallet_action=True,
            amount_usd=5,
            counterparty="Example Vendor",
            planned_tools=["wallet_governor_client"],
            sanitized_input={"action_type": "spend"},
            decision=PolicyDecisionType.ALLOW,
            risk_level=RiskLevel.LOW,
            confidence=ConfidenceLevel.HIGH,
            policy_version="v1",
            request_fingerprint="fingerprint",
        ),
        idempotency_key="policy:policy_001",
    )


def seed_tos_legal_check(ledger_service: LedgerService) -> None:
    ledger_service.record_tos_legal_check(
        TosLegalCheck(
            created_at=datetime(2026, 1, 1, 0, 2, tzinfo=UTC),
            tos_legal_check_id="tos_001",
            opportunity_id="opp_001",
            decision=TosDecisionType.PROCEED,
            confidence=ConfidenceLevel.HIGH,
            platform_terms_summary="Proceed.",
            legal_risk_summary="Low.",
            tos_risk_summary="Low.",
            evidence_archive_ids=["artifact_001"],
        ),
        idempotency_key="tos:tos_001",
    )


def seed_budget_plan(ledger_service: LedgerService) -> None:
    ledger_service.record_budget_plan(
        BudgetPlan(
            created_at=datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
            budget_plan_id="budget_001",
            opportunity_id="opp_001",
            policy_decision_id="policy_001",
            tos_legal_check_id="tos_001",
            decision=BudgetDecisionType.EXECUTE_REQUEST,
            recommended_budget_usd=5,
            max_loss_usd=5,
            expected_gross_revenue_usd=25,
            expected_net_revenue_usd=20,
            break_even_condition="One payout",
            success_metric="Paid",
            stop_condition="Stop after one try",
            required_records=["budget_snapshot"],
            risk_level=RiskLevel.LOW,
            wallet_spend_request_allowed=True,
            approved_spend_categories=["purchase"],
            reasons=["Within limits."],
        ),
        idempotency_key="budget:budget_001",
    )


def test_counterparty_snapshot_can_feed_risk_profiling(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = ArchiveConfig(base_directory=tmp_path / "archive")
    seed_opportunity(ledger_service)
    snapshot_plugin = CounterpartySnapshotPlugin(
        CounterpartySnapshotConfig(
            enabled=True,
            allowed_hosts=["example.com"],
        ),
        archive_config,
        ledger_service,
    )
    risk_profiler = CounterpartyRiskProfiler(archive_config, ledger_service)
    snapshot = snapshot_plugin.capture(
        CounterpartySnapshotRequest(
            opportunity_id="opp_001",
            counterparty_name="Example Vendor",
            source_url="https://example.com/public/profile",
            source_category="public_profile",
            content_type="text/plain",
            content_text=(
                "display_name: Example Vendor\n"
                "support_email: support@example.com\n"
                "payout_terms_present: yes\n"
                "payment_proof_present: yes\n"
                "support_responsive: yes\n"
                "domain_age_days: 365\n"
            ),
            captured_at=datetime(2026, 1, 1, tzinfo=UTC),
            current_time=datetime(2026, 1, 2, tzinfo=UTC),
        )
    )
    domain_age_days = snapshot.indicators["domain_age_days"]
    assert isinstance(domain_age_days, int)
    result = risk_profiler.profile(
        CounterpartyRiskProfileRequest(
            opportunity_id="opp_001",
            counterparty_name="Example Vendor",
            platform_domain=str(snapshot.indicators["platform_domain"]),
            payout_history_success_rate=(
                1.0 if snapshot.indicators["payment_proof_present"] else 0.4
            ),
            support_responsive=bool(snapshot.indicators["support_responsive"]),
            clear_payout_rules=bool(snapshot.indicators["payout_terms_present"]),
            clear_deadlines=True,
            suspicious_claims_present=False,
            off_platform_payment_required=False,
            unexpected_kyc_required=False,
            domain_age_days=domain_age_days,
            evidence_archive_ids=snapshot.evidence_archive_ids,
        )
    )

    assert snapshot.evidence_archive_ids
    assert result.risk_tier is CounterpartyRiskTier.LOW


def test_metrics_export_can_summarize_review_and_strategy_outputs(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = ArchiveConfig(base_directory=tmp_path / "archive")
    seed_opportunity(ledger_service)
    seed_policy_decision(ledger_service)
    seed_tos_legal_check(ledger_service)
    seed_budget_plan(ledger_service)
    review = ExperimentReviewer(archive_config, ledger_service).review(
        ExperimentReviewRequest(
            opportunity_id="opp_001",
            budget_plan_id="budget_001",
            review_reason="Completed work",
            current_date=datetime(2026, 1, 3, tzinfo=UTC),
            revenue_usd=20,
            fees_usd=1,
            time_spent_hours=2,
            success_metric_met=True,
            evidence_archive_ids=["artifact_001"],
        )
    )
    reconciliation = RevenueReconciler(archive_config, ledger_service).reconcile(
        RevenueReconciliationRequest(
            opportunity_id="opp_001",
            expected_amount=20,
            currency_or_asset="USD",
            current_date=datetime(2026, 1, 3, tzinfo=UTC),
            observations=[
                ReconciliationObservation(
                    observation_id="obs_001",
                    amount=20,
                    currency_or_asset="USD",
                    observed_at=datetime(2026, 1, 3, tzinfo=UTC),
                    counterparty="Example Vendor",
                    source_type="receipt",
                )
            ],
        )
    )
    StrategyMemorySummarizer(archive_config, ledger_service).summarize(
        StrategyMemorySummaryRequest(
            opportunity_id="opp_001",
            experiment_review_id=review.experiment_review_id,
            scope="global",
            net_usd=review.net_usd,
            roi_percent=review.roi_percent,
            time_spent_hours=review.time_spent_hours,
            reconciliation_status=ReconciliationStatus.MATCHED,
            counterparty_risk_tier=CounterpartyRiskTier.LOW,
            evidence_archive_ids=reconciliation.evidence_archive_ids,
        )
    )
    exporter = MetricsExportPlugin(
        MetricsExportConfig(enabled=True, export_root=tmp_path / "exports"),
        archive_config,
        ledger_service,
    )

    result = exporter.export(
        MetricsExportRequest(
            export_type="strategy_summaries",
            output_format="json",
            opportunity_category="bounty",
        )
    )
    rows = json.loads(result.output_path.read_text(encoding="utf-8"))

    assert rows[0]["scope"] == "global"
    assert result.summary["row_count"] == 1


def test_brave_web_search_archives_request_response_and_ledger_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "token")
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = ArchiveConfig(base_directory=tmp_path / "archive")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "python jobs"
        return httpx.Response(
            200,
            json={
                "web": {
                    "total": 1,
                    "results": [
                        {
                            "title": "Result One",
                            "url": "https://example.com/one",
                            "description": "First result",
                        }
                    ],
                }
            },
        )

    plugin = BraveSearchPlugin(
        BraveSearchConfig(enabled=True, max_results=5, max_news_results=5),
        archive_config,
        ledger_service,
        transport=httpx.MockTransport(handler),
    )

    result = plugin.search(BraveSearchRequest(query="python jobs", count=1))
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.WEB_SEARCH,
        related_id=result.search_id,
    )
    archived = json.loads(Path(evidence[0].archive_path).read_text(encoding="utf-8"))

    assert result.ledger_record.payload["mode"] == "web"
    assert result.ledger_record.payload["result_count"] == 1
    assert archived["request"]["query"] == "python jobs"
    assert archived["response"]["web"]["results"][0]["title"] == "Result One"


def test_brave_news_search_preserves_mode_freshness_and_source_domains(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "token")
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = ArchiveConfig(base_directory=tmp_path / "archive")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["freshness"] == "pd"
        return httpx.Response(
            200,
            json={
                "web": {
                    "total": 1,
                    "results": [
                        {
                            "title": "ETF headline",
                            "url": "https://www.reuters.com/example",
                            "description": "News result",
                        }
                    ],
                }
            },
        )

    plugin = BraveSearchPlugin(
        BraveSearchConfig(enabled=True, max_results=5, max_news_results=5),
        archive_config,
        ledger_service,
        transport=httpx.MockTransport(handler),
    )

    result = plugin.search_news(
        BraveNewsSearchRequest(
            query="bitcoin etf",
            count=1,
            source_domains=["Reuters.com", "apnews.com"],
        )
    )

    assert result.mode == "news"
    assert result.freshness == "pd"
    assert result.source_domains == ["reuters.com", "apnews.com"]
    assert result.ledger_record.payload["source_domains"] == ["reuters.com", "apnews.com"]


def test_brave_invalid_response_records_failure_audit_without_success_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "token")
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = BraveSearchPlugin(
        BraveSearchConfig(enabled=True, max_results=5, max_news_results=5),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(429, json={"error": "rate limited"})
        ),
    )

    with pytest.raises(BraveSearchPluginError, match="request failed"):
        plugin.search(BraveSearchRequest(query="python jobs", count=1))

    evidence = ledger_service.get_related_events(related_type=RecordType.WEB_SEARCH)
    audit_events = ledger_service.get_related_events(
        related_type=RecordType.AUDIT_EVENT,
        event_type="record_audit_event",
    )
    audits: list[dict[str, object]] = []
    for event in audit_events:
        nested_payload = event.payload.get("payload")
        if event.payload.get("related_record_id") is None or not isinstance(
            nested_payload, dict
        ):
            continue
        audit_payload = cast(dict[str, object], nested_payload)
        if audit_payload.get("event_name") == "brave_web_search_failed":
            audits.append(audit_payload)
    assert evidence == []
    assert len(audits) == 1
    assert audits[0]["reason"] == "invalid_response"


def test_mastodon_timeline_sampling_records_normalized_result_and_archive(
    tmp_path: Path,
) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = MastodonDiscoveryPlugin(
        MastodonDiscoveryConfig(
            enabled=True,
            require_auth=False,
            max_results=10,
            api_base_url="https://mastodon.social",
        ),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=[
                    {
                        "id": "100",
                        "url": "https://mastodon.social/@alice/100",
                        "created_at": "2026-05-21T21:00:00Z",
                        "content": "<p>Hello <a href=\"https://example.com/news\">news</a> #AI</p>",
                        "visibility": "public",
                        "language": "en",
                        "replies_count": 1,
                        "reblogs_count": 2,
                        "favourites_count": 3,
                        "media_attachments": [],
                        "sensitive": False,
                        "account": {"acct": "alice", "display_name": "Alice Example"},
                        "tags": [{"name": "AI"}],
                    }
                ],
            )
        ),
    )

    result = plugin.sample_public_timeline(MastodonPublicTimelineRequest(limit=1, local=True))
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.MASTODON_DISCOVERY,
        related_id=result.sample_id,
    )
    archived = json.loads(Path(evidence[0].archive_path).read_text(encoding="utf-8"))

    assert result.statuses[0].author_handle == "alice"
    assert result.statuses[0].tags == ["ai"]
    assert str(result.statuses[0].links[0]) == "https://mastodon.social/@alice/100"
    assert archived["response"][0]["id"] == "100"
    assert result.ledger_record.payload["status_ids"] == ["100"]


def test_mastodon_failure_audit_does_not_write_success_records(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    plugin = MastodonDiscoveryPlugin(
        MastodonDiscoveryConfig(
            enabled=True,
            require_auth=False,
            max_results=10,
            api_base_url="https://mastodon.social",
        ),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(MastodonDiscoveryPluginError, match="unavailable"):
        plugin.sample_public_timeline(MastodonPublicTimelineRequest(limit=1))

    assert ledger_service.get_related_events(related_type=RecordType.MASTODON_DISCOVERY) == []
    audit_events = ledger_service.get_related_events(
        related_type=RecordType.AUDIT_EVENT,
        event_type="record_audit_event",
    )
    audits: list[dict[str, object]] = []
    for event in audit_events:
        nested_payload = event.payload.get("payload")
        if not isinstance(nested_payload, dict):
            continue
        audit_payload = cast(dict[str, object], nested_payload)
        if audit_payload.get("event_name") == "mastodon_public_timeline_failed":
            audits.append(audit_payload)
    assert len(audits) == 1
    assert audits[0]["reason"] == "transport_error"


def test_crypto_spot_price_lookup_records_exact_evidence_and_record_types(
    tmp_path: Path,
) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = CryptoMarketDataPlugin(
        CryptoMarketDataConfig(enabled=True, max_chart_points=10),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "bitcoin": {
                        "usd": 70000.5,
                        "usd_market_cap": 1380000000000.0,
                        "usd_24h_vol": 25000000000.0,
                        "usd_24h_change": 2.5,
                        "last_updated_at": 1711983682,
                    }
                },
            )
        ),
    )

    result = plugin.get_spot_price(CryptoSpotPriceRequest(asset_id="Bitcoin"))
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.CRYPTO_MARKET_DATA,
        related_id=result.lookup_id,
    )

    assert result.price == 70000.5
    assert result.ledger_record.record_type is RecordType.CRYPTO_MARKET_DATA
    assert evidence[0].evidence_type == "coingecko_spot_price_response"
    assert ledger_service.get_related_events(related_type=RecordType.SPEND_REQUEST) == []


def test_crypto_market_chart_lookup_records_bounded_points_and_archive(
    tmp_path: Path,
) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = CryptoMarketDataPlugin(
        CryptoMarketDataConfig(enabled=True, max_chart_points=10),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "prices": [
                        [1711843200000, 69702.3],
                        [1711929600000, 71246.9],
                        [1711983682000, 68887.7],
                    ],
                    "market_caps": [
                        [1711843200000, 1370247487960.09],
                        [1711929600000, 1401370211582.37],
                        [1711983682000, 1355701979725.16],
                    ],
                    "total_volumes": [
                        [1711843200000, 16408802301.83],
                        [1711929600000, 19723005998.21],
                        [1711983682000, 30137418199.64],
                    ],
                },
            )
        ),
    )

    result = plugin.get_recent_market_chart(
        CryptoMarketChartRequest(asset_id="bitcoin", days=7, count=2)
    )
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.CRYPTO_MARKET_DATA,
        related_id=result.lookup_id,
    )

    assert result.result_count == 2
    assert result.points[0].timestamp_ms == 1711929600000
    assert evidence[0].evidence_type == "coingecko_market_chart_response"


def test_crypto_provider_error_fails_closed_with_audit_visibility(tmp_path: Path) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = CryptoMarketDataPlugin(
        CryptoMarketDataConfig(enabled=True, max_chart_points=10),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"status": {"error_message": "rate limit exceeded"}},
            )
        ),
    )

    with pytest.raises(CryptoMarketDataPluginError, match="rate limit exceeded"):
        plugin.get_recent_market_chart(
            CryptoMarketChartRequest(asset_id="bitcoin", days=7, count=2)
        )

    assert ledger_service.get_related_events(related_type=RecordType.CRYPTO_MARKET_DATA) == []
    audit_events = ledger_service.get_related_events(
        related_type=RecordType.AUDIT_EVENT,
        event_type="record_audit_event",
    )
    audits: list[dict[str, object]] = []
    for event in audit_events:
        nested_payload = event.payload.get("payload")
        if not isinstance(nested_payload, dict):
            continue
        audit_payload = cast(dict[str, object], nested_payload)
        if audit_payload.get("event_name") == "crypto_market_chart_failed":
            audits.append(audit_payload)
    assert len(audits) == 1
    assert audits[0]["reason"] == "provider_error"
    assert audits[0]["provider_error"] == "rate limit exceeded"


def test_hosted_plugins_remain_fail_closed_when_disabled_or_misconfigured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = ArchiveConfig(base_directory=tmp_path / "archive")
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("MASTODON_API_TOKEN", raising=False)

    brave = BraveSearchPlugin(
        BraveSearchConfig(enabled=False, max_results=5, max_news_results=5),
        archive_config,
        ledger_service,
    )
    mastodon = MastodonDiscoveryPlugin(
        MastodonDiscoveryConfig(
            enabled=True,
            require_auth=True,
            max_results=10,
            api_base_url="https://mastodon.social",
        ),
        archive_config,
        ledger_service,
    )
    crypto = CryptoMarketDataPlugin(
        CryptoMarketDataConfig(enabled=False, max_chart_points=10),
        archive_config,
        ledger_service,
    )

    with pytest.raises(ValueError, match="disabled"):
        brave.search(BraveSearchRequest(query="python jobs"))
    with pytest.raises(MastodonDiscoveryPluginError, match="MASTODON_API_TOKEN"):
        mastodon.sample_public_timeline(MastodonPublicTimelineRequest(limit=1))
    with pytest.raises(ValueError, match="disabled"):
        crypto.get_spot_price(CryptoSpotPriceRequest(asset_id="bitcoin"))
