"""Duplicate opportunity detection."""

from __future__ import annotations

from difflib import SequenceMatcher

from openclaw_moneybot.shared.types import DuplicateConfidence, RecordType
from openclaw_moneybot.skills.duplicate_opportunity_detector.models import (
    DuplicateOpportunityDetectorRequest,
    DuplicateOpportunityDetectorResult,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.support import record_structured_result
from openclaw_moneybot.utils.ids import make_id


def _normalized(value: str | None) -> str:
    return "" if value is None else " ".join(value.lower().split())


def _max_confidence(
    current: DuplicateConfidence,
    candidate: DuplicateConfidence,
) -> DuplicateConfidence:
    order = {
        DuplicateConfidence.LOW: 0,
        DuplicateConfidence.MEDIUM: 1,
        DuplicateConfidence.HIGH: 2,
    }
    return current if order[current] >= order[candidate] else candidate


class DuplicateOpportunityDetector:
    """Detect reposted or substantially identical opportunities."""

    def __init__(self, ledger_service: LedgerService) -> None:
        self.ledger_service = ledger_service

    def evaluate(
        self,
        request: DuplicateOpportunityDetectorRequest,
    ) -> DuplicateOpportunityDetectorResult:
        """Compare a candidate opportunity against prior opportunities."""
        analysis_id = make_id("duplicate_analysis")
        matched_ids: list[str] = []
        match_reasons: list[str] = []
        confidence = DuplicateConfidence.LOW
        candidate = request.candidate
        title = _normalized(candidate.title)
        description = _normalized(candidate.description)
        for existing in request.existing:
            if candidate.source_url == existing.source_url:
                matched_ids.append(existing.opportunity_id)
                match_reasons.append("exact_url_match")
                confidence = DuplicateConfidence.HIGH
                continue
            if (
                candidate.rules_url
                and candidate.rules_url == existing.rules_url
                and (
                    title == _normalized(existing.title)
                    or SequenceMatcher(
                        None,
                        description or title,
                        _normalized(existing.description) or _normalized(existing.title),
                    ).ratio()
                    >= 0.92
                )
            ):
                matched_ids.append(existing.opportunity_id)
                match_reasons.append("normalized_rules_url_match")
                confidence = DuplicateConfidence.HIGH
                continue
            if title and title == _normalized(existing.title):
                matched_ids.append(existing.opportunity_id)
                match_reasons.append("normalized_title_match")
                confidence = _max_confidence(confidence, DuplicateConfidence.MEDIUM)
                continue
            similarity = SequenceMatcher(
                None,
                description or title,
                _normalized(existing.description) or _normalized(existing.title),
            ).ratio()
            if (
                similarity >= 0.92
                and candidate.platform == existing.platform
                and candidate.payout_usd == existing.payout_usd
            ):
                matched_ids.append(existing.opportunity_id)
                match_reasons.append("near_duplicate_repost")
                confidence = _max_confidence(confidence, DuplicateConfidence.HIGH)
        is_duplicate = bool(matched_ids)
        if not is_duplicate and (not candidate.title or not candidate.description):
            confidence = DuplicateConfidence.MEDIUM
            match_reasons.append("metadata_incomplete_review")
        safe_next_steps = (
            ["reuse_existing_opportunity_or_require_review"]
            if is_duplicate
            else ["continue_normal_workflow"]
        )
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=analysis_id,
            record_type=RecordType.DUPLICATE_ANALYSIS,
            related_record_id=candidate.opportunity_id,
            payload={
                "candidate_opportunity_id": candidate.opportunity_id,
                "is_duplicate": is_duplicate,
                "confidence": confidence.value,
                "matched_opportunity_ids": matched_ids,
                "match_reasons": match_reasons,
                "safe_next_steps": safe_next_steps,
            },
        )
        return DuplicateOpportunityDetectorResult(
            duplicate_analysis_id=analysis_id,
            is_duplicate=is_duplicate,
            confidence=confidence,
            matched_opportunity_ids=matched_ids,
            match_reasons=match_reasons,
            safe_next_steps=safe_next_steps,
            ledger_record=ledger_record,
        )
