"""Models for bounded inbox observation."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord
from openclaw_moneybot.shared.types import InboundMessageClassification


class InboxAttachment(MoneyBotModel):
    """Metadata-only inbox attachment summary."""

    filename: str
    size_bytes: int = Field(ge=0)
    mime_type: str | None = None


class InboxMessageInput(MoneyBotModel):
    """One inbound message to normalize and classify."""

    message_id: str
    thread_id: str
    sender_email: str
    subject: str
    body: str
    received_at: datetime
    known_reference_ids: list[str] = Field(default_factory=list)
    attachments: list[InboxAttachment] = Field(default_factory=list)


class InboxObservationRequest(MoneyBotModel):
    """Batch observation request for one dedicated bot mailbox."""

    mailbox_address: str
    messages: list[InboxMessageInput] = Field(default_factory=list)


class InboxMessageObservationResult(MoneyBotModel):
    """Normalized result for one observed inbound message."""

    observation_id: str
    message_id: str
    thread_id: str
    classification: InboundMessageClassification
    linked_reference_ids: list[str] = Field(default_factory=list)
    attachment_actions: dict[str, str] = Field(default_factory=dict)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord


class InboxThreadSummary(MoneyBotModel):
    """Collapsed thread-level summary for follow-up logic."""

    thread_id: str
    classifications: list[InboundMessageClassification] = Field(default_factory=list)
    linked_reference_ids: list[str] = Field(default_factory=list)


class InboxObservationResult(MoneyBotModel):
    """Batch observation result."""

    messages: list[InboxMessageObservationResult] = Field(default_factory=list)
    thread_summaries: list[InboxThreadSummary] = Field(default_factory=list)
