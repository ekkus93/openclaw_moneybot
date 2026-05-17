# OpenClaw MoneyBot Skill Implementation TODOs

These TODO files are implementation handoff documents for building the OpenClaw MoneyBot skills from the existing `SKILL.md` specifications.

Assumptions:

- Python implementation is acceptable unless the repo dictates another language.
- Use Pydantic v2 for typed contracts and validation.
- Use SQLite for durable local state and tests.
- Prefer deterministic rule engines over LLM-only judgment for safety-critical decisions.
- Do not use external commercial LLM APIs. The bot will use the user's local LLM.
- Do not give OpenClaw direct access to private keys, wallet passphrases, raw Bitcoin RPC credentials, personal accounts, or unrestricted shell access.
- Every externally meaningful action must be written to the ledger before execution.

# TODO — `budget_and_roi_planner`

## Goal

Implement the skill that converts a vetted opportunity into a bounded experiment plan with explicit spend, max loss, expected return, success metric, and stop condition.

## Implementation tasks

### 1. Skill scaffolding

- [ ] Create implementation module for `budget_and_roi_planner`.
  - [ ] `models.py` for Pydantic v2 contracts.
  - [ ] `calculator.py` for deterministic budget/ROI calculations.
  - [ ] `risk.py` for budget risk classification.
  - [ ] `runner.py` for OpenClaw entrypoint.
- [ ] Add tests under `tests/skills/test_budget_and_roi_planner.py`.

### 2. Input contract

- [ ] Define `BudgetPlanRequest`.
  - [ ] `opportunity_id`
  - [ ] `opportunity_name`
  - [ ] `tos_legal_check_id`
  - [ ] `policy_decision_id`
  - [ ] `proposed_action`
  - [ ] `required_spend_usd`
  - [ ] `estimated_revenue_usd`
  - [ ] `estimated_time_hours`
  - [ ] `fees_usd`
  - [ ] `recurring_costs_usd`
  - [ ] `asset`
  - [ ] `wallet_balance_usd`
  - [ ] `daily_spend_remaining_usd`
  - [ ] `evidence_archive_ids`
- [ ] Require a non-rejected TOS/legal check.
- [ ] Require a non-blocked policy decision.
- [ ] Reject missing spend, revenue, or max-loss data.

### 3. Output contract

- [ ] Define `BudgetPlanResult`.
  - [ ] `budget_plan_id`
  - [ ] `decision`: `reject | simulate | execute_request | human_review`
  - [ ] `recommended_budget_usd`
  - [ ] `max_loss_usd`
  - [ ] `expected_gross_revenue_usd`
  - [ ] `expected_net_revenue_usd`
  - [ ] `break_even_condition`
  - [ ] `success_metric`
  - [ ] `stop_condition`
  - [ ] `required_records`
  - [ ] `risk_level`
  - [ ] `wallet_spend_request_allowed`
  - [ ] `reasons`
- [ ] Include deterministic calculation fields.
- [ ] Include config version.

### 4. Budget math

- [ ] Calculate gross expected revenue.
- [ ] Calculate known fees.
  - [ ] Platform fees.
  - [ ] Payment fees.
  - [ ] Domain/hosting/listing fees.
  - [ ] Blockchain network fees estimate if supplied.
- [ ] Calculate expected net revenue.
- [ ] Calculate break-even units/actions.
- [ ] Calculate worst-case loss.
- [ ] Calculate wallet balance impact.
- [ ] Calculate daily and weekly spend budget impact.
- [ ] Treat unknown fees as risk-increasing and require review.

### 5. Experiment design

- [ ] Require a concrete success metric.
  - [ ] Revenue received.
  - [ ] Valid lead generated.
  - [ ] Bounty submission accepted.
  - [ ] Landing page conversion.
  - [ ] Other measurable result.
- [ ] Require a concrete stop condition.
  - [ ] Max spend reached.
  - [ ] Time budget reached.
  - [ ] No leads after threshold.
  - [ ] Rejection received.
  - [ ] TOS/legal red flag discovered.
- [ ] Require a timebox.
- [ ] Require expected next review date.

### 6. Decision rules

- [ ] Return `reject` when max loss exceeds configured limits.
- [ ] Return `reject` when policy or TOS status is blocked/rejected.
- [ ] Return `simulate` when confidence is low but risk is not prohibited.
- [ ] Return `human_review` for recurring billing or unclear costs.
- [ ] Return `execute_request` only when:
  - [ ] TOS/legal is proceed.
  - [ ] Policy guard is allow.
  - [ ] Spend fits all limits.
  - [ ] Success/stop metrics are explicit.
  - [ ] Evidence and ledger IDs are present.

### 7. Ledger and wallet handoff

- [ ] Produce ledger-ready `experiment_plan` record.
- [ ] Produce wallet-governor spend request only if decision is `execute_request`.
- [ ] Include `budget_plan_id` in wallet request metadata.
- [ ] Include required receipt/evidence expectations.
- [ ] Include tax/recordkeeping note for digital asset spend.

### 8. Tests

- [ ] Test successful low-cost plan.
- [ ] Test missing policy decision -> reject.
- [ ] Test missing TOS check -> reject.
- [ ] Test spend over max single limit -> reject.
- [ ] Test recurring billing -> human_review.
- [ ] Test unknown fees -> human_review.
- [ ] Test negative expected net -> reject or simulate according to config.
- [ ] Test explicit stop condition required.
- [ ] Test wallet handoff object shape.

### 9. Acceptance criteria

- [ ] No plan can request wallet spending without policy and TOS references.
- [ ] Every plan has max loss, expected net, success metric, and stop condition.
- [ ] Every spend-cap violation fails closed.
- [ ] Output is ledger-ready and testable offline.
