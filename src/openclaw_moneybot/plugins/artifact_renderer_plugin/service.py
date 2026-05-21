"""Deterministically render submission and proof artifacts."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from openclaw_moneybot.plugins.artifact_renderer_plugin.models import (
    ArtifactRenderRequest,
    ArtifactRenderResult,
)
from openclaw_moneybot.plugins.support import PluginHealthResult, record_plugin_audit_event
from openclaw_moneybot.shared import ArchiveConfig, ArtifactRendererConfig
from openclaw_moneybot.shared.types import ArtifactRenderOutcome, RecordType
from openclaw_moneybot.skills.ledger_skill.service import LedgerService
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    EvidenceArchiveRequest,
    ReceiptAndEvidenceArchiver,
)
from openclaw_moneybot.skills.support import record_structured_result
from openclaw_moneybot.utils.ids import make_id


class ArtifactRendererPlugin:
    """Render local artifact bundles from approved templates only."""

    def __init__(
        self,
        config: ArtifactRendererConfig,
        archive_config: ArchiveConfig,
        ledger_service: LedgerService,
    ) -> None:
        self.config = config
        self.archiver = ReceiptAndEvidenceArchiver(archive_config, ledger_service)
        self.ledger_service = ledger_service

    def health(self) -> PluginHealthResult:
        return PluginHealthResult(
            plugin_name="artifact_renderer_plugin",
            enabled=self.config.enabled,
            read_only=False,
        )

    def render(self, request: ArtifactRenderRequest) -> ArtifactRenderResult:
        """Render a deterministic artifact bundle."""

        template = self._load_template(request.template_name)
        required_fields = template.get("required_fields", [])
        if not isinstance(required_fields, list):
            msg = "Template required_fields must be a list."
            raise ValueError(msg)
        missing_fields = [
            field_name
            for field_name in required_fields
            if not request.field_values.get(str(field_name))
        ]
        if missing_fields:
            missing_field_names = ", ".join(str(item) for item in missing_fields)
            msg = f"Missing required render fields: {missing_field_names}"
            raise ValueError(msg)
        if any(value.strip().upper() in {"TODO", "TBD"} for value in request.field_values.values()):
            msg = "Render field values may not contain placeholder markers."
            raise ValueError(msg)
        for evidence_id in request.evidence_archive_ids:
            if self.ledger_service.get_evidence_record(evidence_id) is None:
                msg = f"Unknown evidence reference for render: {evidence_id}"
                raise ValueError(msg)

        render_id = make_id("rendered_artifact")
        render_dir = self._resolve_render_dir(render_id, request.output_subdir)
        render_dir.mkdir(parents=True, exist_ok=True)
        filename = str(template.get("output_filename", "artifact.txt"))
        body_template = str(template.get("body_template", ""))
        rendered_body = body_template.format(**request.field_values)
        output_path = render_dir / filename
        output_path.write_text(rendered_body, encoding="utf-8")
        checksums = {filename: sha256(rendered_body.encode("utf-8")).hexdigest()}
        manifest_path = render_dir / "manifest.json"
        manifest_payload = {
            "render_id": render_id,
            "template_name": request.template_name,
            "files": [
                {
                    "path": filename,
                    "sha256": checksums[filename],
                }
            ],
            "evidence_archive_ids": sorted(request.evidence_archive_ids),
        }
        manifest_path.write_text(
            json.dumps(manifest_payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        rendered_evidence = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.RENDERED_ARTIFACT,
                related_id=render_id,
                evidence_type="rendered_artifact_bundle",
                content_text=rendered_body,
                notes="Rendered artifact bundle output",
            )
        )
        manifest_evidence = self.archiver.archive(
            EvidenceArchiveRequest(
                related_type=RecordType.RENDERED_ARTIFACT,
                related_id=render_id,
                evidence_type="rendered_artifact_manifest",
                content_text=manifest_path.read_text(encoding="utf-8"),
                notes="Rendered artifact manifest",
            )
        )
        all_evidence_ids = [
            *request.evidence_archive_ids,
            rendered_evidence.evidence_id,
            manifest_evidence.evidence_id,
        ]
        ledger_record = record_structured_result(
            self.ledger_service,
            record_id=render_id,
            record_type=RecordType.RENDERED_ARTIFACT,
            related_record_id=request.related_record_id,
            payload={
                "template_name": request.template_name,
                "rendered_paths": [str(output_path)],
                "manifest_path": str(manifest_path),
                "checksums": checksums,
                "evidence_archive_ids": all_evidence_ids,
            },
        )
        record_plugin_audit_event(
            self.ledger_service,
            related_record_id=render_id,
            event_name="artifact_rendered",
            payload={"template_name": request.template_name, "output_path": str(output_path)},
        )
        return ArtifactRenderResult(
            render_id=render_id,
            outcome=ArtifactRenderOutcome.RENDERED,
            rendered_paths=[output_path],
            manifest_path=manifest_path,
            checksums=checksums,
            evidence_archive_ids=all_evidence_ids,
            ledger_record=ledger_record,
        )

    def _load_template(self, template_name: str) -> dict[str, object]:
        template_path = (self.config.template_root / f"{template_name}.json").resolve()
        if not str(template_path).startswith(str(self.config.template_root.resolve())):
            msg = "Template path escaped the approved template root."
            raise ValueError(msg)
        if not template_path.exists():
            msg = f"Unknown template reference: {template_name}"
            raise ValueError(msg)
        payload = json.loads(template_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            msg = "Template payload must be a JSON object."
            raise ValueError(msg)
        return payload

    def _resolve_render_dir(self, render_id: str, output_subdir: str) -> Path:
        if output_subdir.startswith("/") or ".." in Path(output_subdir).parts:
            msg = "Render output path must stay within the approved render root."
            raise ValueError(msg)
        render_dir = (self.config.render_root / output_subdir / render_id).resolve()
        if not str(render_dir).startswith(str(self.config.render_root.resolve())):
            msg = "Render output path must stay within the approved render root."
            raise ValueError(msg)
        return render_dir
