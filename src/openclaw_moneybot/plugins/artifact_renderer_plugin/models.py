"""Models for deterministic artifact rendering."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.contracts import LedgerRecord
from openclaw_moneybot.shared.types import ArtifactRenderOutcome


class ArtifactRenderRequest(MoneyBotModel):
    """Render request for a bounded local template."""

    related_record_id: str
    template_name: str
    output_subdir: str = "default"
    field_values: dict[str, str] = Field(default_factory=dict)
    evidence_archive_ids: list[str] = Field(default_factory=list)


class ArtifactRenderResult(MoneyBotModel):
    """Rendered artifact bundle metadata."""

    render_id: str
    outcome: ArtifactRenderOutcome
    rendered_paths: list[Path] = Field(default_factory=list)
    manifest_path: Path
    checksums: dict[str, str] = Field(default_factory=dict)
    evidence_archive_ids: list[str] = Field(default_factory=list)
    ledger_record: LedgerRecord
