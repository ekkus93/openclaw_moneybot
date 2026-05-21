"""Deterministic deliverable validation."""

from __future__ import annotations

from openclaw_moneybot.shared import ArchiveConfig
from openclaw_moneybot.shared.types import DeliverableValidationOutcome, RecordType
from openclaw_moneybot.skills.deliverable_quality_checker.models import (
    DeliverableQualityCheckRequest,
    DeliverableQualityCheckResult,
)
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import ReceiptAndEvidenceArchiver
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id

PLACEHOLDER_MARKERS = ("todo", "tbd", "lorem ipsum", "[todo]")


class DeliverableQualityChecker:
    """Verify required deliverables before submission or review completion."""

    def __init__(self, archive_config: ArchiveConfig, ledger_service: LedgerService) -> None:
        self.ledger_service = ledger_service
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)

    def evaluate(
        self,
        request: DeliverableQualityCheckRequest,
    ) -> DeliverableQualityCheckResult:
        """Validate required fields and artifacts."""
        quality_id = make_id("deliverable_quality")
        artifacts_by_name = {item.artifact_name.lower(): item for item in request.artifacts}
        missing_items: list[str] = []
        invalid_items: list[str] = []
        warnings: list[str] = []
        passed_checks: list[str] = []

        for field_name in request.required_fields:
            value = request.field_values.get(field_name, "").strip()
            if not value:
                missing_items.append(f"field:{field_name}")
                continue
            if any(marker in value.lower() for marker in PLACEHOLDER_MARKERS):
                invalid_items.append(f"field:{field_name}")
                continue
            passed_checks.append(f"field:{field_name}")

        for artifact_name in request.required_artifacts:
            artifact = artifacts_by_name.get(artifact_name.lower())
            if artifact is None:
                missing_items.append(f"artifact:{artifact_name}")
                continue
            if artifact.content_text and any(
                marker in artifact.content_text.lower() for marker in PLACEHOLDER_MARKERS
            ):
                invalid_items.append(f"artifact:{artifact_name}")
                continue
            if (
                artifact.expected_sha256 is not None
                and artifact.actual_sha256 is not None
                and artifact.expected_sha256 != artifact.actual_sha256
            ):
                invalid_items.append(f"hash:{artifact_name}")
                continue
            if artifact.evidence_archive_id is None:
                warnings.append(f"artifact:{artifact_name}:missing_evidence_link")
            passed_checks.append(f"artifact:{artifact_name}")

        missing_references = [
            reference_id
            for reference_id in request.expected_reference_ids
            if not any(
                reference_id in (artifact.content_text or "")
                for artifact in request.artifacts
            )
        ]
        for reference_id in missing_references:
            invalid_items.append(f"reference:{reference_id}")

        if invalid_items or missing_items:
            status = DeliverableValidationOutcome.FAILED
        elif warnings:
            status = DeliverableValidationOutcome.NEEDS_REVIEW
        else:
            status = DeliverableValidationOutcome.PASSED

        snapshot = {
            "submission_package_id": request.submission_package_id,
            "status": status.value,
            "missing_items": missing_items,
            "invalid_items": invalid_items,
            "warnings": warnings,
            "passed_checks": passed_checks,
        }
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.DELIVERABLE_QUALITY,
            related_id=quality_id,
            evidence_type="deliverable_manifest",
            payload=snapshot,
            notes="Deliverable quality validation snapshot",
        )
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=quality_id,
            record_type=RecordType.DELIVERABLE_QUALITY,
            related_record_id=request.opportunity_id,
            payload={
                **snapshot,
                "evidence_archive_ids": [*request.evidence_archive_ids, evidence_id],
            },
        )
        return DeliverableQualityCheckResult(
            deliverable_quality_id=quality_id,
            status=status,
            missing_items=missing_items,
            invalid_items=invalid_items,
            warnings=warnings,
            passed_checks=passed_checks,
            evidence_archive_ids=[*request.evidence_archive_ids, evidence_id],
            ledger_record=ledger_record,
        )
