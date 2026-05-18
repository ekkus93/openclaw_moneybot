"""Source adapters for opportunity scouting."""

from __future__ import annotations

from typing import Protocol

from pydantic import JsonValue

from openclaw_moneybot.shared.types import RecordType
from openclaw_moneybot.skills.opportunity_scout.models import ScoutSourceDocument
from openclaw_moneybot.skills.receipt_and_evidence_archiver import (
    EvidenceArchiveRequest,
    ReceiptAndEvidenceArchiver,
)


class OpportunitySourceAdapter(Protocol):
    """Adapter interface for fetching candidate source documents."""

    def fetch_candidates(self) -> list[ScoutSourceDocument]: ...

    def normalize_candidate(self, candidate: ScoutSourceDocument) -> ScoutSourceDocument: ...

    def attach_source_evidence(
        self,
        candidate: ScoutSourceDocument,
        *,
        related_type: RecordType,
        related_id: str,
        archiver: ReceiptAndEvidenceArchiver,
    ) -> list[str]: ...


class LocalFixtureDocumentAdapter:
    """Adapter for pre-supplied local fixture documents."""

    def __init__(self, documents: list[ScoutSourceDocument]) -> None:
        self.documents = documents

    def fetch_candidates(self) -> list[ScoutSourceDocument]:
        return [self.normalize_candidate(document) for document in self.documents]

    def normalize_candidate(self, candidate: ScoutSourceDocument) -> ScoutSourceDocument:
        return candidate.model_copy(
            update={
                "source_type": candidate.source_type or "fixture",
                "category_hint": candidate.category_hint.strip().lower(),
            }
        )

    def attach_source_evidence(
        self,
        candidate: ScoutSourceDocument,
        *,
        related_type: RecordType,
        related_id: str,
        archiver: ReceiptAndEvidenceArchiver,
    ) -> list[str]:
        archived = archiver.archive(
            EvidenceArchiveRequest(
                related_type=related_type,
                related_id=related_id,
                evidence_type="source_document",
                content_text=candidate.content_text,
                source_url=candidate.source_url,
                notes=f"Archived source from {candidate.source_type}",
            )
        )
        return [archived.evidence_id]


class ManualUrlIngestionAdapter(LocalFixtureDocumentAdapter):
    """Adapter for a manually supplied URL plus already-fetched content."""

    def __init__(
        self,
        *,
        source_name: str,
        category_hint: str,
        source_url: str,
        payment_method: str,
        content_text: str,
        rules_url: str | None = None,
    ) -> None:
        super().__init__(
            [
                ScoutSourceDocument(
                    source_name=source_name,
                    source_type="manual_url",
                    category_hint=category_hint,
                    source_url=source_url,
                    rules_url=rules_url,
                    payment_method=payment_method,
                    content_text=content_text,
                )
            ]
        )


class GitHubIssueFixtureAdapter(LocalFixtureDocumentAdapter):
    """Adapter for fixture-backed GitHub issue/search results."""

    def __init__(self, issues_payload: list[dict[str, JsonValue]]) -> None:
        documents = []
        for issue in issues_payload:
            title = str(issue.get("title", "GitHub issue opportunity"))
            body = str(issue.get("body", ""))
            source_url = str(issue.get("html_url", "https://github.com/example/example/issues/1"))
            labels_value = issue.get("labels", [])
            labels = labels_value if isinstance(labels_value, list) else []
            documents.append(
                ScoutSourceDocument(
                    source_name=title,
                    source_type="github_issue_fixture",
                    category_hint=str(issue.get("category_hint", "bounty")),
                    source_url=source_url,
                    payment_method=str(issue.get("payment_method", "issue bounty")),
                    content_text=body,
                    known_risk_notes=[str(label) for label in labels if isinstance(label, str)],
                )
            )
        super().__init__(documents)


class PublicBountyPageAdapter(ManualUrlIngestionAdapter):
    """Adapter for a supplied public bounty page snapshot."""

    def __init__(self, *, source_name: str, source_url: str, content_text: str) -> None:
        super().__init__(
            source_name=source_name,
            category_hint="bounty",
            source_url=source_url,
            payment_method="bounty payout",
            content_text=content_text,
        )


class HackathonListingAdapter(ManualUrlIngestionAdapter):
    """Adapter for a supplied hackathon or contest listing snapshot."""

    def __init__(self, *, source_name: str, source_url: str, content_text: str) -> None:
        super().__init__(
            source_name=source_name,
            category_hint="contest",
            source_url=source_url,
            payment_method="contest payout",
            content_text=content_text,
        )
