"""Models for governed email sends and reply classification."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from openclaw_moneybot.shared.base import MoneyBotModel

RecipientSource = Literal[
    "direct_opportunity_contact",
    "bot_directory",
    "reply_thread",
    "manual_verified",
    "personal_import",
    "scraped_list",
]


class EmailSendRequest(MoneyBotModel):
    """A governed request to send one previously drafted email."""

    email_draft_id: str
    policy_decision_id: str
    sender_email: str
    thread_id: str
    recipient_source: RecipientSource
    current_date: datetime
    idempotency_key: str
    is_followup: bool = False
    is_cold_outreach: bool = False
    related_opportunity_id: str | None = None
    related_experiment_id: str | None = None

    @field_validator("sender_email")
    @classmethod
    def validate_sender_email(cls, value: str) -> str:
        """Enforce a simple single-address sender format."""
        if value.count("@") != 1 or value.startswith("@") or value.endswith("@"):
            msg = "Invalid sender_email."
            raise ValueError(msg)
        local_part, domain = value.split("@", 1)
        if not local_part or "." not in domain or domain.startswith(".") or domain.endswith("."):
            msg = "Invalid sender_email."
            raise ValueError(msg)
        return value


class EmailSendResult(MoneyBotModel):
    """Outcome of a governed email send attempt."""

    status: Literal["sent", "rejected"]
    reason: str | None = None
    message_id: str | None = None
    audit_record_id: str
    archive_evidence_id: str | None = None


class EmailReplyRequest(MoneyBotModel):
    """Classify one inbound reply tied to a governed thread."""

    thread_id: str
    sender_email: str
    recipient_email: str
    subject: str
    body: str
    current_date: datetime
    email_draft_id: str | None = None
    related_opportunity_id: str | None = None
    related_experiment_id: str | None = None


class EmailReplyResult(MoneyBotModel):
    """Structured inbound reply classification."""

    classification: Literal[
        "positive",
        "rejection",
        "opt_out",
        "complaint",
        "needs_review",
    ]
    audit_record_id: str
    archive_evidence_id: str
    notes: list[str] = Field(default_factory=list)
