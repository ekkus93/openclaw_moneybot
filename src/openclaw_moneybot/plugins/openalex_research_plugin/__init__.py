"""OpenAlex research plugin package."""

from openclaw_moneybot.plugins.openalex_research_plugin.models import (
    OpenAlexSearchRequest,
    OpenAlexSearchResult,
    OpenAlexWorkRequest,
    OpenAlexWorkResult,
    OpenAlexWorkResultItem,
)
from openclaw_moneybot.plugins.openalex_research_plugin.service import (
    OpenAlexResearchPlugin,
    OpenAlexResearchPluginError,
)

__all__ = [
    "OpenAlexResearchPlugin",
    "OpenAlexResearchPluginError",
    "OpenAlexSearchRequest",
    "OpenAlexSearchResult",
    "OpenAlexWorkRequest",
    "OpenAlexWorkResult",
    "OpenAlexWorkResultItem",
]
