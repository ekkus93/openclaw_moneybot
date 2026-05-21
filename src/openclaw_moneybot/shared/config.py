"""Configuration models and loaders."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import Field, ValidationError, ValidationInfo, field_validator

from openclaw_moneybot.shared.base import MoneyBotModel
from openclaw_moneybot.shared.bitcoin import normalize_btc_address_for_comparison
from openclaw_moneybot.shared.errors import ErrorCode, MoneyBotError, MoneyBotErrorDetail
from openclaw_moneybot.shared.types import ActionType, BitcoinNetwork, EmailMode


class MoneyBotPolicyConfig(MoneyBotModel):
    """Policy-related configuration."""

    policy_version: str
    blocked_categories: list[str]
    review_required_categories: list[str]
    allowed_action_types: list[ActionType] = Field(default_factory=lambda: list(ActionType))
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
    bitcoin_network: BitcoinNetwork = BitcoinNetwork.REGTEST
    blocked_destinations: list[str] = Field(default_factory=list)
    blocked_destination_labels: dict[str, str] = Field(default_factory=dict)
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

    @field_validator("blocked_destinations")
    @classmethod
    def normalize_blocked_destinations(cls, value: list[str]) -> list[str]:
        """Normalize blocklist entries for exact-match comparisons."""
        normalized: list[str] = []
        for destination in value:
            stripped = destination.strip()
            if stripped:
                normalized.append(normalize_btc_address_for_comparison(stripped))
        return normalized


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


class OperatorProfileStoreConfig(MoneyBotModel):
    """Local operator-profile storage configuration."""

    enabled: bool = False
    profile_path: Path = Path("config/operator_profile.json")
    max_export_fields: int = Field(default=32, gt=0)


class RulesSnapshotGatewayConfig(MoneyBotModel):
    """Rules snapshot gateway configuration."""

    enabled: bool = False
    allowed_hosts: list[str] = Field(default_factory=list)
    allowed_content_types: list[str] = Field(default_factory=lambda: ["text/plain", "text/html"])
    max_content_bytes: int = Field(default=200_000, gt=0)
    stale_after_hours: int = Field(default=24 * 7, gt=0)

    @field_validator("allowed_hosts")
    @classmethod
    def normalize_allowed_hosts(cls, value: list[str]) -> list[str]:
        return [host.strip().lower() for host in value if host.strip()]


class WalletObserverConfig(MoneyBotModel):
    """Read-only wallet observer configuration."""

    enabled: bool = False
    allowed_assets: list[str] = Field(default_factory=lambda: ["BTC"])
    read_only: bool = True


class InboxObserverConfig(MoneyBotModel):
    """Dedicated bot-mailbox observation configuration."""

    enabled: bool = False
    mailbox_address: str = "bot@example.com"
    allowed_attachment_extensions: list[str] = Field(
        default_factory=lambda: [".txt", ".json", ".csv", ".md", ".png", ".jpg", ".jpeg"]
    )
    max_body_excerpt_chars: int = Field(default=500, gt=0)
    max_attachment_bytes: int = Field(default=1_000_000, gt=0)

    @field_validator("mailbox_address")
    @classmethod
    def validate_mailbox_address(cls, value: str) -> str:
        if value.count("@") != 1:
            msg = "mailbox_address must be a dedicated bot mailbox."
            raise ValueError(msg)
        domain = value.split("@", 1)[1].lower()
        if domain in {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"}:
            msg = "mailbox_address must not point to a personal mailbox provider."
            raise ValueError(msg)
        return value

    @field_validator("allowed_attachment_extensions")
    @classmethod
    def normalize_attachment_extensions(cls, value: list[str]) -> list[str]:
        normalized = [extension.lower() for extension in value if extension]
        if not normalized:
            msg = "allowed_attachment_extensions must contain at least one extension."
            raise ValueError(msg)
        return normalized


class OpportunityIndexConfig(MoneyBotModel):
    """Local opportunity-index configuration."""

    enabled: bool = False
    index_path: Path = Path("data/opportunity_index.json")
    max_results: int = Field(default=25, gt=0)


class ArtifactRendererConfig(MoneyBotModel):
    """Artifact renderer configuration."""

    enabled: bool = False
    template_root: Path = Path("templates/moneybot")
    render_root: Path = Path("workspace/rendered_artifacts")
    max_bundle_files: int = Field(default=50, gt=0)


class DeadlineSchedulerConfig(MoneyBotModel):
    """Deadline scheduler configuration."""

    enabled: bool = False
    schedule_path: Path = Path("data/deadline_schedule.json")
    default_timezone: str = "UTC"
    max_items: int = Field(default=500, gt=0)


class DownloadQuarantineConfig(MoneyBotModel):
    """Quarantine pipeline configuration."""

    enabled: bool = False
    quarantine_root: Path = Path("workspace/quarantine")
    allowed_hosts: list[str] = Field(default_factory=list)
    allowed_extensions: list[str] = Field(
        default_factory=lambda: [
            ".txt",
            ".json",
            ".csv",
            ".md",
            ".html",
            ".png",
            ".jpg",
            ".jpeg",
            ".pdf",
            ".zip",
        ]
    )
    allowed_mime_types: list[str] = Field(
        default_factory=lambda: [
            "text/plain",
            "application/json",
            "text/csv",
            "text/markdown",
            "text/html",
            "image/png",
            "image/jpeg",
            "application/pdf",
            "application/zip",
        ]
    )
    max_file_bytes: int = Field(default=2_000_000, gt=0)
    max_archive_entries: int = Field(default=100, gt=0)
    max_nested_bytes: int = Field(default=5_000_000, gt=0)

    @field_validator("allowed_hosts", "allowed_extensions", "allowed_mime_types")
    @classmethod
    def normalize_string_lists(cls, value: list[str]) -> list[str]:
        return [item.strip().lower() for item in value if item.strip()]


class CounterpartySnapshotConfig(MoneyBotModel):
    """Public counterparty snapshot configuration."""

    enabled: bool = False
    allowed_hosts: list[str] = Field(default_factory=list)
    allowed_content_types: list[str] = Field(default_factory=lambda: ["text/plain", "text/html"])
    max_content_bytes: int = Field(default=200_000, gt=0)
    freshness_days: int = Field(default=30, gt=0)

    @field_validator("allowed_hosts")
    @classmethod
    def normalize_counterparty_hosts(cls, value: list[str]) -> list[str]:
        return [host.strip().lower() for host in value if host.strip()]


class MetricsExportConfig(MoneyBotModel):
    """Metrics export plugin configuration."""

    enabled: bool = False
    export_root: Path = Path("exports")
    max_rows: int = Field(default=1_000, gt=0)


class AppConfig(MoneyBotModel):
    """Top-level MoneyBot configuration."""

    policy: MoneyBotPolicyConfig
    ledger: LedgerConfig
    archive: ArchiveConfig
    wallet_governor: WalletGovernorConfig
    email: EmailConfig
    browser_governor: BrowserGovernorConfig = Field(default_factory=BrowserGovernorConfig)
    operator_profile_store: OperatorProfileStoreConfig = Field(
        default_factory=OperatorProfileStoreConfig
    )
    rules_snapshot_gateway: RulesSnapshotGatewayConfig = Field(
        default_factory=RulesSnapshotGatewayConfig
    )
    wallet_observer: WalletObserverConfig = Field(default_factory=WalletObserverConfig)
    inbox_observer: InboxObserverConfig = Field(default_factory=InboxObserverConfig)
    opportunity_index: OpportunityIndexConfig = Field(default_factory=OpportunityIndexConfig)
    artifact_renderer: ArtifactRendererConfig = Field(default_factory=ArtifactRendererConfig)
    deadline_scheduler: DeadlineSchedulerConfig = Field(default_factory=DeadlineSchedulerConfig)
    download_quarantine: DownloadQuarantineConfig = Field(default_factory=DownloadQuarantineConfig)
    counterparty_snapshot: CounterpartySnapshotConfig = Field(
        default_factory=CounterpartySnapshotConfig
    )
    metrics_export: MetricsExportConfig = Field(default_factory=MetricsExportConfig)


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
        normalized_errors = json.loads(json.dumps(error.errors(include_url=False), default=str))
        detail = MoneyBotErrorDetail(
            error_code=ErrorCode.INVALID_CONFIG,
            message="Config validation failed",
            recoverable=False,
            safe_for_user=True,
            details={"errors": normalized_errors},
        )
        raise MoneyBotError(detail) from error
