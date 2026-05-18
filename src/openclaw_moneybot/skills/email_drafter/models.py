"""Models for draft-only email generation."""

from __future__ import annotations

from pydantic import Field, HttpUrl, field_validator, model_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import EmailDraftRecord


class EmailDraftRequest(MoneyBotModel):
    """Request for a draft email."""

    opportunity_id: str | None = None
    related_experiment_id: str | None = None
    purpose: str
    recipient_name: str | None = None
    recipient_email: str
    recipient_organization: str | None = None
    context_summary: str
    source_url: HttpUrl | None = None
    policy_decision_id: str | None = None
    policy_decision: str | None = None
    tos_legal_check_id: str | None = None
    tos_legal_decision: str | None = None
    allowed_claims: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    tone: str = "concise"
    requested_call_to_action: str
    mode: str = "draft_only"
    sender_display_name: str = "OpenClaw MoneyBot"
    sender_email: str = "bot@example.com"
    automation_disclosure_required: bool = False
    prior_thread_summary: str | None = None
    recipient_source_url: HttpUrl | None = None
    max_followups: int = Field(default=1, ge=0, le=1)

    @model_validator(mode="after")
    def validate_request(self) -> EmailDraftRequest:
        """Enforce draft-only and basic preconditions."""
        if self.mode != "draft_only":
            msg = "Only draft_only mode is supported in v1."
            raise ValueError(msg)
        if not self.context_summary:
            msg = "context_summary is required."
            raise ValueError(msg)
        if self.opportunity_id is None and self.related_experiment_id is None:
            msg = "An opportunity_id or related_experiment_id is required."
            raise ValueError(msg)
        outbound_purposes = {"proposal", "bounty_application", "vendor_question"}
        if self.purpose in outbound_purposes and self.policy_decision_id is None:
            msg = "policy_decision_id is required for outbound business drafts."
            raise ValueError(msg)
        return self

    @field_validator("recipient_email", "sender_email")
    @classmethod
    def validate_email_address(cls, value: str) -> str:
        """Enforce a minimal single-recipient email format without extra deps."""
        if value.count("@") != 1 or value.startswith("@") or value.endswith("@"):
            msg = "Invalid email address."
            raise ValueError(msg)
        local_part, domain = value.split("@", 1)
        if not local_part or "." not in domain or domain.startswith(".") or domain.endswith("."):
            msg = "Invalid email address."
            raise ValueError(msg)
        return value


class EmailDraftResult(MoneyBotModel):
    """Structured email draft output."""

    email_draft_id: str
    mode: str
    to: str
    subject: str
    body: str
    risk_flags: list[str] = Field(default_factory=list)
    compliance_notes: list[str] = Field(default_factory=list)
    requires_human_review: bool = False
    ledger_record: EmailDraftRecord
    evidence_archive_ids: list[str] = Field(default_factory=list)
    template_name: str
    template_version: str = "v1"
    generated_at: str
