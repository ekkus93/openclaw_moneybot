from enum import StrEnum


class ActionType(StrEnum):
    """Supported MoneyBot action categories."""

    RESEARCH = "research"
    EMAIL = "email"
    BROWSER_SUBMIT = "browser_submit"
    ACCOUNT_CREATE = "account_create"
    SPEND = "spend"
    WALLET_TRANSFER = "wallet_transfer"
    CODE_BUILD = "code_build"
    PUBLISH = "publish"
    PURCHASE = "purchase"
    OTHER = "other"


class PolicyDecisionType(StrEnum):
    """Policy outcomes."""

    ALLOW = "allow"
    BLOCK = "block"
    NEEDS_REVIEW = "needs_review"


class TosDecisionType(StrEnum):
    """Terms/legal outcomes."""

    PROCEED = "proceed"
    REJECT = "reject"
    HUMAN_REVIEW = "human_review"


class BudgetDecisionType(StrEnum):
    """Budget-plan outcomes."""

    REJECT = "reject"
    SIMULATE = "simulate"
    EXECUTE_REQUEST = "execute_request"
    HUMAN_REVIEW = "human_review"


class ReviewDecisionType(StrEnum):
    """Experiment review outcomes."""

    CONTINUE = "continue"
    STOP = "stop"
    RETRY_WITH_CHANGES = "retry_with_changes"
    HUMAN_REVIEW = "human_review"
    BLOCK_CATEGORY = "block_category"


class RiskLevel(StrEnum):
    """Shared risk levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConfidenceLevel(StrEnum):
    """Confidence levels used by review and analysis skills."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EligibilityDecisionType(StrEnum):
    """Eligibility-check outcomes."""

    ELIGIBLE = "eligible"
    BLOCKED = "blocked"
    NEEDS_REVIEW = "needs_review"
    INCOMPLETE = "incomplete"


class TermsChangeSeverity(StrEnum):
    """Severity levels for terms-change monitoring."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCK = "block"


class SubmissionReadinessStatus(StrEnum):
    """Submission-package readiness outcomes."""

    READY = "ready"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"


class ReconciliationStatus(StrEnum):
    """Expected-versus-observed payout reconciliation outcomes."""

    MATCHED = "matched"
    PARTIAL = "partial"
    MISSING = "missing"
    LATE = "late"
    UNDERPAID = "underpaid"
    OVERPAID_NEEDS_REVIEW = "overpaid_needs_review"
    AMBIGUOUS_NEEDS_REVIEW = "ambiguous_needs_review"


class CounterpartyRiskTier(StrEnum):
    """Counterparty risk buckets."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DuplicateConfidence(StrEnum):
    """Confidence for duplicate-opportunity detection."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class QueuePriority(StrEnum):
    """Queue-planning priorities."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    DEFER = "defer"


class DeliverableValidationOutcome(StrEnum):
    """Deliverable quality-check outcomes."""

    PASSED = "passed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class PayoutFollowupRecommendation(StrEnum):
    """Allowed payout follow-up recommendations."""

    WAIT = "wait"
    GATHER_MISSING_PROOF = "gather_missing_proof"
    DRAFT_FOLLOWUP = "draft_followup"
    HUMAN_REVIEW = "human_review"
    STOP_AND_RECORD_LOSS = "stop_and_record_loss"


class StrategyLessonCategory(StrEnum):
    """Structured lesson categories for reusable strategy memory."""

    SCOUTING = "scouting"
    BUDGETING = "budgeting"
    COUNTERPARTY = "counterparty"
    QUEUE = "queue"
    EXECUTION = "execution"
    PAYOUT = "payout"
    EVIDENCE = "evidence"
    RISK = "risk"


class ProfileAttributeAvailability(StrEnum):
    """Availability states for operator-profile fields."""

    CONFIGURED = "configured"
    UNKNOWN = "unknown"
    REDACTED = "redacted"


