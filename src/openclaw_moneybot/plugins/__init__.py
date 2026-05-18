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
]
