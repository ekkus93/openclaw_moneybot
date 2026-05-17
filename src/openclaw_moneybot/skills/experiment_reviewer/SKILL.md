# Skill: experiment_reviewer

## Purpose

`experiment_reviewer` evaluates completed or stalled MoneyBot experiments. It determines whether an experiment made money, lost money, produced useful learning, violated constraints, or should be stopped, repeated, or scaled.

This skill closes the loop so the bot does not keep repeating bad ideas.

## When To Use

Call this skill:

- After an experiment reaches a stop condition.
- After any spend is completed and enough time has passed to observe outcome.
- After a bounty/application receives a response.
- After a product/listing gets traffic or sales data.
- After any policy/TOS issue, platform warning, refund, chargeback, rejection, or user complaint.
- On a daily or weekly review cycle.

## Inputs

```json
{
  "review_id": "string",
  "experiment_id": "string",
  "review_type": "completion | daily | weekly | incident | payout | no_response | manual",
  "ledger_summary": {
    "spent_usd": 0,
    "revenue_usd": 0,
    "wallet_transactions": [],
    "emails_sent": 0,
    "responses_received": 0,
    "receipts": [],
    "actions": []
  },
  "original_plan": {},
  "success_metrics": ["string"],
  "stop_conditions": ["string"],
  "evidence_ids": ["string"],
  "policy_events": [],
  "notes": "string"
}
```

## Output Schema

```json
{
  "review_id": "string",
  "experiment_id": "string",
  "status": "reviewed | insufficient_data | error",
  "decision": "continue | stop | retry_with_changes | scale_cautiously | human_review",
  "financial_result": {
    "spent_usd": 0,
    "revenue_usd": 0,
    "net_usd": 0,
    "unrealized_value_usd": 0,
    "fees_usd": 0
  },
  "metric_results": [
    {
      "metric": "string",
      "target": "string|null",
      "actual": "string|null",
      "met": false
    }
  ],
  "stop_conditions_triggered": ["string"],
  "policy_or_tos_issues": ["string"],
  "evidence_quality": "poor | acceptable | good",
  "lessons_learned": ["string"],
  "recommended_rule_updates": [
    {
      "rule_type": "block | cap | prefer | require_review",
      "description": "string",
      "reason": "string"
    }
  ],
  "next_actions": ["string"],
  "ledger_update_required": true,
  "notes": "string"
}
```

## Review Criteria

### Financial

- Total spend.
- Total revenue received.
- Net result.
- Fees.
- Refunds or chargebacks.
- Unrealized assets or pending payouts.
- BTC/stablecoin transaction values in USD if relevant.

### Operational

- Time spent.
- Number of actions needed.
- Complexity versus expected reward.
- Failure points.
- Whether the bot required too much manual supervision.

### Compliance / Safety

- Any terms-of-service warnings.
- Any email opt-outs or complaints.
- Any platform rate limits or blocks.
- Any unexpected identity/KYC/account requirements.
- Any privacy/user-data implications.
- Any policy guard near-misses.

### Evidence Quality

- Are receipts present?
- Are terms archived?
- Are email records stored?
- Are transaction IDs recorded?
- Is outcome evidence verifiable?

## Decision Rules

### `continue`

Use when:

- Experiment is still within budget and stop conditions are not triggered.
- Early signal is positive or enough data has not yet arrived.
- No policy/TOS issues occurred.

### `stop`

Use when:

- Stop condition was triggered.
- Experiment lost money with no useful signal.
- Policy/TOS issue occurred.
- Revenue mechanism failed.
- Required future actions would violate constraints.
- Evidence is insufficient to justify continuation.

### `retry_with_changes`

Use when:

- The idea is valid but execution had fixable problems.
- Spend was low and lessons are concrete.
- Revised plan can reduce risk or cost.

### `scale_cautiously`

Use sparingly when:

- Experiment generated net positive revenue or strong qualified leads.
- Evidence is good.
- No policy/TOS issues occurred.
- Scaling does not require spam, deception, larger financial risk, or regulated activity.

Scaling must still respect spend caps unless human-reviewed.

### `human_review`

Use when:

- There is a legal/TOS/privacy uncertainty.
- There is a complaint, platform warning, or payment dispute.
- Scaling would require larger spend or new accounts.
- Tax/accounting facts are ambiguous.

## Required Calculations

```text
net_usd = revenue_usd + unrealized_value_usd - spent_usd - fees_usd
```

If exact values are unknown, use ranges and mark `insufficient_data` or lower confidence.

## Rule Update Examples

```json
{
  "rule_type": "block",
  "description": "Block affiliate programs that require cold email outreach.",
  "reason": "High compliance burden and poor response quality."
}
```

```json
{
  "rule_type": "prefer",
  "description": "Prefer documentation bounties with explicit payment terms under 4 hours estimated work.",
  "reason": "Best risk-adjusted result so far."
}
```

## Integration

Reads from:

- `ledger_skill`
- `receipt_and_evidence_archiver`
- `wallet_governor_client`
- `email_drafter`
- `budget_and_roi_planner`

Writes to:

- `ledger_skill` experiment status update.
- Optional policy suggestions to `moneybot_policy_guard` config.
- New opportunity preferences for `opportunity_scout`.

## Failure Behavior

If ledger data is incomplete:

```json
{
  "status": "insufficient_data",
  "decision": "human_review",
  "evidence_quality": "poor",
  "next_actions": ["Collect missing receipts and transaction records before continuing"]
}
```

Do not recommend scaling if evidence is incomplete.

## Test Cases

### Test 1: Net Positive Bounty

Input: $0 spend, $50 payout received, evidence archived.

Expected: `scale_cautiously` or `continue`, prefer similar bounties.

### Test 2: Failed Domain Purchase

Input: $8 domain bought, no traffic, no product published, stop condition reached.

Expected: `stop` or `retry_with_changes` depending on cause.

### Test 3: Email Complaint

Input: one recipient complained or opted out.

Expected: `stop` or `human_review`, recommend stricter outreach rules.

### Test 4: Missing Receipts

Input: spend exists but no receipt/evidence.

Expected: `insufficient_data`, require evidence before continuing.

### Test 5: Good Signal But Needs More Spend

Input: positive lead but next step requires $30 spend.

Expected: `human_review`, because spend exceeds default single cap.
