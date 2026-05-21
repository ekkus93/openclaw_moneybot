"""MoneyBot plugin and service implementations."""

from openclaw_moneybot.plugins.artifact_renderer_plugin import (
    ArtifactRendererPlugin,
    ArtifactRenderRequest,
    ArtifactRenderResult,
)
from openclaw_moneybot.plugins.browser_governor import (
    BrowserActionCompletionRequest,
    BrowserActionRequest,
    BrowserActionResult,
    BrowserGovernorService,
)
from openclaw_moneybot.plugins.deadline_scheduler_plugin import (
    DeadlineQueryRequest,
    DeadlineQueryResult,
    DeadlineScheduleRequest,
    DeadlineScheduleResult,
    DeadlineSchedulerPlugin,
)
from openclaw_moneybot.plugins.download_quarantine_plugin import (
    DownloadQuarantinePlugin,
    QuarantineIngestRequest,
    QuarantineIngestResult,
    QuarantinePromoteRequest,
    QuarantinePromoteResult,
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
from openclaw_moneybot.plugins.opportunity_index_plugin import (
    OpportunityIndexEntry,
    OpportunityIndexPlugin,
    OpportunityIndexRefreshResult,
    OpportunitySimilarityMatch,
    OpportunitySimilarityQueryRequest,
    OpportunitySimilarityQueryResult,
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
    "ArtifactRenderRequest",
    "ArtifactRenderResult",
    "ArtifactRendererPlugin",
    "BrowserActionCompletionRequest",
    "BrowserActionRequest",
    "BrowserActionResult",
    "BrowserGovernorService",
    "DeadlineQueryRequest",
    "DeadlineQueryResult",
    "DeadlineScheduleRequest",
    "DeadlineScheduleResult",
    "DeadlineSchedulerPlugin",
    "DownloadQuarantinePlugin",
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
    "OpportunityIndexEntry",
    "OpportunityIndexPlugin",
    "OpportunityIndexRefreshResult",
    "OpportunitySimilarityMatch",
    "OpportunitySimilarityQueryRequest",
    "OpportunitySimilarityQueryResult",
    "QuarantineIngestRequest",
    "QuarantineIngestResult",
    "QuarantinePromoteRequest",
    "QuarantinePromoteResult",
    "RulesSnapshotCaptureRequest",
    "RulesSnapshotCaptureResult",
    "RulesSnapshotGateway",
    "WalletBalanceObservationRequest",
    "WalletBalanceObservationResult",
    "WalletObserverPlugin",
    "WalletTransactionObservationRequest",
    "WalletTransactionObservationResult",
]
