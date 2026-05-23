"""Arbiter disagreement-resolution service."""

from __future__ import annotations

from collections.abc import Mapping

import httpx
from pydantic import JsonValue

from openclaw_moneybot.plugins.inner_voice_plugin.errors import (
    ArbiterResolutionError,
    InnerVoiceProviderError,
)
from openclaw_moneybot.plugins.inner_voice_plugin.models import (
    ArbiterResolutionOutput,
    ArbiterResolutionRequest,
    ArbiterResolutionResult,
    InnerVoiceRawResponse,
)
from openclaw_moneybot.plugins.inner_voice_plugin.prompting import (
    build_arbiter_prompt,
    render_json,
    sanitize_text,
)
from openclaw_moneybot.plugins.inner_voice_plugin.providers import (
    BaseProviderAdapter,
    build_provider_adapter,
)
from openclaw_moneybot.plugins.support import (
    PluginHealthResult,
    json_mapping,
    record_plugin_audit_event,
)
from openclaw_moneybot.shared import ArbiterConfig, ArchiveConfig
from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    EvidenceArchiveRequest,
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.support import record_structured_result


class ArbiterService:
    """Resolve disagreement between OpenClaw and the inner voice."""

    def __init__(
        self,
        config: ArbiterConfig,
        archive_config: ArchiveConfig,
        ledger_service: LedgerService,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)
        self.ledger_service = ledger_service
        self._provider: BaseProviderAdapter = build_provider_adapter(config, transport=transport)

    def close(self) -> None:
        self._provider.close()

    def health(self) -> PluginHealthResult:
        """Return a cheap local health summary."""

        result = self._provider.health(enabled=True)
        return PluginHealthResult(
            plugin_name="arbiter_service",
            status=result.status,
            enabled=True,
            read_only=True,
        )

    def resolve(
        self,
        request: ArbiterResolutionRequest,
        *,
        required: bool = True,
    ) -> ArbiterResolutionResult:
        """Resolve one debate disagreement through the configured Arbiter model."""

        prompt = build_arbiter_prompt(
            request,
            provider=self.config.provider,
            model_name=self.config.model_name,
            temperature=self.config.temperature,
            top_p=self.config.top_p,
            max_output_tokens=self.config.max_output_tokens,
            timeout_seconds=self.config.timeout_seconds,
        )
        try:
            raw = self._provider.generate(prompt)
            output = ArbiterResolutionOutput.model_validate(raw.parsed_json or {})
        except (InnerVoiceProviderError, ValueError) as error:
            self._persist_failure(
                arbiter_review_id=request.arbiter_review_id,
                debate_id=request.debate_id,
                stage=request.stage.value,
                subject_type=request.subject_type.value,
                subject_id=request.subject_id,
                failure_class="provider_error",
                failure_message=str(error),
                required=required,
            )
            raise ArbiterResolutionError(str(error)) from error

        evidence_archive_ids = self._archive_prompt_and_response(
            related_id=request.arbiter_review_id,
            prompt_payload={
                "request": request.model_dump(mode="json"),
                "rendered_prompt": prompt.model_dump(mode="json"),
            },
            response_payload={
                "response_text": raw.response_text,
                "parsed_json": raw.parsed_json,
                "raw_response_summary": self._raw_response_summary(raw),
            },
        )
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=request.arbiter_review_id,
            record_type=RecordType.ARBITER_REVIEW,
            related_record_id=request.subject_id,
            payload={
                "status": "completed",
                "debate_id": request.debate_id,
                "stage": request.stage.value,
                "subject_type": request.subject_type.value,
                "subject_id": request.subject_id,
                "final_resolution": output.final_resolution.value,
                "prevailing_side": output.prevailing_side.value,
                "evidence_archive_ids": evidence_archive_ids,
                "provider": self.config.provider.value,
                "model_name": self.config.model_name,
            },
        )
        return ArbiterResolutionResult(
            arbiter_review_id=request.arbiter_review_id,
            debate_id=request.debate_id,
            provider=self.config.provider,
            model_name=self.config.model_name,
            stage=request.stage,
            subject_type=request.subject_type,
            subject_id=request.subject_id,
            final_resolution=output.final_resolution,
            prevailing_side=output.prevailing_side,
            resolution_summary=output.resolution_summary,
            rationale_summary=output.rationale_summary,
            required_followups=output.required_followups,
            unresolved_risks=output.unresolved_risks,
            raw_response_summary=self._raw_response_summary(raw),
            evidence_archive_ids=evidence_archive_ids,
            ledger_record=ledger_record,
        )

    def _archive_prompt_and_response(
        self,
        *,
        related_id: str,
        prompt_payload: Mapping[str, object],
        response_payload: Mapping[str, object],
    ) -> list[str]:
        prompt_archive_id = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.ARBITER_REVIEW,
                related_id=related_id,
                evidence_type="arbiter_prompt",
                content_text=sanitize_text(render_json(prompt_payload)),
                notes="Arbiter prompt snapshot",
                summary_hint="Sanitized Arbiter prompt snapshot",
            )
        ).evidence_id
        response_archive_id = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.ARBITER_REVIEW,
                related_id=related_id,
                evidence_type="arbiter_response",
                content_text=sanitize_text(render_json(response_payload)),
                notes="Arbiter response snapshot",
                summary_hint="Sanitized Arbiter response snapshot",
            )
        ).evidence_id
        return [prompt_archive_id, response_archive_id]

    @staticmethod
    def _raw_response_summary(raw: InnerVoiceRawResponse) -> dict[str, JsonValue]:
        return json_mapping(
            {
                "finish_reason": raw.finish_reason,
                "prompt_tokens": raw.prompt_tokens,
                "completion_tokens": raw.completion_tokens,
                "response_chars": len(raw.response_text),
            }
        )

    def _persist_failure(
        self,
        *,
        arbiter_review_id: str,
        debate_id: str,
        stage: str,
        subject_type: str,
        subject_id: str,
        failure_class: str,
        failure_message: str,
        required: bool,
    ) -> None:
        if self.config.persist_failures:
            archive_id = self.archiver.archive(
                EvidenceArchiveRequest(
                    related_type=RecordType.ARBITER_REVIEW,
                    related_id=arbiter_review_id,
                    evidence_type="arbiter_response",
                    content_text=sanitize_text(failure_message),
                    notes="Arbiter failure summary",
                    summary_hint=failure_class,
                )
            ).evidence_id
            record_structured_result(
                self.ledger_service,
                record_id=arbiter_review_id,
                record_type=RecordType.ARBITER_REVIEW,
                related_record_id=subject_id,
                payload={
                    "status": "failed",
                    "debate_id": debate_id,
                    "stage": stage,
                    "subject_type": subject_type,
                    "subject_id": subject_id,
                    "provider": self.config.provider.value,
                    "model_name": self.config.model_name,
                    "failure_class": failure_class,
                    "failure_message": failure_message,
                    "was_required": required,
                    "resolved_disposition": "needs_review",
                    "evidence_archive_ids": [archive_id],
                },
            )
        record_plugin_audit_event(
            self.ledger_service,
            related_record_id=arbiter_review_id,
            event_name="arbiter_resolution_failed",
            payload={
                "debate_id": debate_id,
                "failure_class": failure_class,
                "failure_message": failure_message,
                "was_required": required,
            },
        )
