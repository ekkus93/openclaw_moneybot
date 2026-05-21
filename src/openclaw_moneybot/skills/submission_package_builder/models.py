"""Models for deterministic submission-package building."""

from __future__ import annotations

from pydantic import Field, HttpUrl, JsonValue

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord
from openclaw_moneybot.shared.types import SubmissionReadinessStatus


class SubmissionPackageBuildRequest(MoneyBotModel):
    """Request for deriving a bounded submission package."""

    opportunity_id: str
    opportunity_name: str
    rules_text: str
    source_url: HttpUrl | None = None
    policy_decision_id: str
    tos_legal_check_id: str
    budget_plan_id: str
    evidence_archive_ids: list[str] = Field(default_factory=list)
    mission_context: dict[str, JsonValue] = Field(default_factory=dict)


class SubmissionPackageBuildResult(MoneyBotModel):
    """Structured submission package result."""

    submission_package_id: str
    status: SubmissionReadinessStatus
    required_steps: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    required_artifacts: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    submission_url: str | None = None
    deadline: str | None = None
    quality_checks: list[str] = Field(default_factory=list)
    handoff_notes: list[str] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord
