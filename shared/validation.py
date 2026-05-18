from __future__ import annotations

from shared.config import MoneyBotConfig


def validate_config(cfg: MoneyBotConfig) -> list[str]:
    errors: list[str] = []
    if cfg.max_spend_usd <= 0:
        errors.append("max_spend_usd must be > 0")
    if cfg.email_mode not in ("draft_only", "send"):
        errors.append("email_mode must be draft_only or send")
    return errors


def ensure_safe_defaults(cfg: MoneyBotConfig) -> MoneyBotConfig:
    updated = cfg.model_copy()
    updated.email_mode = "draft_only"
    return updated
