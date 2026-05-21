"""arXiv research plugin package."""

from openclaw_moneybot.plugins.arxiv_research_plugin.models import (
    ArxivPaperRequest,
    ArxivPaperResult,
    ArxivPaperResultItem,
    ArxivSearchRequest,
    ArxivSearchResult,
)
from openclaw_moneybot.plugins.arxiv_research_plugin.service import (
    ArxivResearchPlugin,
    ArxivResearchPluginError,
)

__all__ = [
    "ArxivPaperRequest",
    "ArxivPaperResult",
    "ArxivPaperResultItem",
    "ArxivResearchPlugin",
    "ArxivResearchPluginError",
    "ArxivSearchRequest",
    "ArxivSearchResult",
]
