"""Configuration models and loaders."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import Field, ValidationError, field_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.errors import ErrorCode, MoneyBotError, MoneyBotErrorDetail
from openclaw_moneybot.shared.types import ActionType, EmailMode


class MoneyBotPolicyConfig(MoneyBotModel):
    """Policy-related configuration."""

    policy_version: str
    blocked_categories: list[str]
    review_required_categories: list[str]
    allowed_action_types: list[ActionType] = Field(
        default_factory=lambda: list(ActionType)
    )
    max_single_spend_usd: float = Field(gt=0)
    max_daily_spend_usd: float = Field(gt=0)
    max_weekly_spend_usd: float = Field(gt=0)


class LedgerConfig(MoneyBotModel):
    """Ledger storage configuration."""

    database_path: Path
    export_directory: Path | None = None


class ArchiveConfig(MoneyBotModel):
    """Evidence archive configuration."""

    base_directory: Path
    redact_secrets: bool = True
    allowed_source_roots: list[Path] = Field(default_factory=list)
    max_artifact_bytes: int = Field(default=1_000_000, gt=0)


class WalletGovernorConfig(MoneyBotModel):
    """Shared wallet governor configuration."""

    base_url: str
    timeout_seconds: float = Field(default=10.0, gt=0)
    spend_enabled: bool = False
    allowed_assets: list[str] = Field(default_factory=lambda: ["BTC"])

    @field_validator("base_url")
    @classmethod
    def ensure_local_url(cls, value: str) -> str:
        """Allow local-only base URLs by default."""
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"}:
            msg = "base_url must be an http or https URL"
            raise ValueError(msg)
        if parsed.hostname not in {"127.0.0.1", "localhost"}:
            msg = "base_url must point to localhost or 127.0.0.1"
            raise ValueError(msg)
        return value


class EmailConfig(MoneyBotModel):
    """Email mode configuration."""

    mode: EmailMode = EmailMode.DRAFT_ONLY
    max_outbound_per_day: int = Field(default=0, ge=0)


class AppConfig(MoneyBotModel):
    """Top-level MoneyBot configuration."""

    policy: MoneyBotPolicyConfig
    ledger: LedgerConfig
    archive: ArchiveConfig
    wallet_governor: WalletGovernorConfig
    email: EmailConfig


def load_app_config(path: Path) -> AppConfig:
    """Load an application config from YAML."""
    if not path.exists():
        detail = MoneyBotErrorDetail(
            error_code=ErrorCode.MISSING_CONFIG,
            message=f"Config file does not exist: {path}",
            recoverable=False,
            safe_for_user=True,
            details={"path": str(path)},
        )
        raise MoneyBotError(detail)

    raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, dict):
        detail = MoneyBotErrorDetail(
            error_code=ErrorCode.INVALID_CONFIG,
            message="Config root must be a mapping",
            recoverable=False,
            safe_for_user=True,
        )
        raise MoneyBotError(detail)

    try:
        return AppConfig.model_validate(raw_data)
    except ValidationError as error:
        normalized_errors = json.loads(
            json.dumps(error.errors(include_url=False), default=str)
        )
        detail = MoneyBotErrorDetail(
            error_code=ErrorCode.INVALID_CONFIG,
            message="Config validation failed",
            recoverable=False,
            safe_for_user=True,
            details={"errors": normalized_errors},
        )
        raise MoneyBotError(detail) from error
