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


class EmailMode(StrEnum):
    """Email operating modes."""

    DRAFT_ONLY = "draft_only"
    CAPPED_SEND = "capped_send"


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
