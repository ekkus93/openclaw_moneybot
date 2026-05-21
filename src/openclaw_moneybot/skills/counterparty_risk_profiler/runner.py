"""Deterministic counterparty risk scoring."""

from __future__ import annotations

from openclaw_moneybot.shared import ArchiveConfig
from openclaw_moneybot.shared.types import CounterpartyRiskTier, RecordType
from openclaw_moneybot.skills.counterparty_risk_profiler.models import (
    CounterpartyRiskProfileRequest,
    CounterpartyRiskProfileResult,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import ReceiptAndEvidenceArchiver
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id


class CounterpartyRiskProfiler:
    """Score counterparties using bounded local signals."""

    def __init__(self, archive_config: ArchiveConfig, ledger_service: LedgerService) -> None:
        self.ledger_service = ledger_service
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)

    def profile(self, request: CounterpartyRiskProfileRequest) -> CounterpartyRiskProfileResult:
        """Create a deterministic counterparty risk profile."""
        profile_id = make_id("counterparty_profile")
        score = 50
        positive_signals: list[str] = []
        negative_signals: list[str] = []
        unknowns: list[str] = []

        if request.clear_payout_rules:
            positive_signals.append("clear_payout_rules")
            score -= 10
        else:
            negative_signals.append("unclear_payout_rules")
            score += 10
        if request.clear_deadlines:
            positive_signals.append("clear_deadlines")
            score -= 5
        else:
            unknowns.append("deadline_clarity_unknown")
        if request.payout_history_success_rate is None:
            unknowns.append("payout_history_unknown")
        elif request.payout_history_success_rate >= 0.8:
            positive_signals.append("strong_payout_history")
            score -= 15
        elif request.payout_history_success_rate < 0.5:
            negative_signals.append("weak_payout_history")
            score += 20
        if request.prior_disputes > 0:
            negative_signals.append("prior_disputes")
            score += min(20, request.prior_disputes * 5)
        if request.support_responsive is None:
            unknowns.append("support_responsiveness_unknown")
        elif request.support_responsive:
            positive_signals.append("responsive_support")
            score -= 5
        else:
            negative_signals.append("unresponsive_support")
            score += 10
        if request.suspicious_claims_present:
            negative_signals.append("suspicious_claims")
            score += 25
        if request.off_platform_payment_required:
            negative_signals.append("off_platform_payment_required")
            score += 25
        if request.unexpected_kyc_required:
            negative_signals.append("unexpected_kyc_required")
            score += 15
        if request.domain_age_days is None:
            unknowns.append("domain_age_unknown")
        elif request.domain_age_days < 30:
            negative_signals.append("new_or_unstable_domain")
            score += 10

        score = max(0, min(100, score))
        if score >= 70:
            risk_tier = CounterpartyRiskTier.HIGH
            recommended_action = "needs_review"
        elif score >= 45:
            risk_tier = CounterpartyRiskTier.MEDIUM
            recommended_action = "caution"
        else:
            risk_tier = CounterpartyRiskTier.LOW
            recommended_action = "proceed"

        snapshot = {
            "counterparty_name": request.counterparty_name,
            "platform_domain": request.platform_domain,
            "risk_tier": risk_tier.value,
            "score": score,
            "positive_signals": positive_signals,
            "negative_signals": negative_signals,
            "unknowns": unknowns,
            "recommended_action": recommended_action,
        }
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.COUNTERPARTY_PROFILE,
            related_id=profile_id,
            evidence_type="counterparty_profile_snapshot",
            payload=snapshot,
            notes="Deterministic counterparty risk profile",
        )
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=profile_id,
            record_type=RecordType.COUNTERPARTY_PROFILE,
            related_record_id=request.opportunity_id,
            payload={
                **snapshot,
                "evidence_archive_ids": [*request.evidence_archive_ids, evidence_id],
            },
        )
        return CounterpartyRiskProfileResult(
            counterparty_profile_id=profile_id,
            risk_tier=risk_tier,
            score=score,
            positive_signals=positive_signals,
            negative_signals=negative_signals,
            unknowns=unknowns,
            recommended_action=recommended_action,
            evidence_archive_ids=[*request.evidence_archive_ids, evidence_id],
            ledger_record=ledger_record,
        )
