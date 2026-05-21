"""Structured strategy memory from ledgered outcomes."""

from __future__ import annotations

from openclaw_moneybot.shared import ArchiveConfig
from openclaw_moneybot.shared.types import (
    CounterpartyRiskTier,
    ReconciliationStatus,
    RecordType,
    StrategyLessonCategory,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import ReceiptAndEvidenceArchiver
from openclaw_moneybot.skills.strategy_memory_summarizer.models import (
    StrategyMemorySummaryRequest,
    StrategyMemorySummaryResult,
)
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id


class StrategyMemorySummarizer:
    """Convert experiment outcomes into reusable structured heuristics."""

    def __init__(self, archive_config: ArchiveConfig, ledger_service: LedgerService) -> None:
        self.ledger_service = ledger_service
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)

    def summarize(self, request: StrategyMemorySummaryRequest) -> StrategyMemorySummaryResult:
        """Create a structured strategy memory summary."""
        summary_id = make_id("strategy_summary")
        categories: list[StrategyLessonCategory] = []
        what_worked: list[str] = []
        what_failed: list[str] = []
        heuristics_to_keep: list[str] = []
        heuristics_to_avoid: list[str] = []
        tentative_hypotheses: list[str] = []

        if request.net_usd > 0:
            categories.append(StrategyLessonCategory.BUDGETING)
            what_worked.append("Positive net outcome.")
            heuristics_to_keep.append("Prefer opportunities with positive realized ROI.")
        else:
            categories.append(StrategyLessonCategory.RISK)
            what_failed.append("Outcome failed to recover planned effort or spend.")
            heuristics_to_avoid.append("Avoid repeating low-return variants unchanged.")
        if request.reconciliation_status is ReconciliationStatus.MATCHED:
            categories.append(StrategyLessonCategory.PAYOUT)
            what_worked.append("Expected payout matched observed payout.")
        else:
            categories.append(StrategyLessonCategory.PAYOUT)
            what_failed.append("Payout handling required additional review or follow-up.")
            heuristics_to_avoid.append("Do not assume payout reliability without proof.")
        if request.time_spent_hours > 4:
            categories.append(StrategyLessonCategory.QUEUE)
            heuristics_to_avoid.append("Avoid long timeboxes for similar low-signal experiments.")
        if request.counterparty_risk_tier is CounterpartyRiskTier.LOW:
            categories.append(StrategyLessonCategory.COUNTERPARTY)
            heuristics_to_keep.append("Favor counterparties with strong local trust signals.")
        elif request.counterparty_risk_tier is CounterpartyRiskTier.HIGH:
            categories.append(StrategyLessonCategory.COUNTERPARTY)
            heuristics_to_avoid.append("Escalate high-risk counterparties before committing work.")
        if request.contradictory_results:
            tentative_hypotheses.append(
                "Conflicting outcomes suggest a hypothesis, not a hard rule."
            )

        snapshot = {
            "scope": request.scope,
            "lesson_categories": [item.value for item in categories],
            "what_worked": what_worked,
            "what_failed": what_failed,
            "heuristics_to_keep": heuristics_to_keep,
            "heuristics_to_avoid": heuristics_to_avoid,
            "tentative_hypotheses": tentative_hypotheses,
        }
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.STRATEGY_SUMMARY,
            related_id=summary_id,
            evidence_type="strategy_summary_snapshot",
            payload=snapshot,
            notes="Structured strategy memory summary",
        )
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=summary_id,
            record_type=RecordType.STRATEGY_SUMMARY,
            related_record_id=request.opportunity_id,
            payload={
                **snapshot,
                "evidence_archive_ids": [*request.evidence_archive_ids, evidence_id],
            },
        )
        return StrategyMemorySummaryResult(
            summary_id=summary_id,
            scope=request.scope,
            lesson_categories=categories,
            what_worked=what_worked,
            what_failed=what_failed,
            heuristics_to_keep=heuristics_to_keep,
            heuristics_to_avoid=heuristics_to_avoid,
            tentative_hypotheses=tentative_hypotheses,
            evidence_archive_ids=[*request.evidence_archive_ids, evidence_id],
            ledger_record=ledger_record,
        )
