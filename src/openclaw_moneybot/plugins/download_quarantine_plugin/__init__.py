"""Bounded download and attachment quarantine plugin."""

from openclaw_moneybot.plugins.download_quarantine_plugin.models import (
    QuarantineIngestRequest,
    QuarantineIngestResult,
    QuarantinePromoteRequest,
    QuarantinePromoteResult,
)
from openclaw_moneybot.plugins.download_quarantine_plugin.service import DownloadQuarantinePlugin

__all__ = [
    "DownloadQuarantinePlugin",
    "QuarantineIngestRequest",
    "QuarantineIngestResult",
    "QuarantinePromoteRequest",
    "QuarantinePromoteResult",
]
