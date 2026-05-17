"""Opportunity scout package."""

from openclaw_moneybot.skills.opportunity_scout.models import (
    OpportunityCandidate,
    OpportunityScoutRequest,
    OpportunityScoutResult,
    RejectedCandidate,
    ScoutSourceDocument,
)
from openclaw_moneybot.skills.opportunity_scout.runner import OpportunityScout

__all__ = [
    "OpportunityCandidate",
    "OpportunityScout",
    "OpportunityScoutRequest",
    "OpportunityScoutResult",
    "RejectedCandidate",
    "ScoutSourceDocument",
]
