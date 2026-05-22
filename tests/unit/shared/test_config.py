"""Tests for config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from openclaw_moneybot.shared.config import (
    AppConfig,
    ArxivResearchConfig,
    BiomedicalResearchConfig,
    BlueskyDiscoveryConfig,
    BraveSearchConfig,
    BrowserGovernorConfig,
    CryptoMarketDataConfig,
    EmailConfig,
    MastodonDiscoveryConfig,
    OpenAlexResearchConfig,
    StockMarketDataConfig,
    WalletGovernorConfig,
    WikipediaResearchConfig,
    load_app_config,
)
from openclaw_moneybot.shared.errors import ErrorCode, MoneyBotError
from openclaw_moneybot.shared.types import EmailMode


def test_load_app_config_success(tmp_path: Path) -> None:
    """A valid YAML config loads into AppConfig."""
    config_path = tmp_path / "moneybot.yaml"
    config_path.write_text(
        """
policy:
  policy_version: "v1"
  blocked_categories: ["gambling"]
  review_required_categories: ["affiliate_marketing"]
  max_single_spend_usd: 10
  max_daily_spend_usd: 20
  max_weekly_spend_usd: 40
ledger:
  database_path: "data/moneybot.sqlite3"
archive:
  base_directory: "archive"
wallet_governor:
  base_url: "http://127.0.0.1:8080"
  timeout_seconds: 5
  spend_enabled: false
  allowed_assets: ["BTC"]
email:
  mode: "draft_only"
  max_outbound_per_day: 0
""".strip(),
        encoding="utf-8",
    )

    config = load_app_config(config_path)

    assert isinstance(config, AppConfig)
    assert config.policy.max_single_spend_usd == 10
    assert config.email.mode is EmailMode.DRAFT_ONLY
    assert config.browser_governor.enabled is False


def test_load_app_config_missing_file_raises(tmp_path: Path) -> None:
    """Missing files raise a structured error."""
    missing_path = tmp_path / "missing.yaml"

    with pytest.raises(MoneyBotError) as error:
        load_app_config(missing_path)

    assert error.value.detail.error_code is ErrorCode.MISSING_CONFIG


def test_load_app_config_rejects_non_local_wallet_url(tmp_path: Path) -> None:
    """Wallet URLs must stay local by default."""
    config_path = tmp_path / "moneybot.yaml"
    config_path.write_text(
        """
policy:
  policy_version: "v1"
  blocked_categories: []
  review_required_categories: []
  max_single_spend_usd: 10
  max_daily_spend_usd: 20
  max_weekly_spend_usd: 40
ledger:
  database_path: "data/moneybot.sqlite3"
archive:
  base_directory: "archive"
wallet_governor:
  base_url: "https://example.com"
  timeout_seconds: 5
  spend_enabled: false
  allowed_assets: ["BTC"]
email:
  mode: "draft_only"
  max_outbound_per_day: 0
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(MoneyBotError) as error:
        load_app_config(config_path)

    assert error.value.detail.error_code is ErrorCode.INVALID_CONFIG


def test_wallet_spending_disabled_by_default() -> None:
    config = WalletGovernorConfig(base_url="http://127.0.0.1:8080")

    assert config.spend_enabled is False
    assert config.bitcoin_network.value == "regtest"
    assert config.blocked_destinations == []


def test_wallet_config_normalizes_blocked_destinations() -> None:
    config = WalletGovernorConfig(
        base_url="http://127.0.0.1:8080",
        blocked_destinations=[
            "  BCRT1QQQGJYV6Y24N80ZYE42AUEH0WLUQPZG3N9TG8M2  ",
            "",
        ],
    )

    assert config.blocked_destinations == ["bcrt1qqqgjyv6y24n80zye42aueh0wluqpzg3n9tg8m2"]


def test_email_mode_defaults_to_draft_only() -> None:
    config = EmailConfig()

    assert config.mode is EmailMode.DRAFT_ONLY


