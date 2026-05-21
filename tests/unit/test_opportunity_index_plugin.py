"""Unit tests for the opportunity index plugin."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from openclaw_moneybot.plugins.opportunity_index_plugin import (
    OpportunityIndexPlugin,
    OpportunitySimilarityQueryRequest,
)
from openclaw_moneybot.shared import Opportunity, OpportunityIndexConfig
from openclaw_moneybot.shared.types import RiskLevel
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


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
