"""Core inner voice critique service."""

from __future__ import annotations

from collections.abc import Mapping

import httpx
from pydantic import JsonValue, ValidationError

from openclaw_moneybot.plugins.inner_voice_plugin.errors import (
    InnerVoicePluginError,
    InnerVoiceProviderError,
)
from openclaw_moneybot.plugins.inner_voice_plugin.models import (
    DebateResponderOutput,
    DebateResponderRequest,
    InnerVoiceDebateTurn,
    InnerVoiceRawResponse,
    InnerVoiceReviewOutput,
    InnerVoiceReviewRequest,
    InnerVoiceReviewResult,
)
from openclaw_moneybot.plugins.inner_voice_plugin.prompting import (
    archive_text,
    build_debate_prompt,
    build_inner_voice_prompt,
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
from openclaw_moneybot.shared import ArchiveConfig, InnerVoiceConfig
from openclaw_moneybot.shared.types import DebateSpeaker, RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    EvidenceArchiveRequest,
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.support import record_structured_result


class InnerVoicePlugin:
    """Generate bounded critique and debate turns through a direct provider adapter."""

    def __init__(
        self,
        config: InnerVoiceConfig,
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

        result = self._provider.health(enabled=self.config.enabled)
        return PluginHealthResult(
            plugin_name="inner_voice_plugin",
            status=result.status,
            enabled=self.config.enabled,
            read_only=True,
        )

    def review(
        self,
        request: InnerVoiceReviewRequest,
        *,
        required: bool = False,
    ) -> InnerVoiceReviewResult:
        """Run one structured inner-voice critique pass."""

        self._ensure_enabled()
        try:
            prompt = build_inner_voice_prompt(
                request,
                provider=self.config.provider,
                model_name=self.config.model_name,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                max_output_tokens=self.config.max_output_tokens,
                timeout_seconds=self.config.timeout_seconds,
                max_input_chars=self.config.max_input_chars,
                max_evidence_items=self.config.max_evidence_items,
                max_chars_per_evidence=self.config.max_chars_per_evidence,
                stale_evidence_days=self.config.stale_evidence_days,
            )
            raw = self._provider.generate(prompt)
            parsed_payload = raw.parsed_json or {}
            output = InnerVoiceReviewOutput.model_validate(parsed_payload)
        except (InnerVoiceProviderError, ValidationError, ValueError) as error:
            failure_class = self._classify_failure(error)
            self._persist_failure(
                review_id=request.review_id,
                stage=request.stage.value,
                subject_type=request.subject_type.value,
                subject_id=request.subject_id,
                failure_class=failure_class,
                failure_message=str(error),
                required=required,
            )
            raise InnerVoicePluginError(str(error), failure_class=failure_class) from error

        evidence_archive_ids = self._archive_prompt_and_response(
            related_id=request.review_id,
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
            record_id=request.review_id,
            record_type=RecordType.INNER_VOICE_REVIEW,
            related_record_id=request.subject_id,
            payload={
                "status": "completed",
                "stage": request.stage.value,
                "subject_type": request.subject_type.value,
                "subject_id": request.subject_id,
                "recommended_disposition": output.recommended_disposition.value,
                "confidence_adjustment": output.confidence_adjustment,
                "objection_count": len(output.objections),
                "evidence_archive_ids": evidence_archive_ids,
                "provider": self.config.provider.value,
                "model_name": self.config.model_name,
            },
        )
        return InnerVoiceReviewResult(
            review_id=request.review_id,
            provider=self.config.provider,
            model_name=self.config.model_name,
            stage=request.stage,
            subject_type=request.subject_type,
            subject_id=request.subject_id,
            overall_assessment=output.overall_assessment,
            recommended_disposition=output.recommended_disposition,
            confidence_adjustment=output.confidence_adjustment,
            objections=output.objections,
            missing_evidence=output.missing_evidence,
            stale_information_risks=output.stale_information_risks,
            overlooked_constraints=output.overlooked_constraints,
            counterarguments=output.counterarguments,
            recommended_followups=output.recommended_followups,
            raw_response_summary=self._raw_response_summary(raw),
            evidence_archive_ids=evidence_archive_ids,
            ledger_record=ledger_record,
        )

    def respond_to_debate(self, request: DebateResponderRequest) -> DebateResponderOutput:
        """Generate one bounded inner-voice debate turn."""

        self._ensure_enabled()
        try:
            prompt = build_debate_prompt(
                request,
                provider=self.config.provider,
                model_name=self.config.model_name,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                max_output_tokens=self.config.max_output_tokens,
                timeout_seconds=self.config.timeout_seconds,
                max_input_chars=self.config.max_input_chars,
                max_evidence_items=self.config.max_evidence_items,
                max_chars_per_evidence=self.config.max_chars_per_evidence,
                stale_evidence_days=self.config.stale_evidence_days,
            )
            raw = self._provider.generate(prompt)
            return DebateResponderOutput.model_validate(raw.parsed_json or {})
        except (InnerVoiceProviderError, ValidationError, ValueError) as error:
            failure_class = self._classify_failure(error)
            raise InnerVoicePluginError(str(error), failure_class=failure_class) from error

    @staticmethod
    def make_debate_turn(
        *,
        debate_id: str,
        round_index: int,
        turn_index: int,
        speaker: DebateSpeaker,
        output: DebateResponderOutput,
        created_at: str,
    ) -> InnerVoiceDebateTurn:
        """Create a persisted debate turn from a participant output."""

        return InnerVoiceDebateTurn(
            debate_id=debate_id,
            round_index=round_index,
            turn_index=turn_index,
            speaker=speaker,
            created_at=created_at,
            turn_type=output.turn_type,
            message_text=output.message_text,
            cited_evidence_ids=output.cited_evidence_ids,
            disposition_signal=output.disposition_signal,
            max_unresolved_severity=output.max_unresolved_severity,
            request_arbiter=output.request_arbiter,
        )

    def _ensure_enabled(self) -> None:
        if not self.config.enabled:
            msg = "inner_voice_plugin is disabled."
            raise ValueError(msg)

    def _archive_prompt_and_response(
        self,
        *,
        related_id: str,
        prompt_payload: Mapping[str, object],
        response_payload: Mapping[str, object],
    ) -> list[str]:
        prompt_archive_id = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.INNER_VOICE_REVIEW,
                related_id=related_id,
                evidence_type="inner_voice_prompt",
                content_text=archive_text(
                    render_json(prompt_payload),
                    raw_allowed=self.config.archive_raw_prompt,
                    redaction_mode=self.config.archive_redaction_mode,
                    max_chars=self.config.max_input_chars,
                ),
                notes=(
                    "Inner voice prompt snapshot"
                    if self.config.archive_raw_prompt
                    else "Inner voice prompt summary (raw archival disabled)"
                ),
                summary_hint="Inner voice prompt snapshot",
            )
        ).evidence_id
        response_archive_id = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.INNER_VOICE_REVIEW,
                related_id=related_id,
                evidence_type="inner_voice_response",
                content_text=archive_text(
                    render_json(response_payload),
                    raw_allowed=self.config.archive_raw_response,
                    redaction_mode=self.config.archive_redaction_mode,
                    max_chars=self.config.max_input_chars,
                ),
                notes=(
                    "Inner voice response snapshot"
                    if self.config.archive_raw_response
                    else "Inner voice response summary (raw archival disabled)"
                ),
                summary_hint="Inner voice response snapshot",
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
                "prompt_chars": raw.prompt_chars,
                "response_chars": len(raw.response_text),
            }
        )

    @staticmethod
    def _classify_failure(error: Exception) -> str:
        if isinstance(error, InnerVoiceProviderError):
            return error.failure_class
        if isinstance(error, ValidationError):
            return "schema_validation_failure"
        if "max_input_chars" in str(error):
            return "prompt_too_large"
        return "provider_error"

    def _persist_failure(
        self,
        *,
        review_id: str,
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
                    related_type=RecordType.INNER_VOICE_REVIEW,
                    related_id=review_id,
                    evidence_type="inner_voice_failure",
                    content_text=sanitize_text(failure_message),
                    notes="Inner voice failure summary",
                    summary_hint=failure_class,
                )
            ).evidence_id
            record_structured_result(
                self.ledger_service,
                record_id=review_id,
                record_type=RecordType.INNER_VOICE_REVIEW,
                related_record_id=subject_id,
                payload={
                    "status": "failed",
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
            related_record_id=review_id,
            event_name="inner_voice_review_failed",
            payload={
                "failure_class": failure_class,
                "failure_message": failure_message,
                "was_required": required,
            },
        )
