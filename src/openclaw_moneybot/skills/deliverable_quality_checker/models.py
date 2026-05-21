"""Models for deliverable quality checking."""

from __future__ import annotations

from pydantic import Field

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord
from openclaw_moneybot.shared.types import DeliverableValidationOutcome


class DeliverableArtifact(MoneyBotModel):
    """One deliverable or proof artifact prepared for submission."""

    artifact_name: str
    content_text: str | None = None
    evidence_archive_id: str | None = None
    expected_sha256: str | None = None
    actual_sha256: str | None = None


class DeliverableQualityCheckRequest(MoneyBotModel):
    """Request for bounded deliverable validation."""

    opportunity_id: str
    submission_package_id: str
    required_fields: list[str] = Field(default_factory=list)
    required_artifacts: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    field_values: dict[str, str] = Field(default_factory=dict)
    artifacts: list[DeliverableArtifact] = Field(default_factory=list)
    expected_reference_ids: list[str] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)


class DeliverableQualityCheckResult(MoneyBotModel):
    """Structured deliverable quality result."""

    deliverable_quality_id: str
    status: DeliverableValidationOutcome
    missing_items: list[str] = Field(default_factory=list)
    invalid_items: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    passed_checks: list[str] = Field(default_factory=list)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord
