"""Read-only inbox observation plugin."""

from openclaw_moneybot.plugins.inbox_observer_plugin.models import (
    InboxAttachment,
    InboxMessageInput,
    InboxMessageObservationResult,
    InboxObservationRequest,
    InboxObservationResult,
    InboxThreadSummary,
)
from openclaw_moneybot.plugins.inbox_observer_plugin.service import InboxObserverPlugin

__all__ = [
    "InboxAttachment",
    "InboxMessageInput",
    "InboxMessageObservationResult",
    "InboxObservationRequest",
    "InboxObservationResult",
    "InboxObserverPlugin",
    "InboxThreadSummary",
]
