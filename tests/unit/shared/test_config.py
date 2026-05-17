"""Tests for config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from openclaw_moneybot.shared.config import (
    AppConfig,
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


def test_email_mode_defaults_to_draft_only() -> None:
    config = EmailConfig()

    assert config.mode is EmailMode.DRAFT_ONLY
