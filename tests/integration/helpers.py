"""Shared helpers for integration tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, TypedDict, cast

import httpx
from fastapi.testclient import TestClient

from openclaw_moneybot.orchestration import MoneyBotOrchestrator
from openclaw_moneybot.plugins.browser_governor import BrowserGovernorService
from openclaw_moneybot.plugins.email_governor import EmailGovernorService, FakeEmailTransport
from openclaw_moneybot.plugins.rules_snapshot_gateway import (
    RulesSnapshotCaptureRequest,
    RulesSnapshotCaptureResult,
    RulesSnapshotGateway,
)
from openclaw_moneybot.plugins.wallet_governor_service import (
    FakeWalletBackend,
    FakeWalletBackendState,
    WalletGovernorService,
    create_wallet_governor_app,
)
from openclaw_moneybot.shared import (
    ArchiveConfig,
    BudgetPlan,
    EmailConfig,
    EvidenceRecord,
    LedgerRecord,
    Opportunity,
    PolicyDecision,
    SpendRequest,
    TosLegalCheck,
    WalletTransactionRecord,
)
from openclaw_moneybot.shared.config import (
    BrowserGovernorConfig,
    MoneyBotPolicyConfig,
    RulesSnapshotGatewayConfig,
    WalletGovernorConfig,
)
from openclaw_moneybot.shared.types import (
    ActionType,
    BudgetDecisionType,
    ConfidenceLevel,
    EmailMode,
    PolicyDecisionType,
    RecordType,
    RiskLevel,
    TosDecisionType,
)
from openclaw_moneybot.skills.account_eligibility_checker import AccountEligibilityChecker
from openclaw_moneybot.skills.account_eligibility_checker.models import OperatorProfile
from openclaw_moneybot.skills.budget_and_roi_planner import BudgetAndRoiPlanner
from openclaw_moneybot.skills.budget_and_roi_planner.models import (
    BudgetPlanRequest,
    BudgetPlanResult,
)
from openclaw_moneybot.skills.counterparty_risk_profiler import CounterpartyRiskProfiler
from openclaw_moneybot.skills.deliverable_quality_checker import DeliverableQualityChecker
from openclaw_moneybot.skills.duplicate_opportunity_detector import (
    DuplicateOpportunityDetector,
)
from openclaw_moneybot.skills.email_drafter import EmailDrafter
from openclaw_moneybot.skills.experiment_reviewer import ExperimentReviewer
from openclaw_moneybot.skills.experiment_reviewer.models import (
    ExperimentReviewRequest,
    ExperimentReviewResult,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.moneybot_policy_guard import MoneyBotPolicyGuard
from openclaw_moneybot.skills.moneybot_policy_guard.models import (
    PolicyCheckRequest,
    PolicyCheckResult,
)
from openclaw_moneybot.skills.opportunity_scout import OpportunityScout, ScoutSourceDocument
from openclaw_moneybot.skills.receipt_and_evidence_archiver import ReceiptAndEvidenceArchiver
from openclaw_moneybot.skills.revenue_reconciler import (
    ReconciliationObservation,
    RevenueReconciler,
    RevenueReconciliationRequest,
)
from openclaw_moneybot.skills.revenue_reconciler.models import RevenueReconciliationResult
from openclaw_moneybot.skills.strategy_memory_summarizer import StrategyMemorySummarizer
from openclaw_moneybot.skills.strategy_memory_summarizer.models import (
    StrategyMemorySummaryRequest,
    StrategyMemorySummaryResult,
)
from openclaw_moneybot.skills.submission_package_builder import SubmissionPackageBuilder
from openclaw_moneybot.skills.tos_legal_checker import TosLegalChecker
from openclaw_moneybot.skills.tos_legal_checker.models import (
    TosLegalCheckRequest,
    TosLegalCheckResult,
)
from openclaw_moneybot.skills.wallet_governor_client import WalletGovernorClientSkill
from openclaw_moneybot.utils.time import utc_now


class PolicyEvaluator(Protocol):
    def evaluate(self, request: PolicyCheckRequest) -> PolicyCheckResult: ...


class TosEvaluator(Protocol):
    def evaluate(self, request: TosLegalCheckRequest) -> TosLegalCheckResult: ...


class BudgetEvaluator(Protocol):
    def evaluate(self, request: BudgetPlanRequest) -> BudgetPlanResult: ...


class MetricsHistorySeed(TypedDict):
    opportunity_id: str
    policy: PolicyDecision
    tos: TosLegalCheck
    budget: BudgetPlan
    evidence: EvidenceRecord
    review: ExperimentReviewResult
    reconciliation: RevenueReconciliationResult
    summary: StrategyMemorySummaryResult


def fixture_text(name: str) -> str:
    return (Path("tests/fixtures/tos_legal") / name).read_text(encoding="utf-8")


def make_policy_config() -> MoneyBotPolicyConfig:
    return MoneyBotPolicyConfig(
        policy_version="v1",
        blocked_categories=["gambling"],
        review_required_categories=["affiliate_marketing"],
        max_single_spend_usd=10,
        max_daily_spend_usd=20,
        max_weekly_spend_usd=40,
    )


def make_wallet_config(
    *,
    spend_enabled: bool,
    timeout_seconds: float = 10.0,
    archive_root: Path | None = None,
) -> WalletGovernorConfig:
    return WalletGovernorConfig(
        base_url="http://127.0.0.1",
        timeout_seconds=timeout_seconds,
        spend_enabled=spend_enabled,
        allowed_assets=["BTC"],
        archive_root=archive_root,
    )


def make_archive_config(tmp_path: Path) -> ArchiveConfig:
    return ArchiveConfig(base_directory=tmp_path / "archive")


def make_source_document(
    *,
    extra_text: str = "",
    category_hint: str = "bounty",
    source_url: str = "https://example.com/bounty",
    rules_url: str = "https://example.com/bounty/rules",
    payment_method: str = "BTC payout",
) -> ScoutSourceDocument:
    content_text = fixture_text("allowed_bounty.txt")
    if extra_text:
        content_text = f"{content_text}\n{extra_text}"
    return ScoutSourceDocument(
        source_name="Allowed bounty",
        category_hint=category_hint,
        source_url=source_url,
        rules_url=rules_url,
        payment_method=payment_method,
        content_text=content_text,
    )


def make_operator_profile(**overrides: object) -> OperatorProfile:
    payload: dict[str, object] = {
        "region": "united states",
        "age_years": 30,
        "supported_payout_methods": ["paypal", "bank_wire"],
        "supported_assets": ["btc"],
        "operating_systems": ["linux", "macos", "windows"],
        "available_hardware": ["gpu"],
        "private_infrastructure_available": True,
        "repository_history_available": True,
        "prior_contribution_tags": ["oss"],
        "profile_reputation_available": True,
    }
    payload.update(overrides)
    return OperatorProfile.model_validate(payload)


def write_submission_template(
    template_root: Path,
    *,
    template_name: str = "submission",
    required_fields: list[str] | None = None,
    body_template: str | None = None,
) -> Path:
    template_root.mkdir(parents=True, exist_ok=True)
    field_names = required_fields or ["name", "email"]
    template_path = template_root / f"{template_name}.json"
    template_path.write_text(
        json.dumps(
            {
                "output_filename": "submission.txt",
                "required_fields": field_names,
                "body_template": body_template
                or "".join(f"{field.title()}: {{{field}}}\n" for field in field_names),
            }
        ),
        encoding="utf-8",
    )
    return template_path


def seed_rules_snapshot_pair(
    ledger_service: LedgerService,
    archive_config: ArchiveConfig,
    *,
    opportunity_id: str = "opp_001",
    source_url: str = "https://example.com/rules",
    first_text: str = "Payout is $25.\nAutomation allowed.",
    second_text: str = "Payout is $10.\nAutomation prohibited.",
) -> tuple[RulesSnapshotCaptureResult, RulesSnapshotCaptureResult]:
    gateway = RulesSnapshotGateway(
        RulesSnapshotGatewayConfig(enabled=True, allowed_hosts=["example.com"]),
        archive_config,
        ledger_service,
    )
    first = gateway.capture(
        RulesSnapshotCaptureRequest(
            opportunity_id=opportunity_id,
            source_url=source_url,
            content_text=first_text,
            content_type="text/plain",
            idempotency_key=f"rules:{opportunity_id}:first",
        )
    )
    second = gateway.capture(
        RulesSnapshotCaptureRequest(
            opportunity_id=opportunity_id,
            source_url=source_url,
            content_text=second_text,
            content_type="text/plain",
            idempotency_key=f"rules:{opportunity_id}:second",
        )
    )
    return first, second


def seed_opportunity(
    ledger_service: LedgerService,
    *,
    opportunity_id: str = "opp_001",
    name: str = "Integration opportunity",
    category: str = "bounty",
    status: str = "approved",
    source_url: str = "https://example.com/opportunity",
    rules_url: str = "https://example.com/rules",
    required_spend_usd: float = 5.0,
    estimated_revenue_usd: float = 25.0,
    max_loss_usd: float = 5.0,
) -> Opportunity:
    opportunity = Opportunity(
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        opportunity_id=opportunity_id,
        name=name,
        category=category,
        status=status,
        source_url=source_url,
        rules_url=rules_url,
        required_spend_usd=required_spend_usd,
        estimated_revenue_usd=estimated_revenue_usd,
        max_loss_usd=max_loss_usd,
        legal_risk_precheck=RiskLevel.LOW,
        tos_risk_precheck=RiskLevel.LOW,
    )
    ledger_service.create_opportunity(
        opportunity,
        idempotency_key=f"opportunity:{opportunity_id}",
    )
    return opportunity


def seed_policy_decision(
    ledger_service: LedgerService,
    *,
    policy_decision_id: str = "policy_001",
    opportunity_id: str = "opp_001",
    decision: PolicyDecisionType = PolicyDecisionType.ALLOW,
) -> PolicyDecision:
    policy = PolicyDecision(
        created_at=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
        policy_decision_id=policy_decision_id,
        opportunity_id=opportunity_id,
        action_type=ActionType.SPEND,
        category="purchase",
        requires_payment=True,
        requires_wallet_action=True,
        amount_usd=100.0,
        counterparty="Example Vendor",
        planned_tools=["wallet_governor_client"],
        sanitized_input={"action_type": "spend"},
        decision=decision,
        risk_level=RiskLevel.LOW,
        confidence=ConfidenceLevel.HIGH,
        policy_version="v1",
        request_fingerprint="fingerprint",
    )
    ledger_service.record_policy_decision(policy, idempotency_key=f"policy:{policy_decision_id}")
    return policy


def seed_tos_legal_check(
    ledger_service: LedgerService,
    *,
    tos_legal_check_id: str = "tos_001",
    opportunity_id: str = "opp_001",
    decision: TosDecisionType = TosDecisionType.PROCEED,
    evidence_archive_ids: list[str] | None = None,
) -> TosLegalCheck:
    check = TosLegalCheck(
        created_at=datetime(2026, 1, 1, 0, 2, tzinfo=UTC),
        tos_legal_check_id=tos_legal_check_id,
        opportunity_id=opportunity_id,
        decision=decision,
        confidence=ConfidenceLevel.HIGH,
        platform_terms_summary="Proceed.",
        legal_risk_summary="Low.",
        tos_risk_summary="Low.",
        evidence_archive_ids=evidence_archive_ids or ["artifact_001"],
    )
    ledger_service.record_tos_legal_check(check, idempotency_key=f"tos:{tos_legal_check_id}")
    return check


def seed_evidence_record(
    ledger_service: LedgerService,
    *,
    evidence_id: str = "artifact_001",
    related_record_id: str = "opp_001",
    evidence_type: str = "html_snapshot",
    archive_root: Path | None = None,
) -> EvidenceRecord:
    archive_path = f"archive/{evidence_id}.txt"
    content_sha256 = "a" * 64
    if archive_root is not None:
        archive_root.mkdir(parents=True, exist_ok=True)
        evidence_path = archive_root / f"{evidence_id}.txt"
        content = f"evidence:{evidence_id}".encode()
        evidence_path.write_bytes(content)
        archive_path = str(evidence_path)
        from openclaw_moneybot.skills.receipt_and_evidence_archiver.hashing import sha256_bytes

        content_sha256 = sha256_bytes(content)
    evidence = EvidenceRecord(
        created_at=datetime(2026, 1, 1, 0, 4, tzinfo=UTC),
        evidence_id=evidence_id,
        related_record_type=RecordType.OPPORTUNITY,
        related_record_id=related_record_id,
        evidence_type=evidence_type,
        archive_path=archive_path,
        content_sha256=content_sha256,
        source_url="https://example.com/opportunity",
    )
    ledger_service.record_evidence(evidence, idempotency_key=f"evidence:{evidence_id}")
    return evidence


def seed_budget_plan(
    ledger_service: LedgerService,
    *,
    budget_plan_id: str = "budget_001",
    opportunity_id: str = "opp_001",
    policy_decision_id: str = "policy_001",
    tos_legal_check_id: str = "tos_001",
    decision: BudgetDecisionType = BudgetDecisionType.EXECUTE_REQUEST,
    recommended_budget_usd: float = 5.0,
    expected_gross_revenue_usd: float = 25.0,
) -> BudgetPlan:
    plan = BudgetPlan(
        created_at=datetime(2026, 1, 1, 0, 3, tzinfo=UTC),
        budget_plan_id=budget_plan_id,
        opportunity_id=opportunity_id,
        policy_decision_id=policy_decision_id,
        tos_legal_check_id=tos_legal_check_id,
        decision=decision,
        recommended_budget_usd=recommended_budget_usd,
        max_loss_usd=recommended_budget_usd,
        expected_gross_revenue_usd=expected_gross_revenue_usd,
        expected_net_revenue_usd=expected_gross_revenue_usd - recommended_budget_usd,
        break_even_condition="One payout",
        success_metric="Paid",
        stop_condition="Stop after one try",
        required_records=["budget_snapshot"],
        risk_level=RiskLevel.LOW,
        wallet_spend_request_allowed=decision is BudgetDecisionType.EXECUTE_REQUEST,
        approved_spend_categories=["purchase"],
        reasons=["Within limits."],
    )
    ledger_service.record_budget_plan(plan, idempotency_key=f"budget:{budget_plan_id}")
    return plan


def seed_spend_request(
    ledger_service: LedgerService,
    *,
    spend_request_id: str = "spend_001",
    opportunity_id: str = "opp_001",
    budget_plan_id: str = "budget_001",
    policy_decision_id: str = "policy_001",
    ledger_record_id: str = "ledger_001",
    amount_usd: float = 5.0,
    status: str = "proposed",
) -> SpendRequest:
    request = SpendRequest(
        created_at=utc_now(),
        spend_request_id=spend_request_id,
        opportunity_id=opportunity_id,
        budget_plan_id=budget_plan_id,
        policy_decision_id=policy_decision_id,
        ledger_record_id=ledger_record_id,
        amount_usd=amount_usd,
        asset="BTC",
        destination="bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2",
        counterparty="Example Vendor",
        purpose="Approved small payment",
        category="purchase",
        evidence_archive_ids=["artifact_001"],
        status=status,
    )
    ledger_service.record_spend_request(request, idempotency_key=f"spend:{spend_request_id}")
    return request


def seed_wallet_transaction(
    ledger_service: LedgerService,
    *,
    wallet_transaction_id: str = "wallet_tx_001",
    spend_request_id: str = "spend_001",
    amount_usd_estimate: float = 5.0,
    status: str = "sent",
) -> WalletTransactionRecord:
    transaction = WalletTransactionRecord(
        created_at=utc_now(),
        wallet_transaction_id=wallet_transaction_id,
        spend_request_id=spend_request_id,
        txid=f"tx_{wallet_transaction_id}",
        amount_btc="0.00010000",
        fee_btc="0.00000250",
        amount_usd_estimate=amount_usd_estimate,
        status=status,
        destination="bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2",
        purpose="Approved small payment",
    )
    ledger_service.record_wallet_transaction(
        transaction,
        idempotency_key=f"wallet:{wallet_transaction_id}",
    )
    return transaction


def make_wallet_service(
    ledger_service: LedgerService,
    *,
    spend_enabled: bool,
    timeout_seconds: float = 10.0,
    backend: FakeWalletBackend | None = None,
    archive_root: Path | None = None,
) -> WalletGovernorService:
    return WalletGovernorService(
        make_wallet_config(
            spend_enabled=spend_enabled,
            timeout_seconds=timeout_seconds,
            archive_root=archive_root,
        ),
        make_policy_config(),
        ledger_service,
        backend or FakeWalletBackend(FakeWalletBackendState(balance_sats=5_000_000)),
    )


def make_wallet_test_client(
    service: WalletGovernorService,
    *,
    request_timeout_seconds: float | None = None,
) -> TestClient:
    app = create_wallet_governor_app(
        service,
        request_timeout_seconds=request_timeout_seconds,
    )
    return TestClient(app, base_url="http://127.0.0.1")


def make_wallet_client_skill(
    ledger_service: LedgerService,
    archive_config: ArchiveConfig,
    *,
    spend_enabled: bool,
    transport: httpx.BaseTransport | None = None,
    timeout_seconds: float = 10.0,
) -> WalletGovernorClientSkill:
    return WalletGovernorClientSkill(
        make_wallet_config(spend_enabled=spend_enabled, timeout_seconds=timeout_seconds),
        make_policy_config(),
        ledger_service,
        archive_config,
        transport=transport,
    )


def make_orchestrator(
    tmp_path: Path,
    *,
    spend_enabled: bool,
    policy_guard: PolicyEvaluator | None = None,
    tos_checker: TosEvaluator | None = None,
    budget_planner: BudgetEvaluator | None = None,
) -> tuple[MoneyBotOrchestrator, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = make_archive_config(tmp_path)
    policy_config = make_policy_config()
    wallet_service = make_wallet_service(
        ledger_service,
        spend_enabled=spend_enabled,
        archive_root=archive_config.base_directory,
    )
    wallet_test_client = make_wallet_test_client(wallet_service)
    wallet_client = make_wallet_client_skill(
        ledger_service,
        archive_config,
        spend_enabled=spend_enabled,
        transport=wallet_test_client._transport,
    )
    wallet_client._integration_test_client = wallet_test_client  # type: ignore[attr-defined]
    orchestrator = MoneyBotOrchestrator(
        ledger_service=ledger_service,
        scout=OpportunityScout(),
        duplicate_detector=DuplicateOpportunityDetector(ledger_service),
        eligibility_checker=AccountEligibilityChecker(archive_config, ledger_service),
        policy_guard=cast(
            MoneyBotPolicyGuard,
            policy_guard or MoneyBotPolicyGuard(policy_config),
        ),
        tos_checker=cast(TosLegalChecker, tos_checker or TosLegalChecker(ledger_service)),
        budget_planner=cast(
            BudgetAndRoiPlanner,
            budget_planner or BudgetAndRoiPlanner(policy_config, ledger_service),
        ),
        counterparty_risk_profiler=CounterpartyRiskProfiler(archive_config, ledger_service),
        submission_package_builder=SubmissionPackageBuilder(archive_config, ledger_service),
        deliverable_quality_checker=DeliverableQualityChecker(archive_config, ledger_service),
        email_drafter=EmailDrafter(archive_config, ledger_service),
        wallet_client=wallet_client,
        reviewer=ExperimentReviewer(archive_config, ledger_service),
        revenue_reconciler=RevenueReconciler(archive_config, ledger_service),
        strategy_memory_summarizer=StrategyMemorySummarizer(archive_config, ledger_service),
        archiver=ReceiptAndEvidenceArchiver(archive_config, ledger_service),
    )
    return orchestrator, ledger_service


def make_email_config() -> EmailConfig:
    return EmailConfig(
        mode=EmailMode.CAPPED_SEND,
        max_outbound_per_day=5,
        max_per_domain_per_day=5,
        max_followups_per_thread=1,
        allowed_sender_emails=["bot@example.com"],
    )


def make_browser_config() -> BrowserGovernorConfig:
    return BrowserGovernorConfig(enabled=True, allowed_profile_ids=["moneybot-default"])


def make_email_stack(
    tmp_path: Path,
) -> tuple[LedgerService, EmailDrafter, EmailGovernorService, FakeEmailTransport]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = make_archive_config(tmp_path)
    archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)
    seed_opportunity(ledger_service, required_spend_usd=0.0)
    seed_policy_decision(ledger_service)
    seed_policy_decision(
        ledger_service,
        policy_decision_id="policy_blocked",
        decision=PolicyDecisionType.BLOCK,
    )
    seed_tos_legal_check(ledger_service)
    transport = FakeEmailTransport()
    governor = EmailGovernorService(
        make_email_config(),
        ledger_service,
        archiver,
        transport=transport,
    )
    return ledger_service, EmailDrafter(archive_config, ledger_service), governor, transport


def make_browser_stack(
    tmp_path: Path,
    *,
    enabled: bool,
    allow_policy: bool = True,
) -> tuple[LedgerService, BrowserGovernorService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    archive_config = make_archive_config(tmp_path)
    seed_opportunity(ledger_service)
    seed_policy_decision(
        ledger_service,
        decision=(PolicyDecisionType.ALLOW if allow_policy else PolicyDecisionType.NEEDS_REVIEW),
    )
    archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)
    governor = BrowserGovernorService(
        make_browser_config().model_copy(update={"enabled": enabled}),
        ledger_service,
        archiver,
    )
    return ledger_service, governor


def make_prewrite_record(ledger_service: LedgerService, *, related_id: str) -> str:
    write = ledger_service.record_ledger_record(
        LedgerRecord(
            created_at=utc_now(),
            record_id=f"audit_{related_id}",
            record_type=RecordType.AUDIT_EVENT,
            related_record_id=related_id,
            payload={"event_name": "wallet_prewrite"},
        ),
        idempotency_key=f"prewrite:{related_id}",
    )
    return write.ledger_event_id


def seed_realistic_metrics_history(
    ledger_service: LedgerService,
    archive_config: ArchiveConfig,
    *,
    opportunity_id: str = "opp_001",
    category: str = "bounty",
    expected_amount: float = 20.0,
    revenue_usd: float = 20.0,
    observed_amount: float | None = 20.0,
    current_date: datetime | None = None,
) -> MetricsHistorySeed:
    current = current_date or datetime(2026, 1, 3, tzinfo=UTC)
    seed_opportunity(ledger_service, opportunity_id=opportunity_id, category=category)
    policy = seed_policy_decision(
        ledger_service,
        policy_decision_id=f"policy_{opportunity_id}",
        opportunity_id=opportunity_id,
    )
    tos = seed_tos_legal_check(
        ledger_service,
        tos_legal_check_id=f"tos_{opportunity_id}",
        opportunity_id=opportunity_id,
    )
    evidence = seed_evidence_record(
        ledger_service,
        evidence_id=f"artifact_{opportunity_id}",
        related_record_id=opportunity_id,
    )
    budget = seed_budget_plan(
        ledger_service,
        budget_plan_id=f"budget_{opportunity_id}",
        opportunity_id=opportunity_id,
        policy_decision_id=policy.policy_decision_id,
        tos_legal_check_id=tos.tos_legal_check_id,
        expected_gross_revenue_usd=expected_amount,
    )
    review = ExperimentReviewer(archive_config, ledger_service).review(
        ExperimentReviewRequest(
            opportunity_id=opportunity_id,
            budget_plan_id=budget.budget_plan_id,
            review_reason="integration_metrics_history",
            current_date=current,
            revenue_usd=revenue_usd,
            time_spent_hours=2.0,
            success_metric_met=revenue_usd >= expected_amount,
            evidence_archive_ids=[evidence.evidence_id],
        )
    )
    observations: list[ReconciliationObservation] = []
    if observed_amount is not None:
        observations.append(
            ReconciliationObservation(
                observation_id=f"obs_{opportunity_id}",
                source_type="receipt",
                reference_id=f"receipt_{opportunity_id}",
                amount=observed_amount,
                currency_or_asset="USD",
                observed_at=current,
                counterparty="Example Vendor",
                evidence_archive_id=evidence.evidence_id,
            )
        )
    reconciliation = RevenueReconciler(archive_config, ledger_service).reconcile(
        RevenueReconciliationRequest(
            opportunity_id=opportunity_id,
            expected_amount=expected_amount,
            currency_or_asset="USD",
            current_date=current,
            expected_date=datetime(2026, 1, 2, tzinfo=UTC),
            observations=observations,
            evidence_archive_ids=[evidence.evidence_id],
        )
    )
    summary = StrategyMemorySummarizer(archive_config, ledger_service).summarize(
        StrategyMemorySummaryRequest(
            opportunity_id=opportunity_id,
            experiment_review_id=review.experiment_review_id,
            scope="opportunity",
            net_usd=review.net_usd,
            roi_percent=review.roi_percent,
            time_spent_hours=2.0,
            reconciliation_status=reconciliation.status,
            counterparty_risk_tier=None,
            evidence_archive_ids=reconciliation.evidence_archive_ids,
        )
    )
    return {
        "opportunity_id": opportunity_id,
        "policy": policy,
        "tos": tos,
        "budget": budget,
        "evidence": evidence,
        "review": review,
        "reconciliation": reconciliation,
        "summary": summary,
    }
