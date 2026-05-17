from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class MoneyBotError(BaseModel):
    error_code: str
    message: str
    recoverable: bool
    details: dict[str, Any]
    safe_for_user: bool = True

    @classmethod
    def not_found(cls, name: str) -> MoneyBotError:
        return cls(
            error_code="NOT_FOUND",
            message=f"{name} not found",
            recoverable=True,
            details={"name": name},
        )

    @classmethod
    def invalid_request(cls, detail: str) -> MoneyBotError:
        return cls(
            error_code="INVALID_REQUEST",
            message="Request is invalid",
            recoverable=True,
            details={"detail": detail},
        )

    @classmethod
    def blocked(cls, reason: str) -> MoneyBotError:
        return cls(
            error_code="BLOCKED",
            message="Action is blocked by policy",
            recoverable=False,
            details={"reason": reason},
            safe_for_user=True,
        )
