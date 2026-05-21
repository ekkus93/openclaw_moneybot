"""Unit tests for the artifact renderer plugin."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openclaw_moneybot.plugins.artifact_renderer_plugin import (
    ArtifactRendererPlugin,
    ArtifactRenderRequest,
)
from openclaw_moneybot.shared import ArchiveConfig, ArtifactRendererConfig
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_plugin(tmp_path: Path) -> ArtifactRendererPlugin:
    template_root = tmp_path / "templates"
    template_root.mkdir()
    (template_root / "submission.json").write_text(
        json.dumps(
            {
                "output_filename": "submission.txt",
                "required_fields": ["name", "summary"],
                "body_template": "Name: {name}\nSummary: {summary}\n",
            }
        ),
        encoding="utf-8",
    )
    return ArtifactRendererPlugin(
        ArtifactRendererConfig(
            enabled=True,
            template_root=template_root,
            render_root=tmp_path / "rendered",
        ),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        LedgerService.from_db_path(tmp_path / "moneybot.sqlite3"),
    )


def test_valid_render_request_produces_expected_package_outputs(tmp_path: Path) -> None:
    result = make_plugin(tmp_path).render(
        ArtifactRenderRequest(
            related_record_id="opp_001",
            template_name="submission",
            field_values={"name": "Bot", "summary": "Ready"},
        )
    )

    assert result.rendered_paths[0].read_text(encoding="utf-8").startswith("Name: Bot")
    assert result.manifest_path.exists() is True


def test_missing_required_fields_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Missing required render fields"):
        make_plugin(tmp_path).render(
            ArtifactRenderRequest(
                related_record_id="opp_001",
                template_name="submission",
                field_values={"name": "Bot"},
            )
        )


def test_unknown_template_reference_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown template reference"):
        make_plugin(tmp_path).render(
            ArtifactRenderRequest(
                related_record_id="opp_001",
                template_name="missing",
                field_values={"name": "Bot", "summary": "Ready"},
            )
        )


def test_out_of_bounds_output_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="approved render root"):
        make_plugin(tmp_path).render(
            ArtifactRenderRequest(
                related_record_id="opp_001",
                template_name="submission",
                output_subdir="../escape",
                field_values={"name": "Bot", "summary": "Ready"},
            )
        )


def test_manifest_and_checksums_are_stable_across_repeated_renders(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)
    first = plugin.render(
        ArtifactRenderRequest(
            related_record_id="opp_001",
            template_name="submission",
            field_values={"name": "Bot", "summary": "Ready"},
        )
    )
    second = plugin.render(
        ArtifactRenderRequest(
            related_record_id="opp_001",
            template_name="submission",
            field_values={"name": "Bot", "summary": "Ready"},
        )
    )

    assert first.checksums == second.checksums


def test_malformed_required_fields_type_is_rejected(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)
    (plugin.config.template_root / "bad.json").write_text(
        json.dumps(
            {
                "output_filename": "submission.txt",
                "required_fields": "name",
                "body_template": "Name: {name}",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="required_fields must be a list"):
        plugin.render(
            ArtifactRenderRequest(
                related_record_id="opp_001",
                template_name="bad",
                field_values={"name": "Bot"},
            )
        )


@pytest.mark.parametrize("placeholder", ["TODO", "TBD"])
def test_placeholder_markers_are_rejected(tmp_path: Path, placeholder: str) -> None:
    with pytest.raises(ValueError, match="placeholder markers"):
        make_plugin(tmp_path).render(
            ArtifactRenderRequest(
                related_record_id="opp_001",
                template_name="submission",
                field_values={"name": "Bot", "summary": placeholder},
            )
        )


def test_unknown_evidence_reference_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown evidence reference"):
        make_plugin(tmp_path).render(
            ArtifactRenderRequest(
                related_record_id="opp_001",
                template_name="submission",
                field_values={"name": "Bot", "summary": "Ready"},
                evidence_archive_ids=["missing_evidence"],
            )
        )


def test_template_payload_must_be_a_json_object(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)
    (plugin.config.template_root / "bad.json").write_text(
        '["not", "an", "object"]',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="JSON object"):
        plugin.render(
            ArtifactRenderRequest(
                related_record_id="opp_001",
                template_name="bad",
                field_values={"name": "Bot", "summary": "Ready"},
            )
        )


def test_template_path_escape_attempt_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="approved template root"):
        make_plugin(tmp_path).render(
            ArtifactRenderRequest(
                related_record_id="opp_001",
                template_name="../escape",
                field_values={"name": "Bot", "summary": "Ready"},
            )
        )


def test_absolute_output_subdir_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="approved render root"):
        make_plugin(tmp_path).render(
            ArtifactRenderRequest(
                related_record_id="opp_001",
                template_name="submission",
                output_subdir="/tmp/escape",
                field_values={"name": "Bot", "summary": "Ready"},
            )
        )


def test_resolved_render_path_escape_is_rejected(tmp_path: Path) -> None:
    plugin = make_plugin(tmp_path)
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    plugin.config.render_root.mkdir()
    (plugin.config.render_root / "linked").symlink_to(outside_root, target_is_directory=True)

    with pytest.raises(ValueError, match="approved render root"):
        plugin.render(
            ArtifactRenderRequest(
                related_record_id="opp_001",
                template_name="submission",
                output_subdir="linked",
                field_values={"name": "Bot", "summary": "Ready"},
            )
        )
