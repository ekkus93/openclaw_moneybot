from __future__ import annotations

from pydantic import BaseModel


class EmailDraftRequest(BaseModel):
    opportunity_id: str
    opportunity_name: str
    recipient: str
    subject: str
    body: str
    is_draft_only: bool = True


class EmailDraftResult(BaseModel):
    draft_id: str
    subject: str
    body: str
    is_sent: bool
    draft_status: str
