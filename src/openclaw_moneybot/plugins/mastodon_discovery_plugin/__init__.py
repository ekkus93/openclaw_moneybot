"""Mastodon discovery plugin package."""

from openclaw_moneybot.plugins.mastodon_discovery_plugin.models import (
    MastodonPublicTimelineRequest,
    MastodonStatusSample,
    MastodonTimelineSampleResult,
)
from openclaw_moneybot.plugins.mastodon_discovery_plugin.service import (
    MastodonDiscoveryPlugin,
    MastodonDiscoveryPluginError,
)

__all__ = [
    "MastodonDiscoveryPlugin",
    "MastodonDiscoveryPluginError",
    "MastodonPublicTimelineRequest",
    "MastodonStatusSample",
    "MastodonTimelineSampleResult",
]
