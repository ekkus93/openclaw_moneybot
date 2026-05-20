"""Shared contracts and support code."""

from openclaw_moneybot.shared.bitcoin import (
    AddressValidationResult,
    normalize_btc_address_for_comparison,
    validate_btc_address,
)
from openclaw_moneybot.shared.config import (
    AppConfig,
    ArchiveConfig,
    BrowserGovernorConfig,
    EmailConfig,
    LedgerConfig,
    MoneyBotPolicyConfig,
    WalletGovernorConfig,
    load_app_config,
)
from openclaw_moneybot.shared.contracts import (
    BudgetPlan,
    EmailDraftRecord,
    EvidenceRecord,
    ExperimentReview,
    LedgerRecord,
    MoneyBotAction,
    Opportunity,
    PolicyDecision,
    SpendRequest,
    TosLegalCheck,
    WalletTransactionRecord,
)
from openclaw_moneybot.shared.errors import ErrorCode, MoneyBotError, MoneyBotErrorDetail
from openclaw_moneybot.shared.types import (
    BitcoinNetwork,
    SpendRequestStatus,
    WalletTransactionStatus,
)

__all__ = [
    "AppConfig",
    "ArchiveConfig",
    "AddressValidationResult",
    "BitcoinNetwork",
    "BrowserGovernorConfig",
    "BudgetPlan",
    "EmailConfig",
    "EmailDraftRecord",
    "ErrorCode",
    "EvidenceRecord",
    "ExperimentReview",
    "LedgerConfig",
    "LedgerRecord",
    "MoneyBotAction",
    "MoneyBotError",
    "MoneyBotErrorDetail",
    "MoneyBotPolicyConfig",
    "normalize_btc_address_for_comparison",
    "Opportunity",
    "PolicyDecision",
    "SpendRequest",
    "SpendRequestStatus",
    "TosLegalCheck",
    "WalletGovernorConfig",
    "WalletTransactionRecord",
    "WalletTransactionStatus",
    "validate_btc_address",
    "load_app_config",
]
