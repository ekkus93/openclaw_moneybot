"""Duplicate opportunity detector package."""

from openclaw_moneybot.skills.duplicate_opportunity_detector.models import (
    DuplicateOpportunityDetectorRequest,
    DuplicateOpportunityDetectorResult,
    OpportunityFingerprint,
)
from openclaw_moneybot.skills.duplicate_opportunity_detector.runner import (
    DuplicateOpportunityDetector,
)

__all__ = [
    "DuplicateOpportunityDetector",
    "DuplicateOpportunityDetectorRequest",
    "DuplicateOpportunityDetectorResult",
    "OpportunityFingerprint",
]
