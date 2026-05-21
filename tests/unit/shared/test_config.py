"""Tests for config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from openclaw_moneybot.shared.config import (
    AppConfig,
    BraveSearchConfig,
    BrowserGovernorConfig,
    EmailConfig,
    WalletGovernorConfig,
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


def test_brave_search_config_rejects_non_brave_host() -> None:
    with pytest.raises(ValueError, match="api.search.brave.com"):
        BraveSearchConfig(api_base_url="https://example.com/search")


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