def test_browser_governor_defaults_disabled() -> None:
    config = BrowserGovernorConfig()

    assert config.enabled is False
    assert config.allowed_profile_ids == ["moneybot-default"]
    assert config.execution_enabled is False
    assert config.browser_engine == "firefox"
    assert config.allowed_hosts == []


def test_wallet_config_rejects_unsupported_url_scheme() -> None:
    with pytest.raises(ValueError, match="http or https"):
        WalletGovernorConfig(base_url="ftp://127.0.0.1:8080")


def test_email_config_rejects_empty_sender_list() -> None:
    with pytest.raises(ValueError, match="allowed_sender_emails"):
        EmailConfig(allowed_sender_emails=[])


def test_email_config_rejects_non_positive_daily_cap_for_capped_send() -> None:
    with pytest.raises(ValueError, match="max_outbound_per_day"):
        EmailConfig(mode=EmailMode.CAPPED_SEND, max_outbound_per_day=0)


def test_browser_governor_config_rejects_empty_profile_list() -> None:
    with pytest.raises(ValueError, match="allowed_profile_ids"):
        BrowserGovernorConfig(allowed_profile_ids=[])


def test_browser_governor_config_requires_allowed_hosts_for_live_execution() -> None:
    with pytest.raises(ValueError, match="allowed_hosts"):
        BrowserGovernorConfig(execution_enabled=True)


def test_browser_governor_config_rejects_non_firefox_engine() -> None:
    with pytest.raises(ValueError, match="browser_engine"):
        BrowserGovernorConfig(browser_engine="chromium")


def test_brave_search_defaults_are_bounded_and_disabled() -> None:
    config = BraveSearchConfig()

    assert config.enabled is False
    assert config.api_key_env_var == "BRAVE_SEARCH_API_KEY"
    assert config.max_results == 10
    assert config.max_news_results == 10
    assert config.default_news_freshness == "pd"


def test_brave_search_config_rejects_non_brave_host() -> None:
    with pytest.raises(ValueError, match="api.search.brave.com"):
        BraveSearchConfig(api_base_url="https://example.com/search")


def test_wikipedia_research_defaults_are_bounded_and_disabled() -> None:
    config = WikipediaResearchConfig()

    assert config.enabled is False
    assert config.default_language == "en"
    assert config.max_results == 10
    assert config.max_extract_chars == 2_000


def test_wikipedia_research_config_rejects_non_wikipedia_hosts() -> None:
    with pytest.raises(ValueError, match="wikipedia.org"):
        WikipediaResearchConfig(api_base_url="https://example.com/w/api.php")


def test_arxiv_research_defaults_are_bounded_and_disabled() -> None:
    config = ArxivResearchConfig()

    assert config.enabled is False
    assert config.api_base_url == "https://export.arxiv.org/api/query"
    assert config.max_results == 10
    assert config.max_summary_chars == 2_000
    assert config.default_sort_by == "relevance"
    assert config.default_sort_order == "descending"


def test_arxiv_research_config_rejects_non_arxiv_hosts() -> None:
    with pytest.raises(ValueError, match="export.arxiv.org"):
        ArxivResearchConfig(api_base_url="https://example.com/api/query")


def test_openalex_research_defaults_are_bounded_and_disabled() -> None:
    config = OpenAlexResearchConfig()

    assert config.enabled is False
    assert config.api_base_url == "https://api.openalex.org/works"
    assert config.api_key_env_var == "OPENALEX_API_KEY"
    assert config.max_results == 10
    assert config.max_abstract_chars == 2_000


def test_openalex_research_config_rejects_non_openalex_hosts() -> None:
    with pytest.raises(ValueError, match="api.openalex.org"):
        OpenAlexResearchConfig(api_base_url="https://example.com/works")


def test_biomedical_research_defaults_are_bounded_and_disabled() -> None:
    config = BiomedicalResearchConfig()

    assert config.enabled is False
    assert config.pubmed_search_api_base_url.endswith("/esearch.fcgi")
    assert config.pubmed_fetch_api_base_url.endswith("/efetch.fcgi")
    assert config.europe_pmc_search_api_base_url.endswith("/europepmc/webservices/rest/search")
    assert config.max_results == 10
    assert config.max_abstract_chars == 2_000


