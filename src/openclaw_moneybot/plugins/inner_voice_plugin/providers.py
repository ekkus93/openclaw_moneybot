"""Direct provider adapters for inner voice and Arbiter calls."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Protocol, cast

import httpx
from pydantic import JsonValue

from openclaw_moneybot.plugins.inner_voice_plugin.errors import InnerVoiceProviderError
from openclaw_moneybot.plugins.inner_voice_plugin.models import (
    InnerVoicePromptRequest,
    InnerVoiceRawResponse,
)
from openclaw_moneybot.plugins.support import PluginHealthResult, json_mapping
from openclaw_moneybot.shared.types import ProviderName


class ProviderConfigLike(Protocol):
    """Shared config fields needed by provider adapters."""

    provider: ProviderName
    model_name: str
    base_url: str
    api_key_env_var: str
    allow_hosted_provider: bool
    timeout_seconds: float
    max_output_tokens: int


class BaseProviderAdapter:
    """Base helper for direct provider-specific adapters."""

    provider_name: ProviderName
    supports_json_mode: bool = True
    supports_system_prompt: bool = True
    healthcheck_path: str | None = None

    def __init__(
        self,
        config: ProviderConfigLike,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = config.base_url.rstrip("/")
        self.model_name = config.model_name
        self.timeout_seconds = config.timeout_seconds
        self.max_output_tokens = config.max_output_tokens
        self.api_key_env_var = config.api_key_env_var
        self.allow_hosted_provider = config.allow_hosted_provider
        self._client = httpx.Client(timeout=config.timeout_seconds, transport=transport)

    def close(self) -> None:
        self._client.close()

    def health(self, *, enabled: bool) -> PluginHealthResult:
        """Return a cheap local health assessment."""

        if not enabled:
            return PluginHealthResult(
                plugin_name="inner_voice_provider",
                status="disabled",
                enabled=False,
                read_only=True,
            )
        if not self.model_name:
            return PluginHealthResult(
                plugin_name="inner_voice_provider",
                status="misconfigured",
                enabled=True,
                read_only=True,
            )
        if self.provider_name is ProviderName.OPENAI and not os.getenv(self.api_key_env_var):
            return PluginHealthResult(
                plugin_name="inner_voice_provider",
                status="missing_api_key",
                enabled=True,
                read_only=True,
            )
        if self.healthcheck_path is not None:
            try:
                response = self._client.get(
                    f"{self.base_url}{self.healthcheck_path}",
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError):
                return PluginHealthResult(
                    plugin_name="inner_voice_provider",
                    status="provider_unreachable",
                    enabled=True,
                    read_only=True,
                )
        return PluginHealthResult(
            plugin_name="inner_voice_provider",
            status="ok",
            enabled=True,
            read_only=True,
        )

    def generate(self, request: InnerVoicePromptRequest) -> InnerVoiceRawResponse:
        raise NotImplementedError

    @staticmethod
    def _parse_strict_json_object(text: str) -> dict[str, JsonValue]:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            msg = "Provider returned malformed JSON."
            raise InnerVoiceProviderError(msg) from error
        if not isinstance(payload, dict):
            msg = "Provider response must be exactly one JSON object."
            raise InnerVoiceProviderError(msg)
        return cast(dict[str, JsonValue], payload)

    @staticmethod
    def _string_content(value: object) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, Mapping):
                    text_value = item.get("text")
                    if isinstance(text_value, str):
                        parts.append(text_value)
            if parts:
                return "".join(parts)
        msg = "Provider response did not contain string content."
        raise InnerVoiceProviderError(msg)


class OpenAiProviderAdapter(BaseProviderAdapter):
    """Direct OpenAI chat-completions adapter."""

    provider_name = ProviderName.OPENAI

    def generate(self, request: InnerVoicePromptRequest) -> InnerVoiceRawResponse:
        api_key = os.getenv(self.api_key_env_var)
        if not api_key:
            msg = "OpenAI API key is not configured."
            raise InnerVoiceProviderError(msg, failure_class="invalid_auth")
        payload: dict[str, object] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        try:
            response = self._client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
            )
            response.raise_for_status()
            raw_payload = response.json()
        except (httpx.TimeoutException, httpx.TransportError) as error:
            msg = "OpenAI provider is unavailable."
            raise InnerVoiceProviderError(msg, failure_class="provider_unavailable") from error
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {401, 403}:
                msg = "OpenAI request failed because authentication was rejected."
                raise InnerVoiceProviderError(msg, failure_class="invalid_auth") from error
            msg = f"OpenAI request failed: {error}"
            raise InnerVoiceProviderError(msg, failure_class="provider_error") from error
        except ValueError as error:
            msg = f"OpenAI request failed: {error}"
            raise InnerVoiceProviderError(msg, failure_class="malformed_output") from error
        if not isinstance(raw_payload, dict):
            msg = "OpenAI response must be a JSON object."
            raise InnerVoiceProviderError(msg, failure_class="malformed_output")
        choices = raw_payload.get("choices")
        if not isinstance(choices, list) or not choices:
            msg = "OpenAI response did not contain choices."
            raise InnerVoiceProviderError(msg, failure_class="malformed_output")
        first_choice = choices[0]
        if not isinstance(first_choice, Mapping):
            msg = "OpenAI response choice was malformed."
            raise InnerVoiceProviderError(msg, failure_class="malformed_output")
        message = first_choice.get("message")
        if not isinstance(message, Mapping):
            msg = "OpenAI response choice is missing a message."
            raise InnerVoiceProviderError(msg, failure_class="malformed_output")
        content = self._string_content(message.get("content"))
        usage = raw_payload.get("usage")
        prompt_tokens: int | None = None
        completion_tokens: int | None = None
        if isinstance(usage, Mapping):
            prompt_value = usage.get("prompt_tokens")
            completion_value = usage.get("completion_tokens")
            if isinstance(prompt_value, int):
                prompt_tokens = prompt_value
            if isinstance(completion_value, int):
                completion_tokens = completion_value
        parsed_json = self._parse_strict_json_object(content)
        finish_reason = first_choice.get("finish_reason")
        return InnerVoiceRawResponse(
            provider=self.provider_name,
            model_name=self.model_name,
            response_text=content,
            parsed_json=parsed_json,
            finish_reason=finish_reason if isinstance(finish_reason, str) else None,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            prompt_chars=len(request.system_prompt) + len(request.user_prompt),
            raw_payload=json_mapping(raw_payload),
        )


class OllamaProviderAdapter(BaseProviderAdapter):
    """Direct Ollama chat adapter."""

    provider_name = ProviderName.OLLAMA
    healthcheck_path = "/api/tags"

    def generate(self, request: InnerVoicePromptRequest) -> InnerVoiceRawResponse:
        payload: dict[str, object] = {
            "model": self.model_name,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_output_tokens,
            },
        }
        if request.top_p is not None:
            options = payload["options"]
            assert isinstance(options, dict)
            options["top_p"] = request.top_p
        try:
            response = self._client.post(
                f"{self.base_url}/api/chat",
                json=payload,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            raw_payload = response.json()
        except (httpx.TimeoutException, httpx.TransportError) as error:
            msg = "Ollama provider is unavailable."
            raise InnerVoiceProviderError(msg, failure_class="provider_unavailable") from error
        except httpx.HTTPStatusError as error:
            msg = f"Ollama request failed: {error}"
            raise InnerVoiceProviderError(msg, failure_class="provider_error") from error
        except ValueError as error:
            msg = f"Ollama request failed: {error}"
            raise InnerVoiceProviderError(msg, failure_class="malformed_output") from error
        if not isinstance(raw_payload, dict):
            msg = "Ollama response must be a JSON object."
            raise InnerVoiceProviderError(msg, failure_class="malformed_output")
        message = raw_payload.get("message")
        if not isinstance(message, Mapping):
            msg = "Ollama response is missing a message."
            raise InnerVoiceProviderError(msg, failure_class="malformed_output")
        content = self._string_content(message.get("content"))
        parsed_json = self._parse_strict_json_object(content)
        prompt_tokens = raw_payload.get("prompt_eval_count")
        completion_tokens = raw_payload.get("eval_count")
        return InnerVoiceRawResponse(
            provider=self.provider_name,
            model_name=self.model_name,
            response_text=content,
            parsed_json=parsed_json,
            finish_reason=raw_payload.get("done_reason")
            if isinstance(raw_payload.get("done_reason"), str)
            else None,
            prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else None,
            completion_tokens=completion_tokens if isinstance(completion_tokens, int) else None,
            prompt_chars=len(request.system_prompt) + len(request.user_prompt),
            raw_payload=json_mapping(raw_payload),
        )


class LlamaServerProviderAdapter(BaseProviderAdapter):
    """Direct OpenAI-compatible llama-server adapter."""

    provider_name = ProviderName.LLAMA_SERVER
    healthcheck_path = "/models"

    def generate(self, request: InnerVoicePromptRequest) -> InnerVoiceRawResponse:
        payload: dict[str, object] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        try:
            response = self._client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            raw_payload = response.json()
        except (httpx.TimeoutException, httpx.TransportError) as error:
            msg = "llama-server provider is unavailable."
            raise InnerVoiceProviderError(msg, failure_class="provider_unavailable") from error
        except httpx.HTTPStatusError as error:
            msg = f"llama-server request failed: {error}"
            raise InnerVoiceProviderError(msg, failure_class="provider_error") from error
        except ValueError as error:
            msg = f"llama-server request failed: {error}"
            raise InnerVoiceProviderError(msg, failure_class="malformed_output") from error
        if not isinstance(raw_payload, dict):
            msg = "llama-server response must be a JSON object."
            raise InnerVoiceProviderError(msg, failure_class="malformed_output")
        choices = raw_payload.get("choices")
        if not isinstance(choices, list) or not choices:
            msg = "llama-server response did not contain choices."
            raise InnerVoiceProviderError(msg, failure_class="malformed_output")
        first_choice = choices[0]
        if not isinstance(first_choice, Mapping):
            msg = "llama-server response choice was malformed."
            raise InnerVoiceProviderError(msg, failure_class="malformed_output")
        message = first_choice.get("message")
        if not isinstance(message, Mapping):
            msg = "llama-server response choice is missing a message."
            raise InnerVoiceProviderError(msg, failure_class="malformed_output")
        content = self._string_content(message.get("content"))
        usage = raw_payload.get("usage")
        prompt_tokens: int | None = None
        completion_tokens: int | None = None
        if isinstance(usage, Mapping):
            prompt_value = usage.get("prompt_tokens")
            completion_value = usage.get("completion_tokens")
            if isinstance(prompt_value, int):
                prompt_tokens = prompt_value
            if isinstance(completion_value, int):
                completion_tokens = completion_value
        parsed_json = self._parse_strict_json_object(content)
        finish_reason = first_choice.get("finish_reason")
        return InnerVoiceRawResponse(
            provider=self.provider_name,
            model_name=self.model_name,
            response_text=content,
            parsed_json=parsed_json,
            finish_reason=finish_reason if isinstance(finish_reason, str) else None,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            prompt_chars=len(request.system_prompt) + len(request.user_prompt),
            raw_payload=json_mapping(raw_payload),
        )


def build_provider_adapter(
    config: ProviderConfigLike,
    *,
    transport: httpx.BaseTransport | None = None,
) -> BaseProviderAdapter:
    """Build the direct adapter for one configured provider family."""

    if config.provider is ProviderName.OPENAI:
        return OpenAiProviderAdapter(config, transport=transport)
    if config.provider is ProviderName.OLLAMA:
        return OllamaProviderAdapter(config, transport=transport)
    if config.provider is ProviderName.LLAMA_SERVER:
        return LlamaServerProviderAdapter(config, transport=transport)
    msg = f"Unsupported provider: {config.provider}"
    raise ValueError(msg)
