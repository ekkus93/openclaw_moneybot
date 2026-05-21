"""Local opportunity index plugin."""

from openclaw_moneybot.plugins.opportunity_index_plugin.models import (
    OpportunityIndexEntry,
    OpportunityIndexRefreshResult,
    OpportunitySimilarityMatch,
    OpportunitySimilarityQueryRequest,
    OpportunitySimilarityQueryResult,
)
from openclaw_moneybot.plugins.opportunity_index_plugin.service import OpportunityIndexPlugin

__all__ = [
    "OpportunityIndexEntry",
    "OpportunityIndexPlugin",
    "OpportunityIndexRefreshResult",
    "OpportunitySimilarityMatch",
    "OpportunitySimilarityQueryRequest",
    "OpportunitySimilarityQueryResult",
]