def test_biomedical_research_config_rejects_non_pubmed_hosts() -> None:
    with pytest.raises(ValueError, match="eutils.ncbi.nlm.nih.gov"):
        BiomedicalResearchConfig(pubmed_search_api_base_url="https://example.com/esearch.fcgi")


def test_mastodon_discovery_defaults_are_bounded_and_disabled() -> None:
    config = MastodonDiscoveryConfig()

    assert config.enabled is False
    assert config.api_base_url == "https://mastodon.social"
    assert config.api_token_env_var == "MASTODON_API_TOKEN"
    assert config.require_auth is False
    assert config.max_results == 20


def test_mastodon_discovery_config_rejects_non_https_urls() -> None:
    with pytest.raises(ValueError, match="https"):
        MastodonDiscoveryConfig(api_base_url="http://mastodon.social")


def test_bluesky_discovery_defaults_are_bounded_and_disabled() -> None:
    config = BlueskyDiscoveryConfig()

    assert config.enabled is False
    assert config.api_base_url == "https://public.api.bsky.app"
    assert config.default_feed_uri == ""
    assert config.max_results == 20


def test_bluesky_discovery_config_rejects_non_public_appview_hosts() -> None:
    with pytest.raises(ValueError, match="public.api.bsky.app"):
        BlueskyDiscoveryConfig(api_base_url="https://api.bsky.app")


def test_stock_market_data_defaults_are_bounded_and_disabled() -> None:
    config = StockMarketDataConfig()

    assert config.enabled is False
    assert config.api_base_url == "https://www.alphavantage.co/query"
    assert config.api_key_env_var == "ALPHA_VANTAGE_API_KEY"
    assert config.max_daily_bars == 30


def test_stock_market_data_config_rejects_non_alpha_vantage_hosts() -> None:
    with pytest.raises(ValueError, match="www.alphavantage.co"):
        StockMarketDataConfig(api_base_url="https://example.com/query")


def test_crypto_market_data_defaults_are_bounded_and_disabled() -> None:
    config = CryptoMarketDataConfig()

    assert config.enabled is False
    assert config.api_base_url == "https://api.coingecko.com/api/v3"
    assert config.max_chart_points == 30


def test_crypto_market_data_config_rejects_non_coingecko_hosts() -> None:
    with pytest.raises(ValueError, match="api.coingecko.com"):
        CryptoMarketDataConfig(api_base_url="https://example.com/api/v3")


def test_load_app_config_rejects_non_mapping_root(tmp_path: Path) -> None:
    config_path = tmp_path / "moneybot.yaml"
    config_path.write_text("- not-a-mapping\n", encoding="utf-8")

    with pytest.raises(MoneyBotError) as error:
        load_app_config(config_path)

    assert error.value.detail.error_code is ErrorCode.INVALID_CONFIG
    assert error.value.detail.message == "Config root must be a mapping"


def test_load_app_config_reports_nested_validation_errors(tmp_path: Path) -> None:
    config_path = tmp_path / "moneybot.yaml"
    config_path.write_text(
        """
policy:
  policy_version: "v1"
  blocked_categories: []
  review_required_categories: []
  max_single_spend_usd: 10
  max_daily_spend_usd: 20
  max_weekly_spend_usd: 40
ledger:
  database_path: "data/moneybot.sqlite3"
archive:
  base_directory: "archive"
wallet_governor:
  base_url: "http://127.0.0.1:8080"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(MoneyBotError) as error:
        load_app_config(config_path)

    assert error.value.detail.error_code is ErrorCode.INVALID_CONFIG
    assert error.value.detail.message == "Config validation failed"
    details = error.value.detail.details
    assert isinstance(details, dict)
    errors = details.get("errors")
    assert isinstance(errors, list)
    assert any(
        isinstance(item, dict) and item.get("loc") == ["email"]
        for item in errors
    )
