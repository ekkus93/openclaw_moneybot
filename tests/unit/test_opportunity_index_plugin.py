"""Unit tests for the opportunity index plugin."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from openclaw_moneybot.plugins.opportunity_index_plugin import (
    OpportunityIndexEntry,
    OpportunityIndexPlugin,
    OpportunitySimilarityQueryRequest,
)
from openclaw_moneybot.plugins.opportunity_index_plugin.service import (
    _normalize,
    _normalize_url,
    _reward_range,
    _similarity_bucket,
)
from openclaw_moneybot.shared import (
    ExperimentReview,
    LedgerRecord,
    Opportunity,
    OpportunityIndexConfig,
)
from openclaw_moneybot.shared.types import RecordType, ReviewDecisionType, RiskLevel
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.support import record_structured_result


def make_plugin(tmp_path: Path) -> tuple[OpportunityIndexPlugin, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    plugin = OpportunityIndexPlugin(
        OpportunityIndexConfig(enabled=True, index_path=tmp_path / "opportunity_index.json"),
        ledger_service,
    )
    return plugin, ledger_service


def create_opportunity(
    ledger_service: LedgerService,
    *,
    opportunity_id: str,
    name: str,
    source_url: str,
    estimated_revenue_usd: float = 25.0,
) -> None:
    ledger_service.create_opportunity(
        Opportunity(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            opportunity_id=opportunity_id,
            name=name,
            category="bounty",
            status="open",
            source_url=source_url,
            required_spend_usd=0,
            estimated_revenue_usd=estimated_revenue_usd,
            max_loss_usd=0,
            legal_risk_precheck=RiskLevel.LOW,
            tos_risk_precheck=RiskLevel.LOW,
        ),
        idempotency_key=f"opp:{opportunity_id}",
    )


def create_review(
    ledger_service: LedgerService,
    *,
    review_id: str,
    opportunity_id: str,
    decision: ReviewDecisionType = ReviewDecisionType.CONTINUE,
    outcome: str = "completed",
) -> None:
    ledger_service.record_experiment_review(
        ExperimentReview(
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
            experiment_review_id=review_id,
            opportunity_id=opportunity_id,
            spent_usd=1.0,
            revenue_usd=2.0,
            net_usd=1.0,
            roi_percent=100.0,
            outcome=outcome,
            decision=decision,
            lessons=["worked"],
            recommended_next_actions=["continue"],
        ),
        idempotency_key=f"review:{review_id}",
    )


def create_rule_snapshot(
    ledger_service: LedgerService,
    *,
    record_id: str,
    opportunity_id: str,
    normalized_hash: str = "hash_001",
) -> None:
    record_structured_result(
        ledger_service,
        record_id=record_id,
        record_type=RecordType.RULE_SNAPSHOT,
        related_record_id=opportunity_id,
        payload={
            "opportunity_id": opportunity_id,
            "normalized_hash": normalized_hash,
        },
    )


def test_similar_opportunities_are_surfaced_as_duplicates(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    create_opportunity(
        ledger_service,
        opportunity_id="opp_001",
        name="Example docs bounty",
        source_url="https://example.com/bounties/1",
    )
    plugin.rebuild_index()

    result = plugin.query_similar(
        OpportunitySimilarityQueryRequest(
            title="Example docs bounty",
            source_url="https://example.com/bounties/1",
        )
    )

    assert result.matches[0].opportunity_id == "opp_001"
    assert result.matches[0].similarity.value in {"exact", "high"}


def test_distinct_opportunities_are_not_over_merged(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    create_opportunity(
        ledger_service,
        opportunity_id="opp_001",
        name="Example docs bounty",
        source_url="https://example.com/bounties/1",
    )
    create_opportunity(
        ledger_service,
        opportunity_id="opp_002",
        name="Different hosting task",
        source_url="https://example.com/tasks/2",
    )
    plugin.rebuild_index()

    result = plugin.query_similar(
        OpportunitySimilarityQueryRequest(title="Completely unrelated work")
    )

    assert result.matches == []


def test_incremental_indexing_updates_results_correctly(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    create_opportunity(
        ledger_service,
        opportunity_id="opp_001",
        name="Example docs bounty",
        source_url="https://example.com/bounties/1",
    )
    plugin.rebuild_index()
    create_opportunity(
        ledger_service,
        opportunity_id="opp_002",
        name="Example docs bounty follow-up",
        source_url="https://example.com/bounties/2",
    )

    plugin.update_opportunity("opp_002")
    result = plugin.query_similar(
        OpportunitySimilarityQueryRequest(title="Example docs bounty follow-up")
    )

    assert any(match.opportunity_id == "opp_002" for match in result.matches)


def test_unsafe_query_shapes_are_rejected(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(ValueError, match="configured maximum"):
        plugin.query_similar(OpportunitySimilarityQueryRequest(title="Example", limit=100))


def test_rebuild_path_preserves_determinism(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    create_opportunity(
        ledger_service,
        opportunity_id="opp_001",
        name="Example docs bounty",
        source_url="https://example.com/bounties/1",
    )

    plugin.rebuild_index()
    first = plugin.config.index_path.read_text(encoding="utf-8")
    plugin.rebuild_index()
    second = plugin.config.index_path.read_text(encoding="utf-8")

    assert first == second


def test_query_rebuilds_index_automatically_when_missing(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    create_opportunity(
        ledger_service,
        opportunity_id="opp_001",
        name="Example docs bounty",
        source_url="https://example.com/bounties/1",
    )

    result = plugin.query_similar(OpportunitySimilarityQueryRequest(title="Example docs bounty"))

    assert plugin.config.index_path.exists() is True
    assert result.matches[0].opportunity_id == "opp_001"


def test_query_similar_preserves_deterministic_order_for_ties(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    create_opportunity(
        ledger_service,
        opportunity_id="opp_001",
        name="Example docs bounty",
        source_url="https://example.com/bounties/1",
    )
    create_opportunity(
        ledger_service,
        opportunity_id="opp_002",
        name="Example docs bounty",
        source_url="https://example.com/bounties/2",
    )
    plugin.rebuild_index()

    result = plugin.query_similar(OpportunitySimilarityQueryRequest(title="Example docs bounty"))

    assert [match.opportunity_id for match in result.matches] == ["opp_001", "opp_002"]


def test_update_opportunity_replaces_existing_entry_instead_of_duplicating(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    create_opportunity(
        ledger_service,
        opportunity_id="opp_001",
        name="Example docs bounty",
        source_url="https://example.com/bounties/1",
    )
    plugin.rebuild_index()

    plugin.update_opportunity("opp_001")
    payload = plugin.config.index_path.read_text(encoding="utf-8")

    assert payload.count("opp_001") == 1


def test_rebuild_index_records_entry_count_in_ledger_payload(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    create_opportunity(
        ledger_service,
        opportunity_id="opp_001",
        name="Example docs bounty",
        source_url="https://example.com/bounties/1",
    )

    result = plugin.rebuild_index()

    assert result.ledger_record.payload["entry_count"] == 1


def test_build_entry_raises_for_unknown_opportunity(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)

    with pytest.raises(ValueError, match="Unknown opportunity"):
        plugin._build_entry("missing")


def test_build_entry_collects_rule_snapshot_hashes_and_review_labels(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    create_opportunity(
        ledger_service,
        opportunity_id="opp_001",
        name="Example docs bounty",
        source_url="https://example.com/bounties/1",
    )
    create_rule_snapshot(
        ledger_service,
        record_id="rule_001",
        opportunity_id="opp_001",
        normalized_hash="hash_abc",
    )
    create_review(
        ledger_service,
        review_id="review_001",
        opportunity_id="opp_001",
        decision=ReviewDecisionType.STOP,
    )

    entry = plugin._build_entry("opp_001")

    assert entry.rule_hashes == ["hash_abc"]
    assert entry.outcome_labels == ["stop"]


def test_build_entry_ignores_malformed_or_unrelated_events_and_sorts_tags(tmp_path: Path) -> None:
    plugin, ledger_service = make_plugin(tmp_path)
    ledger_service.create_opportunity(
        Opportunity(
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            opportunity_id="opp_001",
            name="Example docs bounty",
            category="bounty",
            status="open",
            source_url="https://example.com/bounties/1",
            required_spend_usd=0,
            estimated_revenue_usd=125.0,
            max_loss_usd=0,
            legal_risk_precheck=RiskLevel.LOW,
            tos_risk_precheck=RiskLevel.LOW,
            raw_json={"tags": ["beta", "alpha", "alpha"]},
        ),
        idempotency_key="opp:opp_001",
    )
    ledger_service.record_ledger_record(
        LedgerRecord(
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
            record_id="rule_bad",
            record_type=RecordType.RULE_SNAPSHOT,
            related_record_id="opp_001",
            payload={"payload": "bad"},
        ),
        idempotency_key="rule_bad",
    )
    create_rule_snapshot(
        ledger_service,
        record_id="rule_other",
        opportunity_id="opp_other",
        normalized_hash="hash_other",
    )
    ledger_service.record_ledger_record(
        LedgerRecord(
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
            record_id="review_other",
            record_type=RecordType.EXPERIMENT_REVIEW,
            related_record_id="opp_other",
            payload={"opportunity_id": "opp_other", "decision": "continue"},
        ),
        idempotency_key="review_other",
    )

    entry = plugin._build_entry("opp_001")

    assert entry.rule_hashes == []
    assert entry.outcome_labels == []
    assert entry.tags == ["alpha", "beta", "bounty"]
    assert entry.reward_range == "100_plus"


def test_load_entries_raises_for_non_list_payload(tmp_path: Path) -> None:
    plugin, _ = make_plugin(tmp_path)
    plugin.config.index_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="malformed"):
        plugin._load_entries()


def test_scoring_and_normalization_helpers_cover_branch_thresholds() -> None:
    entry = plugin_entry()
    exact_score, exact_reasons = OpportunityIndexPlugin._score_entry(
        entry,
        normalized_title="example docs bounty",
        normalized_source_url="https://example.com/bounties/1",
        normalized_counterparty="",
    )
    similar_score, similar_reasons = OpportunityIndexPlugin._score_entry(
        entry,
        normalized_title="example docs bounties",
        normalized_source_url="",
        normalized_counterparty="",
    )
    counterparty_score, counterparty_reasons = OpportunityIndexPlugin._score_entry(
        plugin_entry(counterparty="Example Vendor"),
        normalized_title="different",
        normalized_source_url="",
        normalized_counterparty="example vendor",
    )

    assert "exact_source_url" in exact_reasons
    assert exact_score == 1.0
    assert "similar_title" in similar_reasons or "near_exact_title" in similar_reasons
    assert "counterparty_match" in counterparty_reasons
    assert _normalize("  Mixed   CASE ") == "mixed case"
    assert _normalize(None) == ""
    assert _normalize_url("HTTPS://Example.com/path/") == "https://example.com/path"
    assert _reward_range(None) is None
    assert _reward_range(5) == "under_25"
    assert _reward_range(25) == "25_to_99"
    assert _reward_range(100) == "100_plus"
    assert _similarity_bucket(1.0).value == "exact"
    assert _similarity_bucket(0.9).value == "high"
    assert _similarity_bucket(0.6).value == "medium"
    assert _similarity_bucket(0.2).value == "low"
    assert similar_score >= 0.8
    assert counterparty_score == 0.75


def plugin_entry(*, counterparty: str | None = None) -> OpportunityIndexEntry:
    return OpportunityIndexEntry(
        opportunity_id="opp_001",
        title="Example docs bounty",
        normalized_source_url="https://example.com/bounties/1",
        counterparty=counterparty,
        tags=["bounty"],
        reward_range="25_to_99",
        source_hash="hash",
    )
