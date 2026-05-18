"""Opportunity scout package."""

from openclaw_moneybot.skills.opportunity_scout.adapters import (
    GitHubIssueFixtureAdapter,
    HackathonListingAdapter,
    LocalFixtureDocumentAdapter,
    ManualUrlIngestionAdapter,
    OpportunitySourceAdapter,
    PublicBountyPageAdapter,
)
from openclaw_moneybot.skills.opportunity_scout.models import (
    OpportunityCandidate,
    OpportunityScoutRequest,
    OpportunityScoutResult,
    RejectedCandidate,
    ScoutSourceDocument,
)
from openclaw_moneybot.skills.opportunity_scout.runner import OpportunityScout

__all__ = [
    "GitHubIssueFixtureAdapter",
    "HackathonListingAdapter",
    "LocalFixtureDocumentAdapter",
    "ManualUrlIngestionAdapter",
    "OpportunityCandidate",
    "OpportunityScout",
    "OpportunityScoutRequest",
    "OpportunityScoutResult",
    "OpportunitySourceAdapter",
    "PublicBountyPageAdapter",
    "RejectedCandidate",
    "ScoutSourceDocument",
]
