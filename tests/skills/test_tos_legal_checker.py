from __future__ import annotations

from skills.tos_legal_checker.models import TosLegalCheckRequest
from skills.tos_legal_checker.runner import run_tos_legal_check


def test_empty_proposed_action_rejects() -> None:
    req = TosLegalCheckRequest(
        opportunity_id="opp-1",
        opportunity_name="Test",
        proposed_action="",
    )
    result = run_tos_legal_check(req)
    assert result.decision == "reject"


def test_gambling_detected() -> None:
    req = TosLegalCheckRequest(
        opportunity_id="opp-2",
        opportunity_name="Gambling test",
        proposed_action="place bet",
        evidence_text="Gambling is prohibited.",
    )
    result = run_tos_legal_check(req)
    assert result.decision == "reject"


def test_proceed_if_clean() -> None:
    req = TosLegalCheckRequest(
        opportunity_id="opp-3",
        opportunity_name="Clean bounty",
        proposed_action="submit bounty",
        evidence_archive_ids=["ev-1"],
    )
    result = run_tos_legal_check(req)
    assert result.decision == "proceed"
