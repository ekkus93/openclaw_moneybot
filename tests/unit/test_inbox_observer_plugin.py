"""Unit tests for the inbox observer plugin."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from openclaw_moneybot.plugins.inbox_observer_plugin import (
    InboxAttachment,
    InboxMessageInput,
    InboxObservationRequest,
    InboxObserverPlugin,
)
from openclaw_moneybot.shared import ArchiveConfig, InboxObserverConfig
from openclaw_moneybot.shared.types import InboundMessageClassification
from openclaw_moneybot.skills.ledger_skill.service import LedgerService


def make_plugin(tmp_path: Path) -> InboxObserverPlugin:
    return InboxObserverPlugin(
        InboxObserverConfig(enabled=True, mailbox_address="bot@moneybot.local"),
        ArchiveConfig(base_directory=tmp_path / "archive"),
        LedgerService.from_db_path(tmp_path / "moneybot.sqlite3"),
    )


def make_message(**overrides: object) -> InboxMessageInput:
    payload: dict[str, object] = {
        "message_id": "msg_001",
        "thread_id": "thread_001",
        "sender_email": "sender@example.com",
        "subject": "Status update",
        "body": "Generic body",
        "received_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    payload.update(overrides)
    return InboxMessageInput.model_validate(payload)


def test_payout_notice_is_classified_correctly(tmp_path: Path) -> None:
    result = make_plugin(tmp_path).observe(
        InboxObservationRequest(
            mailbox_address="bot@moneybot.local",
            messages=[make_message(subject="Payout sent", body="Your payout txid is 123")],
        )
    )

    assert result.messages[0].classification is InboundMessageClassification.PAYOUT_NOTICE


def test_opt_out_message_is_classified_correctly(tmp_path: Path) -> None:
    result = make_plugin(tmp_path).observe(
        InboxObservationRequest(
            mailbox_address="bot@moneybot.local",
            messages=[make_message(body="Please unsubscribe and stop emailing")],
        )
    )

    assert result.messages[0].classification is InboundMessageClassification.OPT_OUT


def test_complaint_message_is_classified_correctly(tmp_path: Path) -> None:
    result = make_plugin(tmp_path).observe(
        InboxObservationRequest(
            mailbox_address="bot@moneybot.local",
            messages=[make_message(body="This is a spam complaint")],
        )
    )

    assert result.messages[0].classification is InboundMessageClassification.COMPLAINT


def test_unknown_message_stays_unknown(tmp_path: Path) -> None:
    result = make_plugin(tmp_path).observe(
        InboxObservationRequest(
            mailbox_address="bot@moneybot.local",
            messages=[make_message(body="Just checking in")],
        )
    )

    assert result.messages[0].classification is InboundMessageClassification.UNKNOWN


def test_personal_mailbox_config_is_rejected() -> None:
    with pytest.raises(ValueError, match="personal mailbox provider"):
        InboxObserverConfig(mailbox_address="bot@gmail.com")


def test_unsupported_attachment_type_is_quarantined_safely(tmp_path: Path) -> None:
    result = make_plugin(tmp_path).observe(
        InboxObservationRequest(
            mailbox_address="bot@moneybot.local",
            messages=[
                make_message(
                    attachments=[
                        InboxAttachment(
                            filename="payload.exe",
                            size_bytes=100,
                            mime_type="application/octet-stream",
                        )
                    ]
                )
            ],
        )
    )

    assert result.messages[0].attachment_actions["payload.exe"] == "quarantined_unsupported"


def test_thread_linkage_is_preserved(tmp_path: Path) -> None:
    result = make_plugin(tmp_path).observe(
        InboxObservationRequest(
            mailbox_address="bot@moneybot.local",
            messages=[
                make_message(
                    subject="Re: opp_123",
                    body="Payment sent for opp_123",
                    known_reference_ids=["opp_123"],
                )
            ],
        )
    )

    assert result.messages[0].linked_reference_ids == ["opp_123"]
    assert result.thread_summaries[0].linked_reference_ids == ["opp_123"]
