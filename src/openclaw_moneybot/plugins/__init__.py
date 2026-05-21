"""MoneyBot plugin and service implementations."""

from openclaw_moneybot.plugins.browser_governor import (
    BrowserActionCompletionRequest,
    BrowserActionRequest,
    BrowserActionResult,
    BrowserGovernorService,
)
from openclaw_moneybot.plugins.email_governor import (
    EmailGovernorService,
    EmailReplyRequest,
    EmailReplyResult,
    EmailSendRequest,
    EmailSendResult,
    FakeEmailTransport,
)
from openclaw_moneybot.plugins.inbox_observer_plugin import (
    InboxAttachment,
    InboxMessageInput,
    InboxObservationRequest,
    InboxObservationResult,
    InboxObserverPlugin,
)
from openclaw_moneybot.plugins.operator_profile_store import (
    OperatorProfileStore,
    OperatorProfileStoreReadRequest,
    OperatorProfileStoreReadResult,
    OperatorProfileStoreWriteRequest,
    OperatorProfileStoreWriteResult,
)
from openclaw_moneybot.plugins.rules_snapshot_gateway import (
    RulesSnapshotCaptureRequest,
    RulesSnapshotCaptureResult,
    RulesSnapshotGateway,
)
from openclaw_moneybot.plugins.wallet_observer_plugin import (
    WalletBalanceObservationRequest,
    WalletBalanceObservationResult,
    WalletObserverPlugin,
    WalletTransactionObservationRequest,
    WalletTransactionObservationResult,
)

__all__ = [
    "BrowserActionCompletionRequest",
    "BrowserActionRequest",
    "BrowserActionResult",
    "BrowserGovernorService",
    "EmailGovernorService",
    "EmailReplyRequest",
    "EmailReplyResult",
    "EmailSendRequest",
    "EmailSendResult",
    "FakeEmailTransport",
    "InboxAttachment",
    "InboxMessageInput",
    "InboxObservationRequest",
    "InboxObservationResult",
    "InboxObserverPlugin",
    "OperatorProfileStore",
    "OperatorProfileStoreReadRequest",
    "OperatorProfileStoreReadResult",
    "OperatorProfileStoreWriteRequest",
    "OperatorProfileStoreWriteResult",
    "RulesSnapshotCaptureRequest",
    "RulesSnapshotCaptureResult",
    "RulesSnapshotGateway",
    "WalletBalanceObservationRequest",
    "WalletBalanceObservationResult",
    "WalletObserverPlugin",
    "WalletTransactionObservationRequest",
    "WalletTransactionObservationResult",
]
