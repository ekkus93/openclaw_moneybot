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

# TODO — `experiment_reviewer`

## Goal

Implement the skill that reviews completed or in-progress experiments, calculates results, identifies lessons, and decides whether to continue, stop, retry with changes, or escalate to human review.

## Implementation tasks

### 1. Skill scaffolding

- [ ] Create implementation module for `experiment_reviewer`.
  - [ ] `models.py` for Pydantic v2 contracts.
  - [ ] `metrics.py` for deterministic experiment metrics.
  - [ ] `decision.py` for continue/stop/retry logic.
  - [ ] `runner.py` for OpenClaw entrypoint.
- [ ] Add tests under `tests/skills/test_experiment_reviewer.py`.

### 2. Input contract

- [ ] Define `ExperimentReviewRequest`.
  - [ ] `opportunity_id`
  - [ ] `budget_plan_id`
  - [ ] `review_reason`
  - [ ] `ledger_snapshot`
  - [ ] `evidence_archive_ids`
  - [ ] `manual_notes`
  - [ ] `current_date`
- [ ] Support review triggers.
  - [ ] Timebox expired.
  - [ ] Spend limit reached.
  - [ ] Revenue received.
  - [ ] Rejection received.
  - [ ] TOS/legal red flag discovered.
  - [ ] Manual review requested.
- [ ] Require ledger data or ledger query access.

### 3. Output contract

- [ ] Define `ExperimentReviewResult`.
  - [ ] `experiment_review_id`
  - [ ] `opportunity_id`
  - [ ] `spent_usd`
  - [ ] `revenue_usd`
  - [ ] `net_usd`
  - [ ] `roi_percent`
  - [ ] `time_spent_hours`
  - [ ] `success_metric_status`
  - [ ] `stop_condition_status`
  - [ ] `lessons`
  - [ ] `decision`: `continue | stop | retry_with_changes | human_review`
  - [ ] `recommended_next_actions`
  - [ ] `new_blocklist_patterns`
  - [ ] `scoring_feedback`
  - [ ] `ledger_record`
- [ ] Include evidence references.
- [ ] Include reviewer version.

### 4. Metrics calculation

- [ ] Calculate total spend from ledger.
- [ ] Calculate total revenue from ledger.
- [ ] Calculate net profit/loss.
- [ ] Calculate ROI percent.
- [ ] Calculate days since experiment start.
- [ ] Calculate whether max spend was reached.
- [ ] Calculate whether success metric was met.
- [ ] Calculate whether stop condition was met.
- [ ] Mark missing/incomplete data explicitly.

### 5. Decision rules

- [ ] Return `stop` when prohibited or major legal/TOS red flag appears.
- [ ] Return `stop` when stop condition is met and success metric failed.
- [ ] Return `continue` when success metric is progressing and spend/time limits are not reached.
- [ ] Return `retry_with_changes` when outcome is inconclusive but low-risk.
- [ ] Return `human_review` when data is missing, legal/TOS status changed, or funds/revenue handling is unclear.
- [ ] Never recommend increasing budget if original policy/TOS checks are stale.

### 6. Feedback loop

- [ ] Generate feedback for `opportunity_scout` scoring.
  - [ ] Source quality.
  - [ ] Category performance.
  - [ ] Expected vs actual revenue accuracy.
  - [ ] Time estimate accuracy.
  - [ ] Red flag patterns.
- [ ] Generate feedback for `moneybot_policy_guard`.
  - [ ] New suspicious pattern discovered.
  - [ ] Category should become review-required.
- [ ] Generate feedback for `budget_and_roi_planner`.
  - [ ] Underestimated cost.
  - [ ] Missing fee type.
  - [ ] Unrealistic success metric.

### 7. Ledger/evidence integration

- [ ] Query ledger by opportunity ID.
- [ ] Retrieve linked policy/TOS/budget/spend/email/evidence records.
- [ ] Record review result in ledger.
- [ ] Archive review snapshot.
- [ ] Link result to follow-up actions.

### 8. Tests

- [ ] Test profitable experiment -> continue or completed success according to config.
- [ ] Test no revenue and stop condition met -> stop.
- [ ] Test missing data -> human_review.
- [ ] Test legal red flag -> stop.
- [ ] Test inconclusive low-risk result -> retry_with_changes.
- [ ] Test budget exceeded -> stop/human_review.
- [ ] Test feedback generation.
- [ ] Test ledger output.

### 9. Acceptance criteria

- [ ] The reviewer can summarize an experiment from ledger data.
- [ ] The reviewer makes deterministic decisions from configured rules.
- [ ] The reviewer writes lessons back into the system.
- [ ] The reviewer never recommends further spend without fresh policy/budget checks.
