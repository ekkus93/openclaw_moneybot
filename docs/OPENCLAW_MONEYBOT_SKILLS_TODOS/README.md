# OPENCLAW_MONEYBOT_SKILLS_TODOS

This package contains comprehensive implementation TODO lists for the nine OpenClaw MoneyBot skills:

1. `moneybot_policy_guard`
2. `opportunity_scout`
3. `tos_legal_checker`
4. `budget_and_roi_planner`
5. `ledger_skill`
6. `wallet_governor_client`
7. `email_drafter`
8. `receipt_and_evidence_archiver`
9. `experiment_reviewer`

## Recommended build order

Build in this order:

1. `ledger_skill`
2. `moneybot_policy_guard`
3. `receipt_and_evidence_archiver`
4. `tos_legal_checker`
5. `budget_and_roi_planner`
6. `opportunity_scout`
7. `email_drafter`
8. `wallet_governor_client`
9. `experiment_reviewer`

Reasoning:

- The ledger and policy guard are cross-cutting controls.
- Evidence archival is needed before legal/TOS review becomes auditable.
- Budget planning should exist before wallet spending.
- Email and wallet skills should remain draft/proposal-only until the controls are proven.

## Files

```text
OPENCLAW_MONEYBOT_SKILLS_TODOS/
  README.md
  MASTER_IMPLEMENTATION_TODO.md
  skills/
    moneybot_policy_guard/TODO.md
    opportunity_scout/TODO.md
    tos_legal_checker/TODO.md
    budget_and_roi_planner/TODO.md
    ledger_skill/TODO.md
    wallet_governor_client/TODO.md
    email_drafter/TODO.md
    receipt_and_evidence_archiver/TODO.md
    experiment_reviewer/TODO.md
  plugins/
    wallet_governor_service_TODO.md
    ledger_api_TODO.md
```

The `skills/` TODO files describe the OpenClaw-facing skill behavior. The `plugins/` TODO files describe service-level implementation work that the skills depend on.
