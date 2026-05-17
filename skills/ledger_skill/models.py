from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class OpportunityStatus(StrEnum):
    new = "new"
    under_review = "under_review"
    approved = "approved"
    rejected = "rejected"
    completed = "completed"


class SpendStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    sent = "sent"
    rejected = "rejected"
    error = "error"


class EmailMode(StrEnum):
    draft = "draft"
    sent = "sent"
    received = "received"


class OpportunityRecord(BaseModel):
    id: str
    name: str
    category: str
    source_url: str | None = None
    status: OpportunityStatus
    created_at: str
    updated_at: str | None = None


class PolicyDecisionRecord(BaseModel):
    id: str
    opportunity_id: str
    decision: str
    risk_level: str
    matched_rules_json: str
    request_hash: str
    policy_version: str
    created_at: str


class TosLegalCheckRecord(BaseModel):
    id: str
    opportunity_id: str
    decision: str
    confidence: str
    red_flags_json: str
    evidence_ids_json: str
    created_at: str


class BudgetPlanRecord(BaseModel):
    id: str
    opportunity_id: str
    policy_decision_id: str
    tos_legal_check_id: str
    decision: str
    recommended_budget_usd: float
    max_loss_usd: float
    expected_net_revenue_usd: float
    success_metric: str
    stop_condition: str
    created_at: str


class SpendRequestRecord(BaseModel):
    id: str
    budget_plan_id: str
    policy_decision_id: str
    amount_usd: float
    asset: str
    recipient: str
    purpose: str
    status: SpendStatus
    created_at: str


class BtcTransactionRecord(BaseModel):
    id: str
    spend_request_id: str
    txid: str
    amount_btc: float
    fee_btc: float
    usd_value_at_send: float
    destination_address_hash_or_label: str
    created_at: str


class EvidenceRecord(BaseModel):
    id: str
    related_type: str
    related_id: str
    source_url: str | None = None
    archive_path: str | None = None
    content_sha256: str
    created_at: str


class EmailRecord(BaseModel):
    id: str
    opportunity_id: str
    mode: EmailMode
    recipient: str
    subject: str
    body_sha256: str
    archive_path: str | None = None
    created_at: str


class ExperimentReviewRecord(BaseModel):
    id: str
    opportunity_id: str
    spent_usd: float
    revenue_usd: float
    net_usd: float
    decision: str
    lessons_json: str
    created_at: str


class LedgerEvent(BaseModel):
    id: int
    event_type: str
    related_type: str
    related_id: str
    payload_json: str
    previous_event_hash: str | None
    event_hash: str
    created_at: str
    idempotency_key: str | None = None
