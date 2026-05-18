from __future__ import annotations

from skills.opportunity_scout.analysis import analyze
from skills.opportunity_scout.models import (
    OpportunityScoutRequest,
    OpportunityScoutResult,
)


def run_opportunity_scout(request: OpportunityScoutRequest) -> OpportunityScoutResult:
    return analyze(request)
