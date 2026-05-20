"""Configuration models and loaders."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import Field, ValidationError, ValidationInfo, field_validator

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
    archive_root: Path | None = None

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
    max_per_domain_per_day: int = Field(default=1, ge=0)
    max_followups_per_thread: int = Field(default=1, ge=0, le=1)
    allowed_sender_emails: list[str] = Field(default_factory=lambda: ["bot@example.com"])
    require_opt_out_for_cold_outreach: bool = True

    @field_validator("allowed_sender_emails")
    @classmethod
    def validate_allowed_sender_emails(cls, value: list[str]) -> list[str]:
        """Require at least one dedicated sender address."""
        if not value:
            msg = "allowed_sender_emails must contain at least one bot-owned sender."
            raise ValueError(msg)
        return value

    @field_validator("max_outbound_per_day")
    @classmethod
    def validate_send_mode_limit(cls, value: int, info: ValidationInfo) -> int:
        """Require a positive daily cap when capped send mode is enabled."""
        if (
            isinstance(info.data, dict)
            and info.data.get("mode") == EmailMode.CAPPED_SEND
            and value <= 0
        ):
            msg = "max_outbound_per_day must be positive when mode is capped_send."
            raise ValueError(msg)
        return value


class BrowserGovernorConfig(MoneyBotModel):
    """Browser governor configuration."""

    enabled: bool = False
    allowed_profile_ids: list[str] = Field(default_factory=lambda: ["moneybot-default"])

    @field_validator("allowed_profile_ids")
    @classmethod
    def validate_allowed_profile_ids(cls, value: list[str]) -> list[str]:
        """Require at least one bot-owned profile identifier."""
        if not value:
            msg = "allowed_profile_ids must contain at least one bot-owned profile."
            raise ValueError(msg)
        return value


class AppConfig(MoneyBotModel):
    """Top-level MoneyBot configuration."""

    policy: MoneyBotPolicyConfig
    ledger: LedgerConfig
    archive: ArchiveConfig
    wallet_governor: WalletGovernorConfig
    email: EmailConfig
    browser_governor: BrowserGovernorConfig = Field(default_factory=BrowserGovernorConfig)


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
