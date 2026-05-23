"""Errors for the inner voice plugin stack."""

from __future__ import annotations


class InnerVoicePluginError(RuntimeError):
    """Raised when an inner-voice review cannot complete safely."""

    def __init__(self, message: str, *, failure_class: str = "plugin_error") -> None:
        super().__init__(message)
        self.failure_class = failure_class


class InnerVoiceProviderError(InnerVoicePluginError):
    """Raised when a provider cannot satisfy a structured request."""

    def __init__(self, message: str, *, failure_class: str = "provider_error") -> None:
        super().__init__(message, failure_class=failure_class)


class InnerVoiceDebateError(RuntimeError):
    """Raised when a debate session cannot complete safely."""

    def __init__(self, message: str, *, failure_class: str = "debate_error") -> None:
        super().__init__(message)
        self.failure_class = failure_class


class ArbiterResolutionError(RuntimeError):
    """Raised when Arbiter resolution cannot complete safely."""

    def __init__(self, message: str, *, failure_class: str = "arbiter_error") -> None:
        super().__init__(message)
        self.failure_class = failure_class
