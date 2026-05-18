from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class MoneyBotConfig(BaseModel):
    max_spend_usd: float = 100.0
    blocked_categories: list[str] = []
    evidence_archive_path: str = "/tmp/moneybot_evidence"
    sqlite_database_path: str = "/tmp/moneybot.db"
    wallet_governor_url: str = "http://localhost:8080"
    email_mode: str = "draft_only"


def load_config(path: str = "configs/moneybot.yaml") -> MoneyBotConfig:
    p = Path(path)
    if not p.exists():
        return MoneyBotConfig()

    import yaml

    with p.open() as f:
        data = yaml.safe_load(f or {})

    return MoneyBotConfig(**data)
