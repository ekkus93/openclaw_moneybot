# Safety invariants

- Real wallet spending is disabled by default and must stay gated behind `wallet_governor_service`.
- Autonomous spend requires all of: policy `allow`, TOS/legal `proceed`, executable budget approval, a prewritten ledger spend request, and evidence references.
- The wallet governor service re-validates spend authorization server-side and never trusts the client alone.
- `human_review` is blocking for autonomous execution.
- Evidence archival must stay inside configured workspace allowlists and must not read sensitive local files.
- Email remains draft-only.
- Unknown or malformed structured data fails closed.
- Ledger writes and audit events are durable prerequisites for execution, not optional logging.
