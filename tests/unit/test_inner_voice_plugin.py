"""Unit tests for the inner voice plugin, debate coordinator, and Arbiter."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import httpx
import pytest

import openclaw_moneybot.plugins.inner_voice_plugin.providers as provider_module
from openclaw_moneybot.plugins.inner_voice_plugin import (
    ArbiterResolutionError,
    ArbiterResolutionRequest,
    ArbiterService,
    DebateResponderOutput,
    DebateResponderRequest,
    EvidenceSummary,
    InnerVoiceCoordinator,
    InnerVoiceDebateError,
    InnerVoiceDebateRequest,
    InnerVoiceObjection,
    InnerVoicePlugin,
    InnerVoicePluginError,
    InnerVoicePromptRequest,
    InnerVoiceProviderError,
    InnerVoiceReviewRequest,
    build_metrics_snapshot,
    list_arbiter_reviews,
    list_inner_voice_debates,
    list_inner_voice_reviews,
    persist_metrics_snapshot,
)
from openclaw_moneybot.plugins.inner_voice_plugin.prompting import build_inner_voice_prompt
from openclaw_moneybot.shared import ArbiterConfig, ArchiveConfig, InnerVoiceConfig
from openclaw_moneybot.shared.types import (
    ArbiterFinalResolution,
    ArbiterPrevailingSide,
    DebateEndedReason,
    DebateSpeaker,
    DebateTurnType,
    InnerVoiceDisposition,
    InnerVoiceObjectionSeverity,
    InnerVoiceStage,
    InnerVoiceSubjectType,
    ProviderName,
    RecordType,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_review_request() -> InnerVoiceReviewRequest:
    return InnerVoiceReviewRequest(
        review_id="review_001",
        stage=InnerVoiceStage.TOS_LEGAL_CHECK,
        subject_type=InnerVoiceSubjectType.OPPORTUNITY,
        subject_id="opp_001",
        claim_summary="The opportunity is safe and eligible to proceed.",
        structured_context={"mission": "test"},
        constraints_summary=["no direct wallet access"],
        review_goal="Challenge the current conclusion.",
        max_objections=4,
    )


def make_prompt_request(
    *,
    provider: ProviderName,
    model_name: str = "test-model",
    top_p: float | None = None,
) -> InnerVoicePromptRequest:
    return InnerVoicePromptRequest(
        request_id="prompt_001",
        provider=provider,
        model_name=model_name,
        system_prompt="system prompt",
        user_prompt="user prompt",
        response_schema_json={"type": "object"},
        temperature=0.2,
        top_p=top_p,
        max_output_tokens=256,
        timeout_seconds=10.0,
    )


def make_provider_config(
    provider: ProviderName,
    **overrides: object,
) -> InnerVoiceConfig:
    payload: dict[str, object] = {
        "enabled": True,
        "provider": provider,
        "model_name": "test-model",
        "base_url": (
            "https://api.openai.com/v1"
            if provider is ProviderName.OPENAI
            else "http://127.0.0.1:11434"
            if provider is ProviderName.OLLAMA
            else "http://127.0.0.1:8080/v1"
        ),
        "api_key_env_var": "OPENAI_API_KEY",
        "allow_hosted_provider": provider is ProviderName.OPENAI,
        "timeout_seconds": 10.0,
        "max_output_tokens": 256,
    }
    payload.update(overrides)
    return InnerVoiceConfig.model_validate(payload)


def make_inner_voice_plugin(
    tmp_path: Path,
    *,
    provider: ProviderName,
    handler: httpx.BaseTransport,
    config_overrides: dict[str, object] | None = None,
) -> tuple[InnerVoicePlugin, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    config_payload: dict[str, object] = {
        "enabled": True,
        "provider": provider,
        "model_name": "test-model",
        "base_url": (
            "https://api.openai.com/v1"
            if provider is ProviderName.OPENAI
            else "http://127.0.0.1:11434"
            if provider is ProviderName.OLLAMA
            else "http://127.0.0.1:8080/v1"
        ),
        "api_key_env_var": "OPENAI_API_KEY",
        "allow_hosted_provider": provider is ProviderName.OPENAI,
    }
    config_payload.update(config_overrides or {})
    config = InnerVoiceConfig(
        **config_payload,
    )
    plugin = InnerVoicePlugin(
        config,
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=handler,
    )
    return plugin, ledger_service


def make_arbiter_service(
    tmp_path: Path,
    *,
    provider: ProviderName,
    handler: httpx.BaseTransport,
) -> tuple[ArbiterService, LedgerService]:
    ledger_service = LedgerService.from_db_path(tmp_path / "moneybot.sqlite3")
    config = ArbiterConfig(
        provider=provider,
        model_name="arbiter-model",
        base_url=(
            "https://api.openai.com/v1"
            if provider is ProviderName.OPENAI
            else "http://127.0.0.1:11434"
            if provider is ProviderName.OLLAMA
            else "http://127.0.0.1:8080/v1"
        ),
        api_key_env_var="OPENAI_API_KEY",
        allow_hosted_provider=provider is ProviderName.OPENAI,
    )
    service = ArbiterService(
        config,
        ArchiveConfig(base_directory=tmp_path / "archive"),
        ledger_service,
        transport=handler,
    )
    return service, ledger_service


def test_provider_health_states_cover_disabled_config_auth_and_reachability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    disabled_adapter = provider_module.build_provider_adapter(
        make_provider_config(ProviderName.OLLAMA),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )
    misconfigured_adapter = provider_module.build_provider_adapter(
        make_provider_config(ProviderName.OLLAMA),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )
    misconfigured_adapter.model_name = ""
    openai_adapter = provider_module.build_provider_adapter(
        make_provider_config(ProviderName.OPENAI),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )
    unreachable_adapter = provider_module.build_provider_adapter(
        make_provider_config(ProviderName.OLLAMA),
        transport=httpx.MockTransport(lambda request: httpx.Response(503)),
    )
    reachable_adapter = provider_module.build_provider_adapter(
        make_provider_config(ProviderName.OLLAMA),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )

    assert disabled_adapter.health(enabled=False).status == "disabled"
    assert misconfigured_adapter.health(enabled=True).status == "misconfigured"
    assert openai_adapter.health(enabled=True).status == "missing_api_key"
    assert unreachable_adapter.health(enabled=True).status == "provider_unreachable"
    assert reachable_adapter.health(enabled=True).status == "ok"

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")
    openai_ok_adapter = provider_module.build_provider_adapter(
        make_provider_config(ProviderName.OPENAI),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )
    assert openai_ok_adapter.health(enabled=True).status == "ok"

    for adapter in (
        disabled_adapter,
        misconfigured_adapter,
        openai_adapter,
        unreachable_adapter,
        reachable_adapter,
        openai_ok_adapter,
    ):
        adapter.close()


def test_provider_parsing_helpers_are_strict_and_join_text_parts() -> None:
    assert provider_module.BaseProviderAdapter._parse_strict_json_object('{"ok": true}') == {
        "ok": True
    }
    with pytest.raises(InnerVoiceProviderError, match="malformed JSON"):
        provider_module.BaseProviderAdapter._parse_strict_json_object("{nope}")
    with pytest.raises(InnerVoiceProviderError, match="exactly one JSON object"):
        provider_module.BaseProviderAdapter._parse_strict_json_object('["x"]')

    assert provider_module.BaseProviderAdapter._string_content("value") == "value"
    assert provider_module.BaseProviderAdapter._string_content(
        [
            {"type": "text", "text": '{"a":'},
            "ignored",
            {"type": "image"},
            {"type": "text", "text": "1}"},
        ]
    ) == '{"a":1}'

    with pytest.raises(InnerVoiceProviderError, match="string content"):
        provider_module.BaseProviderAdapter._string_content([{"type": "image"}])


@pytest.mark.parametrize(
    ("status_code", "failure_class"),
    [(401, "invalid_auth"), (403, "invalid_auth"), (500, "provider_error")],
)
def test_openai_adapter_maps_http_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    failure_class: str,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")
    adapter = provider_module.build_provider_adapter(
        make_provider_config(ProviderName.OPENAI),
        transport=httpx.MockTransport(lambda request: httpx.Response(status_code, json={})),
    )

    with pytest.raises(InnerVoiceProviderError) as error:
        adapter.generate(make_prompt_request(provider=ProviderName.OPENAI))

    assert error.value.failure_class == failure_class
    adapter.close()


def test_openai_adapter_handles_transport_missing_key_and_success_variants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_key_adapter = provider_module.build_provider_adapter(
        make_provider_config(ProviderName.OPENAI),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )
    with pytest.raises(InnerVoiceProviderError) as missing_key_error:
        missing_key_adapter.generate(make_prompt_request(provider=ProviderName.OPENAI))
    assert missing_key_error.value.failure_class == "invalid_auth"
    missing_key_adapter.close()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")

    transport_adapter = provider_module.build_provider_adapter(
        make_provider_config(ProviderName.OPENAI),
        transport=httpx.MockTransport(
            lambda request: (_ for _ in ()).throw(httpx.ConnectError("boom"))
        ),
    )
    with pytest.raises(InnerVoiceProviderError) as transport_error:
        transport_adapter.generate(make_prompt_request(provider=ProviderName.OPENAI))
    assert transport_error.value.failure_class == "provider_unavailable"
    transport_adapter.close()

    payloads = iter(
        [
            [],
            {},
            {"choices": [123]},
            {"choices": [{"finish_reason": "stop"}]},
            {
                "choices": [
                    {
                        "finish_reason": 123,
                        "message": {"content": '{"ok": true}'},
                    }
                ],
                "usage": {"prompt_tokens": "ten", "completion_tokens": "five"},
            },
        ]
    )
    seen_payloads: list[dict[str, object]] = []

    def success_handler(request: httpx.Request) -> httpx.Response:
        seen_payloads.append(json.loads(request.read().decode("utf-8")))
        return httpx.Response(200, json=next(payloads))

    success_adapter = provider_module.build_provider_adapter(
        make_provider_config(ProviderName.OPENAI),
        transport=httpx.MockTransport(success_handler),
    )

    with pytest.raises(InnerVoiceProviderError, match="JSON object"):
        success_adapter.generate(make_prompt_request(provider=ProviderName.OPENAI))
    with pytest.raises(InnerVoiceProviderError, match="did not contain choices"):
        success_adapter.generate(make_prompt_request(provider=ProviderName.OPENAI))
    with pytest.raises(InnerVoiceProviderError, match="choice was malformed"):
        success_adapter.generate(make_prompt_request(provider=ProviderName.OPENAI))
    with pytest.raises(InnerVoiceProviderError, match="missing a message"):
        success_adapter.generate(make_prompt_request(provider=ProviderName.OPENAI))

    result = success_adapter.generate(
        make_prompt_request(provider=ProviderName.OPENAI, top_p=0.8)
    )

    assert result.finish_reason is None
    assert result.prompt_tokens is None
    assert result.completion_tokens is None
    assert seen_payloads[-1]["top_p"] == 0.8
    assert "top_p" not in seen_payloads[-2]
    success_adapter.close()


def test_ollama_adapter_covers_malformed_and_optional_fields(tmp_path: Path) -> None:
    payloads = iter(
        [
            [],
            {},
            {
                "message": {"content": '{"ok": true}'},
                "done_reason": 123,
                "prompt_eval_count": "ten",
                "eval_count": "five",
            },
        ]
    )

    adapter = provider_module.build_provider_adapter(
        make_provider_config(ProviderName.OLLAMA),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=next(payloads))),
    )

    with pytest.raises(InnerVoiceProviderError, match="JSON object"):
        adapter.generate(make_prompt_request(provider=ProviderName.OLLAMA))
    with pytest.raises(InnerVoiceProviderError, match="missing a message"):
        adapter.generate(make_prompt_request(provider=ProviderName.OLLAMA))

    result = adapter.generate(make_prompt_request(provider=ProviderName.OLLAMA))

    assert result.finish_reason is None
    assert result.prompt_tokens is None
    assert result.completion_tokens is None
    adapter.close()


@pytest.mark.parametrize(
    ("response_factory", "failure_class"),
    [
        (
            lambda request: (_ for _ in ()).throw(httpx.ConnectError("boom")),
            "provider_unavailable",
        ),
        (lambda request: httpx.Response(500, json={}), "provider_error"),
    ],
)
def test_llama_server_adapter_maps_transport_and_http_failures(
    tmp_path: Path,
    response_factory: Callable[[httpx.Request], httpx.Response],
    failure_class: str,
) -> None:
    adapter = provider_module.build_provider_adapter(
        make_provider_config(ProviderName.LLAMA_SERVER),
        transport=httpx.MockTransport(response_factory),
    )

    with pytest.raises(InnerVoiceProviderError) as error:
        adapter.generate(make_prompt_request(provider=ProviderName.LLAMA_SERVER))

    assert error.value.failure_class == failure_class
    adapter.close()


def test_llama_server_adapter_covers_malformed_payloads_and_optional_usage(tmp_path: Path) -> None:
    payloads = iter(
        [
            [],
            {},
            {"choices": [123]},
            {"choices": [{"finish_reason": "stop"}]},
            {
                "choices": [
                    {
                        "finish_reason": 123,
                        "message": {"content": '{"ok": true}'},
                    }
                ],
                "usage": {"prompt_tokens": "ten", "completion_tokens": "five"},
            },
        ]
    )
    adapter = provider_module.build_provider_adapter(
        make_provider_config(ProviderName.LLAMA_SERVER),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=next(payloads))),
    )

    with pytest.raises(InnerVoiceProviderError, match="JSON object"):
        adapter.generate(make_prompt_request(provider=ProviderName.LLAMA_SERVER))
    with pytest.raises(InnerVoiceProviderError, match="did not contain choices"):
        adapter.generate(make_prompt_request(provider=ProviderName.LLAMA_SERVER))
    with pytest.raises(InnerVoiceProviderError, match="choice was malformed"):
        adapter.generate(make_prompt_request(provider=ProviderName.LLAMA_SERVER))
    with pytest.raises(InnerVoiceProviderError, match="missing a message"):
        adapter.generate(make_prompt_request(provider=ProviderName.LLAMA_SERVER))

    result = adapter.generate(make_prompt_request(provider=ProviderName.LLAMA_SERVER))

    assert result.finish_reason is None
    assert result.prompt_tokens is None
    assert result.completion_tokens is None
    adapter.close()


def test_build_provider_adapter_returns_expected_types_and_rejects_unknown_provider(
    tmp_path: Path,
) -> None:
    openai_adapter = provider_module.build_provider_adapter(
        make_provider_config(ProviderName.OPENAI),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )
    ollama_adapter = provider_module.build_provider_adapter(
        make_provider_config(ProviderName.OLLAMA),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )
    llama_adapter = provider_module.build_provider_adapter(
        make_provider_config(ProviderName.LLAMA_SERVER),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )

    assert isinstance(openai_adapter, provider_module.OpenAiProviderAdapter)
    assert isinstance(ollama_adapter, provider_module.OllamaProviderAdapter)
    assert isinstance(llama_adapter, provider_module.LlamaServerProviderAdapter)

    class UnsupportedConfig:
        provider = cast(ProviderName, "bogus")
        model_name = "test-model"
        base_url = "http://127.0.0.1"
        api_key_env_var = "OPENAI_API_KEY"
        allow_hosted_provider = False
        timeout_seconds = 10.0
        max_output_tokens = 256

    with pytest.raises(ValueError, match="Unsupported provider"):
        provider_module.build_provider_adapter(UnsupportedConfig())

    openai_adapter.close()
    ollama_adapter.close()
    llama_adapter.close()


def test_openai_inner_voice_review_shapes_request_and_persists_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.openai.com"
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.read().decode("utf-8"))
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["messages"][1]["content"].find("Challenge the current conclusion.") >= 0
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": (
                                '{"overall_assessment":"Needs more evidence.",'
                                '"recommended_disposition":"needs_review",'
                                '"confidence_adjustment":-0.3,'
                                '"objections":[{"title":"Missing proof","severity":"high",'
                                '"reason":"No payout evidence yet."}],'
                                '"missing_evidence":["payout confirmation"],'
                                '"stale_information_risks":[],'
                                '"overlooked_constraints":["terms may have changed"],'
                                '"counterarguments":["Could still succeed with more proof"],'
                                '"recommended_followups":["capture rules snapshot"]}'
                            )
                        },
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            },
        )

    plugin, ledger_service = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OPENAI,
        handler=httpx.MockTransport(handler),
    )

    result = plugin.review(make_review_request(), required=True)

    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.INNER_VOICE_REVIEW,
        related_id="review_001",
    )
    assert result.recommended_disposition is InnerVoiceDisposition.NEEDS_REVIEW
    assert result.objections[0] == InnerVoiceObjection(
        title="Missing proof",
        severity=InnerVoiceObjectionSeverity.HIGH,
        reason="No payout evidence yet.",
    )
    assert len(evidence) == 2


def test_openai_adapter_rejects_incompatible_model_for_json_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")
    plugin, _ = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OPENAI,
        handler=httpx.MockTransport(
            lambda request: pytest.fail("provider should not be called for incompatible models")
        ),
        config_overrides={"model_name": "text-embedding-3-large"},
    )

    with pytest.raises(InnerVoicePluginError, match="structured JSON"):
        plugin.review(make_review_request(), required=True)


def test_build_inner_voice_prompt_bounds_and_marks_stale_evidence() -> None:
    old_timestamp = (datetime.now(tz=UTC) - timedelta(days=90)).isoformat()
    request = make_review_request().model_copy(
        update={
            "claim_summary": "A" * 500,
            "structured_context": {"mission": "x" * 500},
            "budget_summary": "C" * 2_000,
            "evidence_summary": [
                EvidenceSummary(
                    evidence_id="ev_2",
                    evidence_type="snapshot",
                    source_url="https://example.com/rules",
                    captured_at=old_timestamp,
                    summary="B" * 800,
                ),
                EvidenceSummary(
                    evidence_id="ev_1",
                    evidence_type="snapshot",
                    source_url="https://example.com/rules",
                    captured_at=old_timestamp,
                    summary="duplicate should be dropped",
                ),
            ],
        }
    )

    prompt = build_inner_voice_prompt(
        request,
        provider=ProviderName.OLLAMA,
        model_name="test-model",
        temperature=0.1,
        top_p=0.9,
        max_output_tokens=400,
        timeout_seconds=10.0,
        max_input_chars=1_500,
        max_evidence_items=1,
        max_chars_per_evidence=120,
        stale_evidence_days=30,
    )

    assert len(prompt.system_prompt) + len(prompt.user_prompt) <= 1_500
    assert prompt.user_prompt.count('"evidence_id"') == 1
    assert '"freshness_hint": "stale"' in prompt.user_prompt
    assert "[TRUNCATED:" in prompt.user_prompt


def test_ollama_inner_voice_review_shapes_request(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        payload = json.loads(request.read().decode("utf-8"))
        assert payload["format"] == "json"
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"overall_assessment":"Low risk.",'
                        '"recommended_disposition":"proceed",'
                        '"confidence_adjustment":0,'
                        '"objections":[],'
                        '"missing_evidence":[],'
                        '"stale_information_risks":[],'
                        '"overlooked_constraints":[],'
                        '"counterarguments":[],'
                        '"recommended_followups":[]}'
                    )
                },
                "done_reason": "stop",
                "prompt_eval_count": 12,
                "eval_count": 8,
            },
        )

    plugin, _ = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OLLAMA,
        handler=httpx.MockTransport(handler),
    )

    result = plugin.review(make_review_request())

    assert result.recommended_disposition is InnerVoiceDisposition.PROCEED
    assert result.raw_response_summary.prompt_tokens == 12


def test_inner_voice_health_reports_provider_unreachable(tmp_path: Path) -> None:
    plugin, _ = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OLLAMA,
        handler=httpx.MockTransport(lambda request: httpx.Response(503)),
    )

    health = plugin.health()

    assert health.status == "provider_unreachable"


def test_llama_server_arbiter_shapes_request_and_parses_result(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.read().decode("utf-8"))
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": (
                                '{"final_resolution":"adopt_inner_voice",'
                                '"prevailing_side":"inner_voice",'
                                '"resolution_summary":"The inner voice identified '
                                'the stronger blocker.",'
                                '"rationale_summary":"The evidence gap is material.",'
                                '"required_followups":["capture payment proof"],'
                                '"unresolved_risks":["counterparty uncertainty"]}'
                            )
                        },
                    }
                ],
                "usage": {"prompt_tokens": 15, "completion_tokens": 25},
            },
        )

    service, _ = make_arbiter_service(
        tmp_path,
        provider=ProviderName.LLAMA_SERVER,
        handler=httpx.MockTransport(handler),
    )

    result = service.resolve(
        ArbiterResolutionRequest(
            arbiter_review_id="arbiter_001",
            debate_id="debate_001",
            stage=InnerVoiceStage.PRE_EXECUTION,
            subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
            subject_id="plan_001",
            openclaw_position_summary="Proceed now.",
            inner_voice_position_summary="Stop until the proof is refreshed.",
            disagreement_summary="Proceed now versus wait for refreshed proof.",
            transcript_summary="openclaw: proceed\ninner_voice: wait",
            resolution_goal="Resolve the disagreement.",
            triggered_by=DebateEndedReason.MAX_ROUNDS_REACHED,
        )
    )

    assert result.final_resolution is ArbiterFinalResolution.ADOPT_INNER_VOICE
    assert result.prevailing_side is ArbiterPrevailingSide.INNER_VOICE


def test_llama_server_arbiter_accepts_text_content_parts(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        '{"final_resolution":"adopt_inner_voice",'
                                        '"prevailing_side":"inner_voice",'
                                    ),
                                },
                                {
                                    "type": "text",
                                    "text": (
                                        '"resolution_summary":"The inner voice is correct.",'
                                        '"rationale_summary":"The blocker still stands.",'
                                        '"required_followups":["refresh evidence"],'
                                        '"unresolved_risks":["stale proof"]}'
                                    ),
                                },
                            ]
                        },
                    }
                ]
            },
        )

    service, _ = make_arbiter_service(
        tmp_path,
        provider=ProviderName.LLAMA_SERVER,
        handler=httpx.MockTransport(handler),
    )

    result = service.resolve(
        ArbiterResolutionRequest(
            arbiter_review_id="arbiter_parts_001",
            debate_id="debate_parts_001",
            stage=InnerVoiceStage.PRE_EXECUTION,
            subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
            subject_id="plan_parts_001",
            openclaw_position_summary="Proceed now.",
            inner_voice_position_summary="Stop until evidence is refreshed.",
            disagreement_summary="Proceed now versus wait for refreshed proof.",
            transcript_summary="openclaw: proceed\ninner_voice: wait",
            resolution_goal="Resolve the disagreement.",
            triggered_by=DebateEndedReason.MAX_ROUNDS_REACHED,
        )
    )

    assert result.final_resolution is ArbiterFinalResolution.ADOPT_INNER_VOICE
    assert result.required_followups == ["refresh evidence"]


def test_arbiter_failure_archives_sanitized_request_summary(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not-json"}}]})

    service, ledger_service = make_arbiter_service(
        tmp_path,
        provider=ProviderName.LLAMA_SERVER,
        handler=httpx.MockTransport(handler),
    )

    with pytest.raises(ArbiterResolutionError, match="malformed JSON") as error:
        service.resolve(
            ArbiterResolutionRequest(
                arbiter_review_id="arbiter_failure_001",
                debate_id="debate_001",
                stage=InnerVoiceStage.PRE_EXECUTION,
                subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
                subject_id="plan_001",
                openclaw_position_summary="Proceed now.",
                inner_voice_position_summary="Stop until the proof is refreshed.",
                disagreement_summary="Proceed now versus wait for refreshed proof.",
                transcript_summary="openclaw: proceed\ninner_voice: wait",
                resolution_goal="Resolve the disagreement.",
                triggered_by=DebateEndedReason.MAX_ROUNDS_REACHED,
            )
        )

    assert error.value.failure is not None
    assert error.value.failure.record_id == "arbiter_failure_001"
    assert error.value.failure.record_type is RecordType.ARBITER_REVIEW
    assert error.value.failure.stage == "pre_execution"
    assert error.value.failure.subject_type == "experiment_plan"
    assert error.value.failure.subject_id == "plan_001"
    assert error.value.failure.provider is ProviderName.LLAMA_SERVER
    assert error.value.failure.model_name == "arbiter-model"
    assert error.value.failure.failure_class == "malformed_output"
    assert error.value.failure.failure_message == "Provider returned malformed JSON."
    assert error.value.failure.was_required is True
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.ARBITER_REVIEW,
        related_id="arbiter_failure_001",
    )
    assert {item.evidence_type for item in evidence} >= {"arbiter_prompt", "arbiter_response"}


def test_inner_voice_review_persists_failure_on_malformed_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not-json"}, "finish_reason": "stop"}]},
        )

    plugin, ledger_service = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OPENAI,
        handler=httpx.MockTransport(handler),
    )

    with pytest.raises(InnerVoicePluginError, match="malformed JSON") as error:
        plugin.review(make_review_request(), required=True)

    assert error.value.failure is not None
    assert error.value.failure.record_id == "review_001"
    assert error.value.failure.record_type is RecordType.INNER_VOICE_REVIEW
    assert error.value.failure.stage == "tos_legal_check"
    assert error.value.failure.subject_type == "opportunity"
    assert error.value.failure.subject_id == "opp_001"
    assert error.value.failure.provider is ProviderName.OPENAI
    assert error.value.failure.model_name == "test-model"
    assert error.value.failure.failure_class == "malformed_output"
    assert error.value.failure.failure_message == "Provider returned malformed JSON."
    assert error.value.failure.was_required is True
    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.INNER_VOICE_REVIEW,
        related_id="review_001",
    )
    assert any(item.evidence_type == "inner_voice_failure" for item in evidence)


def test_inner_voice_review_classifies_prompt_too_large_and_persists_failure(
    tmp_path: Path,
) -> None:
    plugin, ledger_service = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OLLAMA,
        handler=httpx.MockTransport(
            lambda request: pytest.fail("provider should not be called for oversized prompts")
        ),
        config_overrides={"max_input_chars": 250},
    )

    with pytest.raises(InnerVoicePluginError) as error:
        plugin.review(
            make_review_request().model_copy(
                update={
                    "claim_summary": "C" * 2_000,
                    "structured_context": {"mission": "y" * 4_000},
                }
            ),
            required=True,
        )

    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.INNER_VOICE_REVIEW,
        related_id="review_001",
    )
    assert error.value.failure_class == "prompt_too_large"
    assert any(item.evidence_type == "inner_voice_failure" for item in evidence)


class StaticResponder:
    """Simple deterministic responder used in debate tests."""

    def __init__(self, outputs: list[DebateResponderOutput]) -> None:
        self._outputs = iter(outputs)

    def respond_to_debate(self, request: DebateResponderRequest) -> DebateResponderOutput:
        return next(self._outputs)


def test_debate_converges_without_arbiter(tmp_path: Path) -> None:
    def inner_voice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"turn_type":"concession",'
                        '"message_text":"I agree after reviewing the same evidence.",'
                        '"cited_evidence_ids":["ev_1"],'
                        '"disposition_signal":"proceed",'
                        '"max_unresolved_severity":"low",'
                        '"request_arbiter":false}'
                    )
                },
                "done_reason": "stop",
            },
        )

    inner_voice, ledger_service = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OLLAMA,
        handler=httpx.MockTransport(inner_voice_handler),
    )
    arbiter, _ = make_arbiter_service(
        tmp_path,
        provider=ProviderName.LLAMA_SERVER,
        handler=httpx.MockTransport(lambda request: httpx.Response(500)),
    )
    coordinator = InnerVoiceCoordinator(
        inner_voice,
        arbiter,
        inner_voice.archiver,
        ledger_service,
    )

    outcome = coordinator.run_debate(
        InnerVoiceDebateRequest(
            stage=InnerVoiceStage.BUDGET_PLANNING,
            subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
            subject_id="plan_001",
            review_goal="Resolve the disagreement.",
            claim_summary="The plan should move forward.",
            disagreement_summary="Proceed or stop.",
            openclaw_initial_position="Proceed with the plan.",
            openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
            openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
            max_debate_rounds=2,
        ),
        openclaw=StaticResponder([]),
    )

    assert outcome.session.ended_reason is DebateEndedReason.CONVERGED
    assert outcome.arbiter_result is None
    transcript_evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.INNER_VOICE_DEBATE,
        related_id=outcome.session.debate_id,
    )
    assert any(
        item.evidence_type == "inner_voice_debate_transcript"
        for item in transcript_evidence
    )
    audit_events = ledger_service.get_related_events(
        related_type=RecordType.AUDIT_EVENT,
    )
    event_names = {
        cast(dict[str, object], event.payload["payload"]).get("event_name")
        for event in audit_events
        if isinstance(event.payload.get("payload"), dict)
    }
    assert {"inner_voice_debate_started", "inner_voice_debate_completed"} <= event_names


def test_debate_max_rounds_reached_invokes_arbiter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")

    def inner_voice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"turn_type":"objection",'
                        '"message_text":"I still disagree because the evidence is stale.",'
                        '"cited_evidence_ids":["ev_2"],'
                        '"disposition_signal":"needs_review",'
                        '"max_unresolved_severity":"high",'
                        '"request_arbiter":false}'
                    )
                },
                "done_reason": "stop",
            },
        )

    def arbiter_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": (
                                '{"final_resolution":"needs_review",'
                                '"prevailing_side":"neither",'
                                '"resolution_summary":"More evidence is needed.",'
                                '"rationale_summary":"The disagreement centers on stale evidence.",'
                                '"required_followups":["refresh the rules snapshot"],'
                                '"unresolved_risks":["stale terms"]}'
                            )
                        },
                    }
                ]
            },
        )

    inner_voice, ledger_service = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OLLAMA,
        handler=httpx.MockTransport(inner_voice_handler),
    )
    arbiter, _ = make_arbiter_service(
        tmp_path,
        provider=ProviderName.OPENAI,
        handler=httpx.MockTransport(arbiter_handler),
    )
    coordinator = InnerVoiceCoordinator(
        inner_voice,
        arbiter,
        inner_voice.archiver,
        ledger_service,
    )

    outcome = coordinator.run_debate(
        InnerVoiceDebateRequest(
            stage=InnerVoiceStage.PRE_EXECUTION,
            subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
            subject_id="plan_001",
            openclaw_review_id="openclaw_review_001",
            inner_voice_review_id="inner_voice_review_001",
            review_goal="Resolve the disagreement.",
            claim_summary="The plan should move forward.",
            disagreement_summary="Proceed or stop.",
            openclaw_initial_position="Proceed with the plan now.",
            openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
            openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
            max_debate_rounds=1,
        ),
        openclaw=StaticResponder([]),
    )

    assert outcome.session.ended_reason is DebateEndedReason.MAX_ROUNDS_REACHED
    assert outcome.arbiter_result is not None
    assert outcome.arbiter_result.final_resolution is ArbiterFinalResolution.NEEDS_REVIEW
    assert outcome.session.openclaw_review_id == "openclaw_review_001"
    assert outcome.session.inner_voice_review_id == "inner_voice_review_001"
    audit_events = ledger_service.get_related_events(
        related_type=RecordType.AUDIT_EVENT,
    )
    event_names = {
        cast(dict[str, object], event.payload["payload"]).get("event_name")
        for event in audit_events
        if isinstance(event.payload.get("payload"), dict)
    }
    assert "inner_voice_arbiter_escalation_requested" in event_names
    debate_evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.INNER_VOICE_DEBATE,
        related_id=outcome.session.debate_id,
    )
    summary_record = next(
        item for item in debate_evidence if item.evidence_type == "inner_voice_debate_summary"
    )
    summary_text = Path(summary_record.archive_path).read_text(encoding="utf-8")
    assert "openclaw_review_001" in summary_text
    assert "inner_voice_review_001" in summary_text
    assert "arbiter_review_id" in summary_text


def test_openclaw_arbiter_request_invokes_arbiter(tmp_path: Path) -> None:
    def inner_voice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"turn_type":"objection",'
                        '"message_text":"I disagree but I can continue debating.",'
                        '"cited_evidence_ids":["ev_2"],'
                        '"disposition_signal":"needs_review",'
                        '"max_unresolved_severity":"medium",'
                        '"request_arbiter":false}'
                    )
                },
                "done_reason": "stop",
            },
        )

    def arbiter_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"final_resolution":"adopt_openclaw",'
                                '"prevailing_side":"openclaw",'
                                '"resolution_summary":"The current evidence supports proceeding.",'
                                '"rationale_summary":"The blocker is not material.",'
                                '"required_followups":[],'
                                '"unresolved_risks":[]}'
                            )
                        },
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    inner_voice, ledger_service = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OLLAMA,
        handler=httpx.MockTransport(inner_voice_handler),
    )
    arbiter, _ = make_arbiter_service(
        tmp_path,
        provider=ProviderName.LLAMA_SERVER,
        handler=httpx.MockTransport(arbiter_handler),
    )
    coordinator = InnerVoiceCoordinator(
        inner_voice,
        arbiter,
        inner_voice.archiver,
        ledger_service,
    )
    openclaw = StaticResponder(
        [
            DebateResponderOutput(
                turn_type=DebateTurnType.REQUEST_ARBITER,
                message_text="I request Arbiter resolution.",
                disposition_signal=InnerVoiceDisposition.PROCEED,
                request_arbiter=True,
            )
        ]
    )

    outcome = coordinator.run_debate(
        InnerVoiceDebateRequest(
            stage=InnerVoiceStage.PRE_EXECUTION,
            subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
            subject_id="plan_001",
            review_goal="Resolve the disagreement.",
            claim_summary="The plan should move forward.",
            disagreement_summary="Proceed or stop.",
            openclaw_initial_position="Proceed with the plan now.",
            openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
            openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
            max_debate_rounds=2,
        ),
        openclaw=openclaw,
    )

    assert outcome.session.ended_reason is DebateEndedReason.REQUEST_ARBITER
    assert outcome.session.arbiter_requested_by is DebateSpeaker.OPENCLAW
    assert outcome.arbiter_result is not None


def test_arbiter_failure_results_in_debate_error_and_failed_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")

    def inner_voice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"turn_type":"objection",'
                        '"message_text":"I still disagree because the evidence is stale.",'
                        '"cited_evidence_ids":["ev_2"],'
                        '"disposition_signal":"needs_review",'
                        '"max_unresolved_severity":"high",'
                        '"request_arbiter":false}'
                    )
                },
                "done_reason": "stop",
            },
        )

    def arbiter_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not-json"}}]})

    inner_voice, ledger_service = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OLLAMA,
        handler=httpx.MockTransport(inner_voice_handler),
    )
    arbiter, _ = make_arbiter_service(
        tmp_path,
        provider=ProviderName.OPENAI,
        handler=httpx.MockTransport(arbiter_handler),
    )
    coordinator = InnerVoiceCoordinator(
        inner_voice,
        arbiter,
        inner_voice.archiver,
        ledger_service,
    )

    with pytest.raises(InnerVoiceDebateError) as error:
        coordinator.run_debate(
            InnerVoiceDebateRequest(
                stage=InnerVoiceStage.PRE_EXECUTION,
                subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
                subject_id="plan_001",
                review_goal="Resolve the disagreement.",
                claim_summary="The plan should move forward.",
                disagreement_summary="Proceed or stop.",
                openclaw_initial_position="Proceed with the plan now.",
                openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
                openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
                max_debate_rounds=1,
            ),
            openclaw=StaticResponder([]),
        )

    assert error.value.failure is not None
    assert error.value.failure.record_type is RecordType.INNER_VOICE_DEBATE
    assert error.value.failure.stage == "pre_execution"
    assert error.value.failure.subject_type == "experiment_plan"
    assert error.value.failure.subject_id == "plan_001"
    assert error.value.failure.failure_class == "malformed_output"
    assert error.value.failure.failure_message == "Provider returned malformed JSON."
    debate_records = ledger_service.get_related_events(related_id="plan_001")
    assert debate_records or ledger_service.get_opportunity("plan_001") is None
    audit_events = ledger_service.get_related_events(
        related_type=RecordType.AUDIT_EVENT,
    )
    event_names = {
        cast(dict[str, object], event.payload["payload"]).get("event_name")
        for event in audit_events
        if isinstance(event.payload.get("payload"), dict)
    }
    assert "inner_voice_arbiter_invocation_failed" in event_names


def test_debate_archives_placeholder_when_raw_transcript_disabled(tmp_path: Path) -> None:
    def inner_voice_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": (
                        '{"turn_type":"concession",'
                        '"message_text":"I agree after reviewing the same evidence.",'
                        '"cited_evidence_ids":["ev_1"],'
                        '"disposition_signal":"proceed",'
                        '"max_unresolved_severity":"low",'
                        '"request_arbiter":false}'
                    )
                },
                "done_reason": "stop",
            },
        )

    inner_voice, ledger_service = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OLLAMA,
        handler=httpx.MockTransport(inner_voice_handler),
        config_overrides={
            "archive_debate_transcript": False,
            "archive_debate_turn_metadata": False,
        },
    )
    arbiter, _ = make_arbiter_service(
        tmp_path,
        provider=ProviderName.LLAMA_SERVER,
        handler=httpx.MockTransport(lambda request: httpx.Response(500)),
    )
    coordinator = InnerVoiceCoordinator(
        inner_voice,
        arbiter,
        inner_voice.archiver,
        ledger_service,
    )

    outcome = coordinator.run_debate(
        InnerVoiceDebateRequest(
            stage=InnerVoiceStage.BUDGET_PLANNING,
            subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
            subject_id="plan_001",
            review_goal="Resolve the disagreement.",
            claim_summary="The plan should move forward.",
            disagreement_summary="Proceed or stop.",
            openclaw_initial_position="Proceed with the plan.",
            openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
            openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
            max_debate_rounds=2,
        ),
        openclaw=StaticResponder([]),
    )

    evidence = ledger_service.list_evidence_for_related(
        related_type=RecordType.INNER_VOICE_DEBATE,
        related_id=outcome.session.debate_id,
    )
    transcript_record = next(
        item for item in evidence if item.evidence_type == "inner_voice_debate_transcript"
    )
    summary_record = next(
        item for item in evidence if item.evidence_type == "inner_voice_debate_summary"
    )
    transcript_text = Path(transcript_record.archive_path).read_text(encoding="utf-8")
    summary_text = Path(summary_record.archive_path).read_text(encoding="utf-8")

    assert "transcript_raw_archival_disabled" in transcript_text
    assert "I agree after reviewing the same evidence." not in transcript_text
    assert '"turns"' not in summary_text


def test_build_metrics_snapshot_summarizes_debate_and_arbiter_results(tmp_path: Path) -> None:
    call_count = 0

    def inner_voice_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            content = (
                '{"overall_assessment":"The review found no material blocker.",'
                '"recommended_disposition":"proceed",'
                '"confidence_adjustment":0,'
                '"objections":[{"title":"Need receipt","severity":"low",'
                '"reason":"Receipt proof is still pending.","evidence_basis":"ev_1"}],'
                '"missing_evidence":["receipt"],'
                '"stale_information_risks":[],'
                '"overlooked_constraints":[],'
                '"counterarguments":[],'
                '"recommended_followups":["collect receipt"]}'
            )
        else:
            content = (
                '{"turn_type":"concession",'
                '"message_text":"I agree after reviewing the same evidence.",'
                '"cited_evidence_ids":["ev_1"],'
                '"disposition_signal":"proceed",'
                '"max_unresolved_severity":"low",'
                '"request_arbiter":false}'
            )
        return httpx.Response(
            200,
            json={
                "message": {"content": content},
                "done_reason": "stop",
            },
        )

    inner_voice, ledger_service = make_inner_voice_plugin(
        tmp_path,
        provider=ProviderName.OLLAMA,
        handler=httpx.MockTransport(inner_voice_handler),
    )
    arbiter, _ = make_arbiter_service(
        tmp_path,
        provider=ProviderName.LLAMA_SERVER,
        handler=httpx.MockTransport(lambda request: httpx.Response(500)),
    )
    coordinator = InnerVoiceCoordinator(
        inner_voice,
        arbiter,
        inner_voice.archiver,
        ledger_service,
    )
    review = inner_voice.review(
        make_review_request().model_copy(update={"review_id": "review_metrics"})
    )
    outcome = coordinator.run_debate(
        InnerVoiceDebateRequest(
            stage=InnerVoiceStage.BUDGET_PLANNING,
            subject_type=InnerVoiceSubjectType.EXPERIMENT_PLAN,
            subject_id="plan_001",
            review_goal="Resolve the disagreement.",
            claim_summary="The plan should move forward.",
            disagreement_summary="Proceed or stop.",
            openclaw_initial_position="Proceed with the plan.",
            openclaw_initial_disposition=InnerVoiceDisposition.PROCEED,
            openclaw_initial_max_unresolved_severity=InnerVoiceObjectionSeverity.LOW,
            max_debate_rounds=2,
        ),
        openclaw=StaticResponder([]),
    )

    snapshot = build_metrics_snapshot([review], [outcome], [])

    assert snapshot.invocation_count_by_stage["tos_legal_check"] == 1
    assert snapshot.debate_session_count_by_stage["budget_planning"] == 1
    assert snapshot.average_prompt_size_chars > 0
    assert snapshot.average_response_size_chars > 0
    metrics_record = persist_metrics_snapshot(
        snapshot,
        ledger_service=ledger_service,
        archiver=inner_voice.archiver,
        snapshot_id="inner_voice_metrics_001",
    )
    review_records = list_inner_voice_reviews(
        ledger_service,
        subject_id="opp_001",
        stage=InnerVoiceStage.TOS_LEGAL_CHECK,
        outcome="proceed",
    )
    debate_records = list_inner_voice_debates(
        ledger_service,
        subject_id="plan_001",
        stage=InnerVoiceStage.BUDGET_PLANNING,
        outcome="proceed",
    )
    arbiter_records = list_arbiter_reviews(
        ledger_service,
        subject_id="plan_001",
        stage=InnerVoiceStage.BUDGET_PLANNING,
        outcome="needs_review",
    )

    assert metrics_record.record_type is RecordType.METRICS_EXPORT
    assert review_records[0].record_id == "review_metrics"
    assert debate_records[0].payload["transcript_archive_ids"]
    assert arbiter_records == []
