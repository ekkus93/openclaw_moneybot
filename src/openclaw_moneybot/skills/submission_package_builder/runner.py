"""Build deterministic submission packages from approved inputs."""

from __future__ import annotations

import re

from openclaw_moneybot.shared import ArchiveConfig
from openclaw_moneybot.shared.types import RecordType, SubmissionReadinessStatus
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import ReceiptAndEvidenceArchiver
from openclaw_moneybot.skills.submission_package_builder.models import (
    SubmissionPackageBuildRequest,
    SubmissionPackageBuildResult,
)
from openclaw_moneybot.skills.support import archive_json_snapshot, record_structured_result
from openclaw_moneybot.utils.ids import make_id


def _extract_list_after_label(text: str, label: str) -> list[str]:
    pattern = rf"{label}\s*:\s*([^\n]+)"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if match is None:
        return []
    return [
        item.strip().lower().replace(" ", "_")
        for item in match.group(1).split(",")
        if item.strip()
    ]


class SubmissionPackageBuilder:
    """Derive a bounded submission checklist from rules text."""

    def __init__(self, archive_config: ArchiveConfig, ledger_service: LedgerService) -> None:
        self.ledger_service = ledger_service
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)

    def build(self, request: SubmissionPackageBuildRequest) -> SubmissionPackageBuildResult:
        """Build a deterministic submission package from approved inputs."""
        submission_package_id = make_id("submission_package")
        text = request.rules_text
        lowered = text.lower()
        required_fields = _extract_list_after_label(text, "required fields")
        required_artifacts = _extract_list_after_label(text, "attachments")
        if "screenshot" in lowered and "screenshot" not in required_artifacts:
            required_artifacts.append("screenshot")
        if "proof" in lowered and "proof" not in required_artifacts:
            required_artifacts.append("proof")
        required_steps = [
            "review_submission_rules",
            "prepare_required_fields",
            "attach_required_artifacts",
            "archive_submission_evidence",
        ]
        required_evidence = [f"{artifact}_evidence" for artifact in required_artifacts]
        quality_checks = [
            "all_required_fields_non_empty",
            "all_required_artifacts_present",
            "opportunity_id_references_consistent",
        ]
        unresolved_items: list[str] = []
        if "required field" in lowered and not required_fields:
            unresolved_items.append("required_fields_not_explicit")
        if "submit at" in lowered and "http" not in lowered:
            unresolved_items.append("submission_url_missing")

        screenshot_counts = {int(value) for value in re.findall(r"(\d+)\s+screenshot", lowered)}
        if len(screenshot_counts) > 1:
            status = SubmissionReadinessStatus.BLOCKED
            unresolved_items.append("conflicting_screenshot_counts")
        elif not text.strip():
            status = SubmissionReadinessStatus.BLOCKED
            unresolved_items.append("missing_rules_text")
        elif unresolved_items:
            status = SubmissionReadinessStatus.NEEDS_REVIEW
        else:
            status = SubmissionReadinessStatus.READY

        submission_url_match = re.search(r"(https?://[^\s]+)", text)
        deadline_match = re.search(r"(deadline\s*:\s*[^\n]+)", text, flags=re.IGNORECASE)
        submission_url = None if submission_url_match is None else submission_url_match.group(1)
        deadline = (
            None
            if deadline_match is None
            else deadline_match.group(1).split(":", 1)[1].strip()
        )
        handoff_notes = [
            "do_not_auto_submit",
            "do_not_invent_missing_fields",
            "stop_if_unresolved_items_remain",
        ]
        snapshot = {
            "opportunity_id": request.opportunity_id,
            "status": status.value,
            "required_steps": required_steps,
            "required_fields": required_fields,
            "required_artifacts": required_artifacts,
            "required_evidence": required_evidence,
            "submission_url": submission_url,
            "deadline": deadline,
            "quality_checks": quality_checks,
            "handoff_notes": handoff_notes,
            "unresolved_items": unresolved_items,
        }
        evidence_id = archive_json_snapshot(
            self.archiver,
            related_type=RecordType.SUBMISSION_PACKAGE,
            related_id=submission_package_id,
            evidence_type="submission_checklist",
            payload=snapshot,
            notes="Deterministic submission package snapshot",
        )
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=submission_package_id,
            record_type=RecordType.SUBMISSION_PACKAGE,
            related_record_id=request.opportunity_id,
            payload={
                **snapshot,
                "evidence_archive_ids": [*request.evidence_archive_ids, evidence_id],
            },
        )
        return SubmissionPackageBuildResult(
            submission_package_id=submission_package_id,
            status=status,
            required_steps=required_steps,
            required_fields=required_fields,
            required_artifacts=required_artifacts,
            required_evidence=required_evidence,
            submission_url=submission_url,
            deadline=deadline,
            quality_checks=quality_checks,
            handoff_notes=handoff_notes,
            unresolved_items=unresolved_items,
            evidence_archive_ids=[*request.evidence_archive_ids, evidence_id],
            ledger_record=ledger_record,
        )
