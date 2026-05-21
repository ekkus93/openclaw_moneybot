"""Deterministic eligibility gating."""

from __future__ import annotations

import re
from collections.abc import Iterable

from openclaw_moneybot.shared import ArchiveConfig
from openclaw_moneybot.shared.types import ConfidenceLevel, EligibilityDecisionType, RecordType
from openclaw_moneybot.skills.account_eligibility_checker.models import (
    AccountEligibilityRequest,
    AccountEligibilityResult,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import ReceiptAndEvidenceArchiver
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id

GEO_PATTERNS = {
    "united states": {"us", "usa", "united states"},
    "us only": {"us", "usa", "united states"},
    "canada": {"canada"},
    "european union": {"eu", "european union"},
    "eu only": {"eu", "european union"},
}
PAYOUT_METHOD_PATTERNS = {
    "paypal": "paypal",
    "bank wire": "bank_wire",
    "wire transfer": "bank_wire",
    "bitcoin": "btc",
    "btc": "btc",
    "usdc": "usdc",
    "ethereum": "eth",
    "eth": "eth",
}
OS_PATTERNS = ("linux", "windows", "mac", "macos")
HARDWARE_PATTERNS = ("gpu", "android", "iphone", "ios")


def _has_any(text: str, needles: Iterable[str]) -> bool:
    return any(needle in text for needle in needles)


class AccountEligibilityChecker:
    """Reject clearly ineligible opportunities before deeper planning."""

    def __init__(self, archive_config: ArchiveConfig, ledger_service: LedgerService) -> None:
        self.ledger_service = ledger_service
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)

    def evaluate(self, request: AccountEligibilityRequest) -> AccountEligibilityResult:
        """Evaluate whether the operator is eligible to pursue an opportunity."""
        eligibility_id = make_id("eligibility")
        text = (request.rules_text or "").lower()
        reasons: list[str] = []
        missing: list[str] = []
        blocked: list[str] = []
        review_required: list[str] = []
        profile = request.operator_profile
        matched_geo_phrase = False

        if not text:
            missing.append("missing_rule_text")

        if "personal account" in text and not profile.personal_account_allowed:
            blocked.append("requires_personal_account")
        if _has_any(text, ("twitter account", "linkedin profile", "non-bot social")):
            if not profile.non_bot_social_identity_available:
                blocked.append("requires_non_bot_social_identity")
        if "account age" in text or "account must be" in text:
            age_match = re.search(r"(\d+)\s*day", text)
            if profile.platform_account_age_days is None:
                missing.append("platform_account_age_unknown")
            elif (
                age_match is not None
                and profile.platform_account_age_days < int(age_match.group(1))
            ):
                blocked.append("platform_account_too_new")
        if _has_any(text, ("reputation", "karma", "rating history")):
            if profile.profile_reputation_available is None:
                review_required.append("reputation_requirement_unverified")
            elif not profile.profile_reputation_available:
                blocked.append("missing_required_reputation_history")

        for phrase, allowed_regions in GEO_PATTERNS.items():
            if phrase in text:
                matched_geo_phrase = True
                region = (profile.region or profile.residency or profile.citizenship or "").lower()
                if not region:
                    missing.append("region_unknown")
                elif region not in allowed_regions:
                    blocked.append("geo_restriction")

        if "18+" in text or "must be 18" in text:
            if profile.age_years is None:
                missing.append("age_unknown")
            elif profile.age_years < 18:
                blocked.append("age_restriction")
        if _has_any(text, ("citizen", "citizenship", "resident")) and not matched_geo_phrase:
            review_required.append("citizenship_or_residency_requirement")
        if _has_any(text, ("llc", "registered business", "business entity", "company required")):
            if profile.has_business_entity is None:
                missing.append("business_entity_unknown")
            elif not profile.has_business_entity:
                blocked.append("business_entity_required")
        if _has_any(text, ("kyc", "tax form", "w-9", "w8", "w-8")):
            if profile.tax_identity_available is None:
                review_required.append("tax_or_kyc_unverified")
            elif not profile.tax_identity_available:
                blocked.append("tax_or_kyc_requirement")

        for os_name in OS_PATTERNS:
            if f"{os_name} required" in text and os_name not in {
                item.lower() for item in profile.operating_systems
            }:
                blocked.append(f"{os_name}_required")
        for hardware in HARDWARE_PATTERNS:
            if hardware in text and hardware not in {
                item.lower() for item in profile.available_hardware
            }:
                blocked.append(f"{hardware}_required")
        if _has_any(text, ("private infrastructure", "self-hosted server", "private vps")):
            if profile.private_infrastructure_available is None:
                review_required.append("private_infrastructure_unverified")
            elif not profile.private_infrastructure_available:
                blocked.append("private_infrastructure_required")
        if _has_any(text, ("repository history", "github history")):
            if profile.repository_history_available is None:
                missing.append("repository_history_unknown")
            elif not profile.repository_history_available:
                blocked.append("repository_history_required")
        if _has_any(text, ("prior contribution", "previous pull request", "prior pr")):
            if not profile.prior_contribution_tags:
                blocked.append("prior_contribution_required")

        hinted_method = (request.payment_method_hint or "").lower()
        hinted_asset = (request.asset_hint or "").lower()
        supported_methods = {item.lower() for item in profile.supported_payout_methods}
        supported_assets = {item.lower() for item in profile.supported_assets}
        for phrase, normalized in PAYOUT_METHOD_PATTERNS.items():
            if phrase in text or phrase == hinted_method or phrase == hinted_asset:
                if normalized in {"btc", "eth", "usdc"}:
                    if normalized not in supported_assets:
                        blocked.append("unsupported_currency_or_asset")
                elif normalized not in supported_methods:
                    blocked.append("unsupported_payout_method")
        if _has_any(text, ("manual approval", "payment approval", "invoice review")):
            review_required.append("manual_payment_approval_needed")

        if blocked:
            decision = EligibilityDecisionType.BLOCKED
            reasons.append(
                "Eligibility requirements conflict with the configured operator profile."
            )
        elif review_required:
            decision = EligibilityDecisionType.NEEDS_REVIEW
            reasons.append("Some requirements are ambiguous or require manual confirmation.")
        elif missing:
            decision = EligibilityDecisionType.INCOMPLETE
            reasons.append("Eligibility evidence is missing for one or more required checks.")
        else:
            decision = EligibilityDecisionType.ELIGIBLE
            reasons.append(
                "The opportunity requirements are compatible with the configured operator profile."
            )

        confidence = (
            ConfidenceLevel.HIGH
            if not review_required and not missing
            else ConfidenceLevel.MEDIUM
        )
        safe_next_steps = {
            EligibilityDecisionType.ELIGIBLE: ["continue_to_policy_and_tos_checks"],
            EligibilityDecisionType.BLOCKED: ["record_block_and_skip_budgeting"],
            EligibilityDecisionType.NEEDS_REVIEW: ["request_manual_eligibility_review"],
            EligibilityDecisionType.INCOMPLETE: ["capture_missing_rules_or_profile_data"],
        }[decision]
        snapshot = {
            "opportunity_id": request.opportunity_id,
            "decision": decision.value,
            "blocked_requirements": blocked,
            "missing_requirements": missing,
            "review_required_requirements": review_required,
            "safe_next_steps": safe_next_steps,
            "policy_decision_id": request.policy_decision_id,
            "tos_legal_check_id": request.tos_legal_check_id,
            "source_url": None if request.source_url is None else str(request.source_url),
        }
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.ACCOUNT_ELIGIBILITY,
            related_id=eligibility_id,
            evidence_type="eligibility_snapshot",
            payload=snapshot,
            notes="Deterministic account eligibility decision",
        )
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=eligibility_id,
            record_type=RecordType.ACCOUNT_ELIGIBILITY,
            related_record_id=request.opportunity_id,
            payload={
                **snapshot,
                "evidence_archive_ids": [*request.evidence_archive_ids, evidence_id],
            },
        )
        return AccountEligibilityResult(
            eligibility_id=eligibility_id,
            decision=decision,
            confidence=confidence,
            reasons=reasons,
            missing_requirements=missing,
            blocked_requirements=blocked,
            review_required_requirements=review_required,
            safe_next_steps=safe_next_steps,
            evidence_archive_ids=[*request.evidence_archive_ids, evidence_id],
            ledger_record=ledger_record,
        )
