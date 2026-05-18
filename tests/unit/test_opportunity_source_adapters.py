"""Tests for opportunity source adapters."""

from __future__ import annotations

from pathlib import Path

from openclaw_moneybot.shared import ArchiveConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.opportunity_scout import (
    GitHubIssueFixtureAdapter,
    HackathonListingAdapter,
    LocalFixtureDocumentAdapter,
    ManualUrlIngestionAdapter,
    OpportunityScout,
    OpportunityScoutRequest,
    PublicBountyPageAdapter,
    ScoutSourceDocument,
)
from openclaw_moneybot.skills.receipt_and_evidence_archiver import ReceiptAndEvidenceArchiver


def make_request(documents: list[ScoutSourceDocument]) -> OpportunityScoutRequest:
    return OpportunityScoutRequest.model_validate(
        {
            "mission": "Find low-budget developer opportunities.",
            "budget_usd": 100,
            "skills_available": ["python", "documentation", "web"],
            "blocked_categories": ["gambling"],
            "preferred_categories": ["bounty", "documentation", "micro_product"],
            "max_results": 10,
            "time_budget_hours": 8,
            "evidence_required": True,
            "source_documents": documents,
        }
    )


def test_local_fixture_adapter_returns_normalized_documents() -> None:
    adapter = LocalFixtureDocumentAdapter(
        [
            ScoutSourceDocument(
                source_name="Docs bounty",
                category_hint="Bounty",
                source_url="https://example.com/bounty",
                payment_method="BTC payout",
                content_text="Spend $5. Payout $25.",
            )
        ]
    )

    documents = adapter.fetch_candidates()

    assert documents[0].source_type == "fixture"
    assert documents[0].category_hint == "bounty"


def test_manual_url_adapter_supports_supplied_content() -> None:
    adapter = ManualUrlIngestionAdapter(
        source_name="Manual source",
        category_hint="documentation",
        source_url="https://example.com/manual",
        payment_method="project payout",
        content_text="Documentation task. Payout $40.",
    )

    documents = adapter.fetch_candidates()

    assert documents[0].source_type == "manual_url"
    assert "Payout $40." in documents[0].content_text


def test_github_fixture_adapter_parses_fixture_payload() -> None:
    adapter = GitHubIssueFixtureAdapter(
        [
            {
                "title": "Issue bounty",
                "html_url": "https://github.com/example/repo/issues/1",
                "body": "Fix bug. Reward $50 after merge.",
                "labels": ["bug", "bounty"],
            }
        ]
    )

    documents = adapter.fetch_candidates()

    assert documents[0].source_type == "github_issue_fixture"
    assert documents[0].known_risk_notes == ["bug", "bounty"]


def test_public_bounty_and_hackathon_adapters_label_source_types() -> None:
    bounty_adapter = PublicBountyPageAdapter(
        source_name="Bounty page",
        source_url="https://example.com/bounty",
        content_text="Bounty. Payout $20.",
    )
    hackathon_adapter = HackathonListingAdapter(
        source_name="Hackathon page",
        source_url="https://example.com/hackathon",
        content_text="Hackathon. Prize $500.",
    )

    assert bounty_adapter.fetch_candidates()[0].category_hint == "bounty"
    assert hackathon_adapter.fetch_candidates()[0].category_hint == "contest"


def test_adapter_source_evidence_is_archived(tmp_path: Path) -> None:
    adapter = ManualUrlIngestionAdapter(
        source_name="Manual source",
        category_hint="documentation",
        source_url="https://example.com/manual",
        payment_method="project payout",
        content_text="Documentation task. Payout $40.",
    )
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archiver = ReceiptAndEvidenceArchiver(
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
    )

    evidence_ids = adapter.attach_source_evidence(
        adapter.fetch_candidates()[0],
        related_type=RecordType.OPPORTUNITY,
        related_id="opp_001",
        archiver=archiver,
    )

    assert len(evidence_ids) == 1
    assert ledger_service.get_evidence_record(evidence_ids[0]) is not None


def test_missing_payout_yields_lower_confidence() -> None:
    result = OpportunityScout().evaluate(
        make_request(
            [
                ScoutSourceDocument(
                    source_name="Unclear source",
                    category_hint="documentation",
                    source_url="https://example.com/source",
                    payment_method="unknown",
                    content_text="Documentation task with no payout listed.",
                )
            ]
        )
    )

    assert result.opportunities[0].confidence.value == "low"
    assert result.opportunities[0].recommended_next_step == "research_more"
