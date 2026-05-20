"""Regression checks for code review follow-up docs."""

from __future__ import annotations

from pathlib import Path


def test_code_review_docs_do_not_contain_stale_split_work_guidance() -> None:
    review1 = Path("docs/CODE_REVIEW1_TODO.md").read_text(encoding="utf-8")
    review2 = Path("docs/CODE_REVIEW2_TODO.md").read_text(encoding="utf-8")

    combined = f"{review1}\n{review2}"

    assert "Suggested Work Split Between Copilot and OpenCode" not in combined
    assert "Copilot should focus on:" not in combined
    assert "OpenCode should focus on:" not in combined
    assert "independently implement the same TODO from the same starting codebase" in combined
