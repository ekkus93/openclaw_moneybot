"""Models for TOS/legal checking."""

from __future__ import annotations

from pydantic import Field, HttpUrl, JsonValue, model_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import TosLegalCheck


class TosLegalCheckRequest(MoneyBotModel):
    """Request for deterministic TOS/legal review."""

    opportunity_id: str
    opportunity_name: str
    source_url: HttpUrl
    rules_url: HttpUrl | None = None
    proposed_action: str
    platform_name: str
    counterparty: str | None = None
    spend_amount_usd: float | None = Field(default=None, ge=0)
    expected_revenue_usd: float | None = Field(default=None, ge=0)
    evidence_text: str | None = None
    evidence_archive_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_evidence_source(self) -> TosLegalCheckRequest:
        """Require at least one evidence source."""
        if self.evidence_text is None and not self.evidence_archive_ids and self.rules_url is None:
            msg = "At least one source of rules or evidence is required."
            raise ValueError(msg)
        return self


class TosLegalCheckResult(MoneyBotModel):
    """Full TOS/legal checker output."""

    decision: str
    confidence: str
    platform_terms_summary: str
    legal_risk_summary: str
    tos_risk_summary: str
    red_flags: list[str] = Field(default_factory=list)
    required_mitigations: list[str] = Field(default_factory=list)
    required_records: list[str] = Field(default_factory=list)
    source_quotes_or_snippets: list[str] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    checker_version: str
    handoff_to_policy_guard: dict[str, JsonValue]
    ledger_record: TosLegalCheck
