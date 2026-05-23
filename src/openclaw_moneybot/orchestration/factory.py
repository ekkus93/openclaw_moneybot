"""Helpers for constructing the default orchestrator from config."""

from __future__ import annotations

import httpx

from openclaw_moneybot.orchestration.workflow import MoneyBotOrchestrator
from openclaw_moneybot.plugins.inner_voice_plugin import (
    ArbiterService,
    InnerVoiceCoordinator,
    InnerVoicePlugin,
)
from openclaw_moneybot.shared import AppConfig
from openclaw_moneybot.skills.account_eligibility_checker import AccountEligibilityChecker
from openclaw_moneybot.skills.budget_and_roi_planner import BudgetAndRoiPlanner
from openclaw_moneybot.skills.counterparty_risk_profiler import CounterpartyRiskProfiler
from openclaw_moneybot.skills.deliverable_quality_checker import DeliverableQualityChecker
from openclaw_moneybot.skills.duplicate_opportunity_detector import (
    DuplicateOpportunityDetector,
)
from openclaw_moneybot.skills.email_drafter import EmailDrafter
from openclaw_moneybot.skills.experiment_reviewer import ExperimentReviewer
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.moneybot_policy_guard import MoneyBotPolicyGuard
from openclaw_moneybot.skills.opportunity_scout import OpportunityScout
from openclaw_moneybot.skills.receipt_and_evidence_archiver import ReceiptAndEvidenceArchiver
from openclaw_moneybot.skills.revenue_reconciler import RevenueReconciler
from openclaw_moneybot.skills.strategy_memory_summarizer import StrategyMemorySummarizer
from openclaw_moneybot.skills.submission_package_builder import SubmissionPackageBuilder
from openclaw_moneybot.skills.tos_legal_checker import TosLegalChecker
from openclaw_moneybot.skills.wallet_governor_client import WalletGovernorClientSkill


def build_orchestrator(
    config: AppConfig,
    *,
    wallet_transport: httpx.BaseTransport | None = None,
    inner_voice_transport: httpx.BaseTransport | None = None,
    arbiter_transport: httpx.BaseTransport | None = None,
) -> MoneyBotOrchestrator:
    """Construct the default MoneyBot orchestrator from loaded config."""
    ledger_service = LedgerService.from_db_path(config.ledger.database_path)
    archiver = ReceiptAndEvidenceArchiver(config.archive, ledger_service)
    inner_voice_plugin = None
    arbiter_service = None
    inner_voice_coordinator = None
    if config.inner_voice.enabled:
        inner_voice_plugin = InnerVoicePlugin(
            config.inner_voice,
            config.archive,
            ledger_service,
            transport=inner_voice_transport,
        )
        arbiter_service = ArbiterService(
            config.arbiter,
            config.archive,
            ledger_service,
            transport=arbiter_transport,
        )
        inner_voice_coordinator = InnerVoiceCoordinator(
            inner_voice_plugin,
            arbiter_service,
            archiver,
            ledger_service,
        )
    return MoneyBotOrchestrator(
        ledger_service=ledger_service,
        scout=OpportunityScout(),
        duplicate_detector=DuplicateOpportunityDetector(ledger_service),
        eligibility_checker=AccountEligibilityChecker(config.archive, ledger_service),
        policy_guard=MoneyBotPolicyGuard(config.policy),
        tos_checker=TosLegalChecker(ledger_service),
        budget_planner=BudgetAndRoiPlanner(config.policy, ledger_service),
        counterparty_risk_profiler=CounterpartyRiskProfiler(config.archive, ledger_service),
        submission_package_builder=SubmissionPackageBuilder(config.archive, ledger_service),
        deliverable_quality_checker=DeliverableQualityChecker(config.archive, ledger_service),
        email_drafter=EmailDrafter(config.archive, ledger_service),
        wallet_client=WalletGovernorClientSkill(
            config.wallet_governor,
            config.policy,
            ledger_service,
            config.archive,
            transport=wallet_transport,
        ),
        reviewer=ExperimentReviewer(config.archive, ledger_service),
        revenue_reconciler=RevenueReconciler(config.archive, ledger_service),
        strategy_memory_summarizer=StrategyMemorySummarizer(config.archive, ledger_service),
        archiver=archiver,
        inner_voice_plugin=inner_voice_plugin,
        arbiter_service=arbiter_service,
        inner_voice_coordinator=inner_voice_coordinator,
    )
