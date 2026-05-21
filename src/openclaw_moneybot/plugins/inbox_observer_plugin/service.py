"""Read-only inbox normalization and classification."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from openclaw_moneybot.plugins.inbox_observer_plugin.models import (
    InboxMessageInput,
    InboxMessageObservationResult,
    InboxObservationRequest,
    InboxObservationResult,
    InboxThreadSummary,
)
from openclaw_moneybot.plugins.support import PluginHealthResult, record_plugin_audit_event
from openclaw_moneybot.shared import ArchiveConfig, InboxObserverConfig
from openclaw_moneybot.shared.types import InboundMessageClassification, RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id


class InboxObserverPlugin:
    """Observe a dedicated bot mailbox without any send capability."""

    def __init__(
        self,
        config: InboxObserverConfig,
        archive_config: ArchiveConfig,
        ledger_service: LedgerService,
    ) -> None:
        self.config = config
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)
        self.ledger_service = ledger_service

    def health(self) -> PluginHealthResult:
        """Return local plugin health metadata."""

        return PluginHealthResult(
            plugin_name="inbox_observer_plugin",
            enabled=self.config.enabled,
            read_only=True,
        )

    def observe(self, request: InboxObservationRequest) -> InboxObservationResult:
        """Normalize, classify, and archive inbound mailbox state."""

        if request.mailbox_address != self.config.mailbox_address:
            record_plugin_audit_event(
                self.ledger_service,
                related_record_id=request.mailbox_address,
                event_name="inbox_observation_failed",
                payload={"reason": "mailbox_not_allowlisted"},
            )
            msg = "Only the configured bot mailbox may be observed."
            raise ValueError(msg)

        message_results: list[InboxMessageObservationResult] = []
        thread_classifications: defaultdict[str, list[InboundMessageClassification]] = defaultdict(
            list
        )
        thread_references: defaultdict[str, set[str]] = defaultdict(set)
        for message in request.messages:
            result = self._observe_message(message)
            message_results.append(result)
            thread_classifications[result.thread_id].append(result.classification)
            thread_references[result.thread_id].update(result.linked_reference_ids)
        thread_summaries = [
            InboxThreadSummary(
                thread_id=thread_id,
                classifications=classifications,
                linked_reference_ids=sorted(thread_references[thread_id]),
            )
            for thread_id, classifications in thread_classifications.items()
        ]
        return InboxObservationResult(
            messages=message_results,
            thread_summaries=thread_summaries,
        )

    def _observe_message(self, message: InboxMessageInput) -> InboxMessageObservationResult:
        observation_id = make_id("inbox_observation")
        classification = self._classify(message)
        attachment_actions = {
            attachment.filename: self._attachment_action(attachment.filename, attachment.size_bytes)
            for attachment in message.attachments
        }
        linked_reference_ids = [
            reference_id
            for reference_id in message.known_reference_ids
            if reference_id in f"{message.subject}\n{message.body}"
        ]
        safe_excerpt = message.body[: self.config.max_body_excerpt_chars]
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.INBOX_OBSERVATION,
            related_id=observation_id,
            evidence_type="inbox_message_snapshot",
            payload={
                "message_id": message.message_id,
                "thread_id": message.thread_id,
                "sender_email": message.sender_email,
                "subject": message.subject,
                "body_excerpt": safe_excerpt,
                "classification": classification.value,
                "linked_reference_ids": linked_reference_ids,
                "attachment_actions": attachment_actions,
            },
            notes="Observed inbound mailbox message",
        )
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=observation_id,
            record_type=RecordType.INBOX_OBSERVATION,
            related_record_id=message.thread_id,
            payload={
                "message_id": message.message_id,
                "thread_id": message.thread_id,
                "classification": classification.value,
                "linked_reference_ids": linked_reference_ids,
                "attachment_actions": attachment_actions,
                "evidence_archive_ids": [evidence_id],
            },
        )
        return InboxMessageObservationResult(
            observation_id=observation_id,
            message_id=message.message_id,
            thread_id=message.thread_id,
            classification=classification,
            linked_reference_ids=linked_reference_ids,
            attachment_actions=attachment_actions,
            evidence_archive_ids=[evidence_id],
            ledger_record=ledger_record,
        )

    @staticmethod
    def _classify(message: InboxMessageInput) -> InboundMessageClassification:
        haystack = f"{message.subject}\n{message.body}".lower()
        if "complaint" in haystack or "spam" in haystack:
            return InboundMessageClassification.COMPLAINT
        if "unsubscribe" in haystack or "opt out" in haystack or "stop emailing" in haystack:
            return InboundMessageClassification.OPT_OUT
        if "payout" in haystack or "payment sent" in haystack or "txid" in haystack:
            return InboundMessageClassification.PAYOUT_NOTICE
        if "unfortunately" in haystack or "decline" in haystack or "reject" in haystack:
            return InboundMessageClassification.REJECTION
        if "approved" in haystack or "accepted" in haystack or "thank you" in haystack:
            return InboundMessageClassification.POSITIVE_RESPONSE
        return InboundMessageClassification.UNKNOWN

    def _attachment_action(self, filename: str, size_bytes: int) -> str:
        if size_bytes > self.config.max_attachment_bytes:
            return "rejected_oversized"
        extension = Path(filename).suffix.lower()
        if extension not in self.config.allowed_attachment_extensions:
            return "quarantined_unsupported"
        return "metadata_only"
