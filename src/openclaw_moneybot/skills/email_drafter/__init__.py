"""Email drafter package."""

from openclaw_moneybot.skills.email_drafter.models import EmailDraftRequest, EmailDraftResult
from openclaw_moneybot.skills.email_drafter.runner import EmailDrafter

__all__ = ["EmailDrafter", "EmailDraftRequest", "EmailDraftResult"]
