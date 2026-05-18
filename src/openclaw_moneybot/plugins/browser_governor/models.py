"""Models for the browser governor service."""

from __future__ import annotations

from pydantic import Field, HttpUrl

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.types import ActionType


class BrowserActionRequest(MoneyBotModel):
    """Preflight request for a governed browser action."""

    action_id: str
    opportunity_id: str
    policy_decision_id: str
    action_type: ActionType
    profile_id: str
    target_url: HttpUrl
    purpose: str
    before_page_text: str = Field(min_length=1)
    uses_personal_account: bool = False
    requires_kyc: bool = False
    attempts_captcha_bypass: bool = False
    uses_bot_evasion: bool = False
    mass_signup: bool = False
    scraping_against_terms: bool = False
    spend_request_id: str | None = None


class BrowserActionCompletionRequest(MoneyBotModel):
    """Completion record for a governed browser action."""

    action_id: str
    opportunity_id: str
    after_page_text: str = Field(min_length=1)
    result_summary: str
    success: bool


class BrowserActionResult(MoneyBotModel):
    """Outcome of browser-governor prepare or complete work."""

    status: str
    reason: str | None = None
    audit_record_id: str
    before_evidence_id: str | None = None
    after_evidence_id: str | None = None
