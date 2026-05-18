from __future__ import annotations

from skills.email_drafter.models import (
    EmailDraftRequest,
    EmailDraftResult,
)


def run_email_draft(request: EmailDraftRequest) -> EmailDraftResult:
    if request.is_draft_only:
        return EmailDraftResult(
            draft_id=f"{request.opportunity_id}-draft",
            subject=request.subject,
            body=request.body,
            is_sent=False,
            draft_status="draft",
        )
    else:
        return EmailDraftResult(
            draft_id=f"{request.opportunity_id}-draft",
            subject=request.subject,
            body=request.body,
            is_sent=False,
            draft_status="draft",
        )