class SnapshotFreshness(StrEnum):
    """Freshness classification for captured snapshots."""

    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class InboundMessageClassification(StrEnum):
    """Deterministic inbound mailbox classifications."""

    PAYOUT_NOTICE = "payout_notice"
    POSITIVE_RESPONSE = "positive_response"
    REJECTION = "rejection"
    OPT_OUT = "opt_out"
    COMPLAINT = "complaint"
    UNKNOWN = "unknown"


class OpportunitySimilarity(StrEnum):
    """Similarity bands for indexed opportunity comparisons."""

    EXACT = "exact"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ArtifactRenderOutcome(StrEnum):
    """Deterministic artifact-rendering outcomes."""

    RENDERED = "rendered"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class DeadlineState(StrEnum):
    """Normalized deadline tracking states."""

    UPCOMING = "upcoming"
    OVERDUE = "overdue"
    COOLING_DOWN = "cooling_down"
    UNCERTAIN = "uncertain"
    CONFLICTING = "conflicting"


class QuarantineScanStatus(StrEnum):
    """Safe quarantine pipeline states."""

    STAGED = "staged"
    REJECTED = "rejected"
    PROMOTED = "promoted"
    NEEDS_REVIEW = "needs_review"


class CounterpartyEvidenceTier(StrEnum):
    """Evidence quality tiers for public counterparty snapshots."""

    STRONG = "strong"
    PARTIAL = "partial"
    WEAK = "weak"
    INCOMPLETE = "incomplete"


class ExportJobStatus(StrEnum):
    """Metrics export lifecycle states."""

    COMPLETED = "completed"
    REJECTED = "rejected"
    BOUNDED = "bounded"


class EmailMode(StrEnum):
    """Email operating modes."""

    DRAFT_ONLY = "draft_only"
    CAPPED_SEND = "capped_send"


class BitcoinNetwork(StrEnum):
    """Supported Bitcoin address networks."""

    MAINNET = "mainnet"
    TESTNET = "testnet"
    REGTEST = "regtest"
    SIGNET = "signet"


class SpendRequestStatus(StrEnum):
    """Canonical spend-request lifecycle states."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENDING = "sending"
    SENT = "sent"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WalletTransactionStatus(StrEnum):
    """Wallet transaction lifecycle states."""

    SENDING = "sending"
    SENT = "sent"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RecordType(StrEnum):
    """Ledger-linked record types."""

    OPPORTUNITY = "opportunity"
    POLICY_DECISION = "policy_decision"
    TOS_LEGAL_CHECK = "tos_legal_check"
    BUDGET_PLAN = "budget_plan"
    SPEND_REQUEST = "spend_request"
    WALLET_TRANSACTION = "wallet_transaction"
    EMAIL_DRAFT = "email_draft"
    EVIDENCE = "evidence"
    EXPERIMENT_REVIEW = "experiment_review"
    AUDIT_EVENT = "audit_event"
    ACCOUNT_ELIGIBILITY = "account_eligibility"
    TERMS_CHANGE = "terms_change"
    SUBMISSION_PACKAGE = "submission_package"
    PAYOUT_RECONCILIATION = "payout_reconciliation"
    COUNTERPARTY_PROFILE = "counterparty_profile"
    DUPLICATE_ANALYSIS = "duplicate_analysis"
    QUEUE_PLAN = "queue_plan"
    DELIVERABLE_QUALITY = "deliverable_quality"
    FOLLOWUP_PLAN = "followup_plan"
    STRATEGY_SUMMARY = "strategy_summary"
    OPERATOR_PROFILE_SNAPSHOT = "operator_profile_snapshot"
    RULE_SNAPSHOT = "rule_snapshot"
    WALLET_OBSERVATION = "wallet_observation"
    INBOX_OBSERVATION = "inbox_observation"
    OPPORTUNITY_INDEX = "opportunity_index"
    RENDERED_ARTIFACT = "rendered_artifact"
    DEADLINE_EVENT = "deadline_event"
    QUARANTINE_SCAN = "quarantine_scan"
    COUNTERPARTY_SNAPSHOT = "counterparty_snapshot"
    METRICS_EXPORT = "metrics_export"
