"""Email governor package."""

from openclaw_moneybot.plugins.email_governor.models import (
    EmailReplyRequest,
    EmailReplyResult,
    EmailSendRequest,
    EmailSendResult,
)
from openclaw_moneybot.plugins.email_governor.service import (
    EmailGovernorService,
    FakeEmailTransport,
)

__all__ = [
    "EmailGovernorService",
    "EmailReplyRequest",
    "EmailReplyResult",
    "EmailSendRequest",
    "EmailSendResult",
    "FakeEmailTransport",
]
