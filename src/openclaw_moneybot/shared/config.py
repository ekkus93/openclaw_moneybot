"""Configuration models and loaders."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import Field, ValidationError, ValidationInfo, field_validator, model_validator

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
    execution_enabled: bool = False
    browser_engine: str = "firefox"
    headless: bool = True
    allowed_hosts: list[str] = Field(default_factory=list)
    profile_root: Path = Path("data/browser_profiles")
    default_timeout_ms: int = Field(default=10_000, gt=0, le=120_000)
    navigation_timeout_ms: int = Field(default=15_000, gt=0, le=120_000)
    max_steps: int = Field(default=12, gt=0, le=50)

    @field_validator("allowed_profile_ids", "allowed_hosts")
    @classmethod
    def normalize_browser_lists(cls, value: list[str], info: ValidationInfo) -> list[str]:
        """Normalize browser governor string lists and keep profile IDs non-empty."""
        normalized = [item.strip().lower() for item in value if item.strip()]
        if info.field_name == "allowed_profile_ids" and not normalized:
            msg = "allowed_profile_ids must contain at least one bot-owned profile."
            raise ValueError(msg)
        return normalized

    @field_validator("browser_engine")
    @classmethod
    def validate_browser_engine(cls, value: str) -> str:
        """Restrict the live automation engine to Firefox."""
        normalized = value.strip().lower()
        if normalized != "firefox":
            msg = "browser_engine must be firefox."
            raise ValueError(msg)
        return normalized

    @model_validator(mode="after")
    def validate_execution_settings(self) -> BrowserGovernorConfig:
        """Require explicit host allowlists before live automation is enabled."""
        if self.execution_enabled and not self.allowed_hosts:
            msg = "allowed_hosts must be configured when browser execution is enabled."
            raise ValueError(msg)
        return self


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


class BraveSearchConfig(MoneyBotModel):
    """Brave Search plugin configuration."""

    enabled: bool = False
    api_base_url: str = "https://api.search.brave.com/res/v1/web/search"
    api_key_env_var: str = "BRAVE_SEARCH_API_KEY"
    timeout_seconds: float = Field(default=10.0, gt=0, le=60.0)
    max_results: int = Field(default=10, gt=0, le=20)
    max_news_results: int = Field(default=10, gt=0, le=20)
    default_country: str = "us"
    default_search_lang: str = "en"
    safesearch: str = "moderate"
    default_news_freshness: str = "pd"

    @field_validator("api_base_url")
    @classmethod
    def validate_brave_api_url(cls, value: str) -> str:
        """Require the hosted Brave Search HTTPS endpoint."""
        parsed = urlparse(value)
        if parsed.scheme != "https":
            msg = "api_base_url must be an https URL"
            raise ValueError(msg)
        if parsed.hostname != "api.search.brave.com":
            msg = "api_base_url must point to api.search.brave.com"
            raise ValueError(msg)
        return value

    @field_validator("api_key_env_var")
    @classmethod
    def normalize_brave_env_var(cls, value: str) -> str:
        return value.strip()

    @field_validator(
        "default_country",
        "default_search_lang",
        "safesearch",
        "default_news_freshness",
    )
    @classmethod
    def normalize_brave_strings(cls, value: str) -> str:
        return value.strip().lower()


class WikipediaResearchConfig(MoneyBotModel):
    """Wikipedia research plugin configuration."""

    enabled: bool = False
    api_base_url: str = "https://en.wikipedia.org/w/api.php"
    summary_api_base_url: str = "https://en.wikipedia.org/api/rest_v1/page/summary"
    timeout_seconds: float = Field(default=10.0, gt=0, le=60.0)
    max_results: int = Field(default=10, gt=0, le=20)
    max_extract_chars: int = Field(default=2_000, gt=0, le=10_000)
    default_language: str = "en"

    @field_validator("api_base_url", "summary_api_base_url")
    @classmethod
    def validate_wikipedia_urls(cls, value: str) -> str:
        """Require HTTPS Wikipedia endpoints."""
        parsed = urlparse(value)
        if parsed.scheme != "https":
            msg = "Wikipedia API URLs must be https URLs"
            raise ValueError(msg)
        hostname = parsed.hostname or ""
        if not hostname.endswith(".wikipedia.org"):
            msg = "Wikipedia API URLs must point to wikipedia.org hosts"
            raise ValueError(msg)
        return value

    @field_validator("default_language")
    @classmethod
    def normalize_wikipedia_language(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            msg = "default_language must not be empty"
            raise ValueError(msg)
        return normalized


class ArxivResearchConfig(MoneyBotModel):
    """arXiv research plugin configuration."""

    enabled: bool = False
    api_base_url: str = "https://export.arxiv.org/api/query"
    timeout_seconds: float = Field(default=10.0, gt=0, le=60.0)
    max_results: int = Field(default=10, gt=0, le=20)
    max_summary_chars: int = Field(default=2_000, gt=0, le=10_000)
    default_sort_by: str = "relevance"
    default_sort_order: str = "descending"

    @field_validator("api_base_url")
    @classmethod
    def validate_arxiv_api_url(cls, value: str) -> str:
        """Require the hosted arXiv API endpoint."""
        parsed = urlparse(value)
        if parsed.scheme != "https":
            msg = "arXiv API URLs must be https URLs"
            raise ValueError(msg)
        if parsed.hostname != "export.arxiv.org":
            msg = "arXiv API URLs must point to export.arxiv.org"
            raise ValueError(msg)
        if not parsed.path.endswith("/api/query"):
            msg = "arXiv API URLs must point to the /api/query endpoint"
            raise ValueError(msg)
        return value

    @field_validator("default_sort_by")
    @classmethod
    def normalize_arxiv_sort_by(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"relevance", "lastupdateddate", "submitteddate"}:
            msg = "default_sort_by must be relevance, lastupdateddate, or submitteddate"
            raise ValueError(msg)
        return normalized

    @field_validator("default_sort_order")
    @classmethod
    def normalize_arxiv_sort_order(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"ascending", "descending"}:
            msg = "default_sort_order must be ascending or descending"
            raise ValueError(msg)
        return normalized


class OpenAlexResearchConfig(MoneyBotModel):
    """OpenAlex research plugin configuration."""

    enabled: bool = False
    api_base_url: str = "https://api.openalex.org/works"
    api_key_env_var: str = "OPENALEX_API_KEY"
    timeout_seconds: float = Field(default=10.0, gt=0, le=60.0)
    max_results: int = Field(default=10, gt=0, le=20)
    max_abstract_chars: int = Field(default=2_000, gt=0, le=10_000)

    @field_validator("api_base_url")
    @classmethod
    def validate_openalex_api_url(cls, value: str) -> str:
        """Require the hosted OpenAlex works endpoint."""
        parsed = urlparse(value)
        if parsed.scheme != "https":
            msg = "OpenAlex API URLs must be https URLs"
            raise ValueError(msg)
        if parsed.hostname != "api.openalex.org":
            msg = "OpenAlex API URLs must point to api.openalex.org"
            raise ValueError(msg)
        if not parsed.path.endswith("/works"):
            msg = "OpenAlex API URLs must point to the /works endpoint"
            raise ValueError(msg)
        return value

    @field_validator("api_key_env_var")
    @classmethod
    def normalize_openalex_env_var(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "api_key_env_var must not be empty"
            raise ValueError(msg)
        return normalized


class BiomedicalResearchConfig(MoneyBotModel):
    """PubMed and Europe PMC research plugin configuration."""

    enabled: bool = False
    pubmed_search_api_base_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    pubmed_fetch_api_base_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    europe_pmc_search_api_base_url: str = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    timeout_seconds: float = Field(default=10.0, gt=0, le=60.0)
    max_results: int = Field(default=10, gt=0, le=20)
    max_abstract_chars: int = Field(default=2_000, gt=0, le=10_000)

    @field_validator("pubmed_search_api_base_url", "pubmed_fetch_api_base_url")
    @classmethod
    def validate_pubmed_api_urls(cls, value: str) -> str:
        """Require the hosted NCBI E-utilities endpoints."""
        parsed = urlparse(value)
        if parsed.scheme != "https":
            msg = "PubMed API URLs must be https URLs"
            raise ValueError(msg)
        if parsed.hostname != "eutils.ncbi.nlm.nih.gov":
            msg = "PubMed API URLs must point to eutils.ncbi.nlm.nih.gov"
            raise ValueError(msg)
        if not parsed.path.startswith("/entrez/eutils/"):
            msg = "PubMed API URLs must point to E-utilities endpoints"
            raise ValueError(msg)
        return value

    @field_validator("europe_pmc_search_api_base_url")
    @classmethod
    def validate_europe_pmc_api_url(cls, value: str) -> str:
        """Require the hosted Europe PMC search endpoint."""
        parsed = urlparse(value)
        if parsed.scheme != "https":
            msg = "Europe PMC API URLs must be https URLs"
            raise ValueError(msg)
        if parsed.hostname != "www.ebi.ac.uk":
            msg = "Europe PMC API URLs must point to www.ebi.ac.uk"
            raise ValueError(msg)
        if not parsed.path.endswith("/europepmc/webservices/rest/search"):
            msg = "Europe PMC API URLs must point to the search endpoint"
            raise ValueError(msg)
        return value


class MastodonDiscoveryConfig(MoneyBotModel):
    """Mastodon discovery plugin configuration."""

    enabled: bool = False
    api_base_url: str = "https://mastodon.social"
    api_token_env_var: str = "MASTODON_API_TOKEN"
    require_auth: bool = False
    timeout_seconds: float = Field(default=10.0, gt=0, le=60.0)
    max_results: int = Field(default=20, gt=0, le=40)

    @field_validator("api_base_url")
    @classmethod
    def validate_mastodon_base_url(cls, value: str) -> str:
        """Require an HTTPS Mastodon instance root URL."""
        parsed = urlparse(value)
        if parsed.scheme != "https":
            msg = "Mastodon API base URLs must be https URLs"
            raise ValueError(msg)
        if parsed.hostname is None:
            msg = "Mastodon API base URLs must include a hostname"
            raise ValueError(msg)
        if parsed.path not in {"", "/"}:
            msg = "Mastodon API base URLs must point to the instance root"
            raise ValueError(msg)
        return value.rstrip("/")

    @field_validator("api_token_env_var")
    @classmethod
    def normalize_mastodon_env_var(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "api_token_env_var must not be empty"
            raise ValueError(msg)
        return normalized


class BlueskyDiscoveryConfig(MoneyBotModel):
    """Bluesky discovery plugin configuration."""

    enabled: bool = False
    api_base_url: str = "https://public.api.bsky.app"
    default_feed_uri: str = ""
    timeout_seconds: float = Field(default=10.0, gt=0, le=60.0)
    max_results: int = Field(default=20, gt=0, le=100)

    @field_validator("api_base_url")
    @classmethod
    def validate_bluesky_base_url(cls, value: str) -> str:
        """Require an HTTPS Bluesky public AppView root URL."""
        parsed = urlparse(value)
        if parsed.scheme != "https":
            msg = "Bluesky API base URLs must be https URLs"
            raise ValueError(msg)
        if parsed.hostname != "public.api.bsky.app":
            msg = "Bluesky API base URLs must point to public.api.bsky.app"
            raise ValueError(msg)
        if parsed.path not in {"", "/"}:
            msg = "Bluesky API base URLs must point to the instance root"
            raise ValueError(msg)
        return value.rstrip("/")

    @field_validator("default_feed_uri")
    @classmethod
    def normalize_default_feed_uri(cls, value: str) -> str:
        return value.strip()


class StockMarketDataConfig(MoneyBotModel):
    """Stock market data plugin configuration."""

    enabled: bool = False
    api_base_url: str = "https://www.alphavantage.co/query"
    api_key_env_var: str = "ALPHA_VANTAGE_API_KEY"
    timeout_seconds: float = Field(default=10.0, gt=0, le=60.0)
    max_daily_bars: int = Field(default=30, gt=0, le=100)

    @field_validator("api_base_url")
    @classmethod
    def validate_stock_market_api_url(cls, value: str) -> str:
        """Require the hosted Alpha Vantage query endpoint."""
        parsed = urlparse(value)
        if parsed.scheme != "https":
            msg = "Stock market API URLs must be https URLs"
            raise ValueError(msg)
        if parsed.hostname != "www.alphavantage.co":
            msg = "Stock market API URLs must point to www.alphavantage.co"
            raise ValueError(msg)
        if not parsed.path.endswith("/query"):
            msg = "Stock market API URLs must point to the /query endpoint"
            raise ValueError(msg)
        return value

    @field_validator("api_key_env_var")
    @classmethod
    def normalize_stock_market_env_var(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "api_key_env_var must not be empty"
            raise ValueError(msg)
        return normalized


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
    brave_search: BraveSearchConfig = Field(default_factory=BraveSearchConfig)
    wikipedia_research: WikipediaResearchConfig = Field(default_factory=WikipediaResearchConfig)
    arxiv_research: ArxivResearchConfig = Field(default_factory=ArxivResearchConfig)
    openalex_research: OpenAlexResearchConfig = Field(default_factory=OpenAlexResearchConfig)
    biomedical_research: BiomedicalResearchConfig = Field(default_factory=BiomedicalResearchConfig)
    mastodon_discovery: MastodonDiscoveryConfig = Field(default_factory=MastodonDiscoveryConfig)
    bluesky_discovery: BlueskyDiscoveryConfig = Field(default_factory=BlueskyDiscoveryConfig)
    stock_market_data: StockMarketDataConfig = Field(default_factory=StockMarketDataConfig)


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
