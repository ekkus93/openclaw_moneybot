# Skill: budget_and_roi_planner

## Purpose

`budget_and_roi_planner` converts a vetted opportunity into a bounded, measurable experiment with explicit spend limits, expected outcomes, failure conditions, and stop rules.

This skill does not execute purchases or payments. It prepares a plan that must be recorded by `ledger_skill`, approved by `moneybot_policy_guard`, and executed through governed tools only.

## Core Principle

No money should be spent unless the bot can clearly state:

- What is being bought or committed.
- Why it is necessary.
- The maximum possible loss.
- The expected return or learning value.
- The success metric.
- The stop condition.
- The evidence required after execution.

## Inputs

```json
{
  "plan_id": "string",
  "opportunity_id": "string",
  "opportunity_summary": "string",
  "source_urls": ["string"],
  "tos_legal_result": {},
  "policy_guard_result": {},
  "available_budget_usd": 100,
  "max_single_spend_usd": 10,
  "max_daily_spend_usd": 20,
  "wallet_asset": "BTC | USDC_SOL | SOL | ETH | none",
  "required_spend_items": [
    {
      "item": "string",
      "vendor_or_counterparty": "string",
      "amount_usd": 0,
      "required": true,
      "recurring": false,
      "source_url": "string|null"
    }
  ],
  "estimated_revenue": {
    "low_usd": 0,
    "base_usd": 0,
    "high_usd": 0,
    "timeframe_days": 0
  },
  "estimated_time_hours": 0,
  "notes": "string"
}
```

## Output Schema

Return strict JSON:

```json
{
  "plan_id": "string",
  "opportunity_id": "string",
  "decision": "reject | simulate | execute_after_ledger | human_review",
  "confidence": "low | medium | high",
  "experiment_name": "string",
  "summary": "string",
  "budget": {
    "available_budget_usd": 100,
    "recommended_spend_usd": 0,
    "max_loss_usd": 0,
    "single_spend_limit_usd": 10,
    "daily_spend_limit_usd": 20,
    "recurring_spend_detected": false,
    "recurring_spend_details": []
  },
  "spend_items": [
    {
      "item": "string",
      "amount_usd": 0,
      "vendor_or_counterparty": "string",
      "required": true,
      "approved": false,
      "reason": "string",
      "receipt_required": true
    }
  ],
  "roi_estimate": {
    "revenue_low_usd": 0,
    "revenue_base_usd": 0,
    "revenue_high_usd": 0,
    "net_low_usd": 0,
    "net_base_usd": 0,
    "net_high_usd": 0,
    "break_even_condition": "string",
    "time_to_first_result_days": 0
  },
  "success_metrics": ["string"],
  "stop_conditions": ["string"],
  "required_next_skills": ["ledger_skill", "wallet_governor_client", "receipt_and_evidence_archiver"],
  "risk_notes": ["string"],
  "ledger_record_required_before_execution": true
}
```

## Decision Rules

### `reject`

Use when:

- Required spend exceeds limits.
- Maximum loss is unclear.
- Revenue mechanism is implausible or deceptive.
- TOS/legal/policy checks failed.
- Recurring charge risk cannot be controlled.
- The plan requires prohibited behavior.
- The plan cannot produce a measurable result.

### `simulate`

Use when:

- The opportunity is interesting but lacks enough information for spending.
- The plan can be tested without spending money.
- The expected return is uncertain and preliminary validation is needed.

### `execute_after_ledger`

Use only when:

- TOS/legal result is `proceed` or explicitly reviewed.
- Policy guard allows the action.
- Spend is within single and daily limits.
- Spend items are specific and bounded.
- A ledger record can be written before execution.
- Receipt/evidence capture is possible.

### `human_review`

Use when:

- Spend is near limits.
- The opportunity has contractual, tax, privacy, or public-claim complexity.
- The bot needs to create an account on a marketplace, financial, crypto, advertising, or affiliate platform.
- The plan involves cold outreach, public advertising, or recurring services.

## Required Calculations

At minimum:

```text
recommended_spend_usd = sum(approved spend items)
max_loss_usd = recommended_spend_usd + unavoidable fees + known cancellation/recurring risk
net_low_usd = revenue_low_usd - max_loss_usd
net_base_usd = revenue_base_usd - max_loss_usd
net_high_usd = revenue_high_usd - max_loss_usd
```

Do not hide platform fees, gas fees, transaction fees, hosting fees, listing fees, or recurring billing.

If the bot cannot estimate a fee, include it in `risk_notes` and lower confidence.

## Spend Rules

Default limits:

- Maximum single spend: $10.
- Maximum daily spend: $20.
- Maximum weekly spend: $40.
- Maximum wallet budget: $100.

No plan may approve:

- `send all` or balance-draining transfers.
- Recurring subscriptions without human review.
- Purchases requiring personal identity or personal accounts.
- Purchases where refund/cancellation terms are unavailable.
- Crypto swaps, token purchases, DeFi, NFTs, or trading.

## Stop Conditions

Every executable plan must include stop conditions. Examples:

- Stop after spending planned budget.
- Stop if no reply after one allowed follow-up.
- Stop if platform flags or restricts the account.
- Stop if a page/offer requires additional unplanned spend.
- Stop if legal/TOS uncertainty appears.
- Stop if estimated total cost exceeds approved budget by any amount.

## Success Metrics

Use measurable metrics:

- Received payout.
- Received qualified reply.
- Accepted bounty submission.
- Product page published.
- First sale completed.
- Lead submitted.
- Revenue greater than spend.
- Learning objective completed without violations.

Avoid vague metrics like “got exposure” or “seems promising.”

## Integration

Before this skill:

- `opportunity_scout`
- `tos_legal_checker`
- `moneybot_policy_guard`

After this skill:

- `ledger_skill` creates plan and spend records.
- `wallet_governor_client` handles allowed payment.
- `receipt_and_evidence_archiver` stores receipts/evidence.
- `experiment_reviewer` evaluates outcome.

## Failure Behavior

If budget or revenue numbers are unknown:

- Do not invent precision.
- Use ranges.
- Set confidence low.
- Recommend `simulate` or `human_review`, not execution.

## Test Cases

### Execute: $8 Domain Purchase

Input: Approved micro-product needs one domain for $8/year, no recurring auto-renew unless disabled, clear cancellation, domain needed for landing page.

Expected: `execute_after_ledger` with max loss $8 plus any fee; require receipt and ledger.

### Reject: $50 Ad Spend

Input: Bot wants $50 ad campaign with no tested landing page and unclear claims.

Expected: `reject` or `human_review`, spend exceeds default limits and claims/ad review needed.

### Simulate: Product Idea

Input: Bot proposes a $5 checklist product but has not validated demand.

Expected: `simulate`, create landing page or draft before spend.

### Human Review: Affiliate Program

Input: Affiliate program could pay but requires public disclosure and email marketing.

Expected: `human_review`, require terms, email policy, and claim review.
