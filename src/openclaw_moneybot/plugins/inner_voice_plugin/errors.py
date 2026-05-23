"""Errors for the inner voice plugin stack."""

from __future__ import annotations


class InnerVoicePluginError(RuntimeError):
    """Raised when an inner-voice review cannot complete safely."""


class InnerVoiceProviderError(InnerVoicePluginError):
    """Raised when a provider cannot satisfy a structured request."""


class InnerVoiceDebateError(RuntimeError):
    """Raised when a debate session cannot complete safely."""


class ArbiterResolutionError(RuntimeError):
    """Raised when Arbiter resolution cannot complete safely."""
