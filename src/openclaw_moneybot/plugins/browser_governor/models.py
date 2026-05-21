"""Models for the browser governor service."""

from __future__ import annotations

from pydantic import Field, HttpUrl, model_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.types import ActionType


class BrowserGovernedActionRequest(MoneyBotModel):
    """Shared metadata for a governed browser action."""

    action_id: str
    opportunity_id: str
    policy_decision_id: str
    action_type: ActionType
    profile_id: str
    target_url: HttpUrl
    purpose: str
    uses_personal_account: bool = False
    requires_kyc: bool = False
    attempts_captcha_bypass: bool = False
    uses_bot_evasion: bool = False
    mass_signup: bool = False
    scraping_against_terms: bool = False
    spend_request_id: str | None = None


class BrowserActionRequest(BrowserGovernedActionRequest):
    """Preflight request for a governed browser action."""

    before_page_text: str = Field(min_length=1)


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


class BrowserExecutionStep(MoneyBotModel):
    """One bounded Playwright browser step."""

    kind: str
    selector: str | None = None
    text: str | None = None
    timeout_ms: int = Field(default=5_000, gt=0, le=120_000)

    @model_validator(mode="after")
    def validate_step_fields(self) -> BrowserExecutionStep:
        """Require selectors and text only for the operations that need them."""
        kind = self.kind.strip().lower()
        if kind not in {"fill", "click", "wait_for_text"}:
            msg = "kind must be one of: fill, click, wait_for_text."
            raise ValueError(msg)
        self.kind = kind
        if kind == "fill":
            if self.selector is None or not self.selector.strip():
                msg = "fill steps require a selector."
                raise ValueError(msg)
            if self.text is None:
                msg = "fill steps require text."
                raise ValueError(msg)
        elif kind == "click":
            if self.selector is None or not self.selector.strip():
                msg = "click steps require a selector."
                raise ValueError(msg)
            if self.text is not None:
                msg = "click steps do not accept text."
                raise ValueError(msg)
        elif self.text is None:
            msg = "wait_for_text steps require text."
            raise ValueError(msg)
        return self


class BrowserExecutionRequest(BrowserGovernedActionRequest):
    """Structured request for bounded Playwright+Firefox execution."""

    steps: list[BrowserExecutionStep] = Field(min_length=1)


class BrowserExecutionResult(BrowserActionResult):
    """Outcome of one automated browser execution."""

    final_url: str | None = None
    result_summary: str | None = None
