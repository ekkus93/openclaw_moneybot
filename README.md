# OpenClaw MoneyBot

OpenClaw MoneyBot is a bounded, auditable local experiment runner for small money-making workflows. It is intentionally **not** a general autonomous finance agent: policy, ledger, evidence, and wallet boundaries are all explicit and testable.

The project assumes a **local LLM/orchestrator environment**. Model output is treated as untrusted input and is always expected to flow through deterministic policy, schema, ledger, evidence, and wallet controls.

## Requirements

- Python **3.11**
- [`uv`](https://docs.astral.sh/uv/) for environment and dependency management

## Setup

```bash
uv sync --python 3.11 --all-groups
```

## Quality gates

Run Ruff:

```bash
uv run --python 3.11 ruff check .
```

Run mypy:

```bash
uv run --python 3.11 mypy .
```

Run pytest:

```bash
uv run --python 3.11 pytest
```

## Safe defaults

- Wallet spending is **disabled by default**.
- Email stays in **`draft_only`** mode by default.
- The email governor only allows live send attempts in **`capped_send`** mode with bot-owned sender allowlists, rate limits, policy checks, and archived outbound records.
- The browser governor is **disabled by default** and only prepares/completes governed actions; it does not provide autonomous browser control.
- Unknown policy categories default to **`needs_review`**.
- Missing config fails closed with a structured error.
- The local wallet governor HTTP API is expected to stay on **localhost only**.
- The Bitcoin Core backend exists only as a disabled-by-default skeleton.

## Current limitations

- Real Bitcoin Core integration is present only as a guarded skeleton and remains disabled by default.
- Email delivery is still opt-in and transport-backed; the default mode remains draft-only.
- Browser automation is still intentionally out of scope; the browser governor is a policy/evidence boundary, not a browser driver.
- Real opportunity scouting is still adapter-driven and fixture-first, not broad autonomous browsing.

## Core safety docs

- `docs/SAFETY_INVARIANTS.md`
- `docs/WALLET_GOVERNOR_DESIGN.md`
- `docs/LEDGER_SCHEMA.md`
- `docs/EVIDENCE_ARCHIVE.md`
- `docs/LOCAL_DEPLOYMENT.md`
- `docs/TESTING.md`
- `docs/CODE_REVIEW1_FIXES.md`

## Review branch assumption

This fix pass assumes **Copilot's branch is the authoritative base**. Any comparison or follow-on work should start from the current Copilot branch head instead of reviving older alternate scaffolds.

## Running a dry-run mission

1. Create a config file:

```yaml
policy:
  policy_version: "v1"
  blocked_categories: ["gambling"]
  review_required_categories: ["affiliate_marketing"]
  max_single_spend_usd: 10
  max_daily_spend_usd: 20
  max_weekly_spend_usd: 40
ledger:
  database_path: "data/moneybot.sqlite3"
archive:
  base_directory: "archive"
wallet_governor:
  base_url: "http://127.0.0.1:8080"
  timeout_seconds: 5
  spend_enabled: false
  allowed_assets: ["BTC"]
email:
  mode: "draft_only"
  max_outbound_per_day: 0
browser_governor:
  enabled: false
  allowed_profile_ids: ["moneybot-default"]
  execution_enabled: false
  browser_engine: "firefox"
  allowed_hosts: ["example.com"]
  profile_root: "data/browser_profiles"
brave_search:
  enabled: false
  api_base_url: "https://api.search.brave.com/res/v1/web/search"
  api_key_env_var: "BRAVE_SEARCH_API_KEY"
  max_results: 10
  max_news_results: 10
  default_news_freshness: "pd"
wikipedia_research:
  enabled: false
  api_base_url: "https://en.wikipedia.org/w/api.php"
  summary_api_base_url: "https://en.wikipedia.org/api/rest_v1/page/summary"
  max_results: 10
  max_extract_chars: 2000
```

2. Build the orchestrator from config and run a mission:

```python
from datetime import UTC, datetime

from openclaw_moneybot.orchestration import DryRunMissionRequest, build_orchestrator
from openclaw_moneybot.shared import load_app_config
from openclaw_moneybot.skills.opportunity_scout import ScoutSourceDocument

config = load_app_config("moneybot.yaml")
orchestrator = build_orchestrator(config)

result = orchestrator.run_dry_run(
    DryRunMissionRequest(
        mission="Review one bounded bounty",
        current_date=datetime.now(tz=UTC),
        source_documents=[
            ScoutSourceDocument(
                source_name="Example bounty",
                category_hint="bounty",
                source_url="https://example.com/bounty",
                rules_url="https://example.com/bounty/rules",
                payment_method="BTC payout",
                content_text=(
                    "Eligibility: open to individual developers.\n"
                    "Payment: bounty paid after accepted submission.\n"
                    "Automation: no prohibition on automated research tools.\n"
                    "Requires $5 spend for a hosted preview environment.\n"
                    "Payout is up to $25."
                ),
            )
        ],
        draft_recipient_email="maintainer@example.com",
        draft_recipient_name="Maintainer",
        enable_wallet_payment=False,
    )
)

print(result.model_dump())
```

For live browser execution, install the Playwright Firefox runtime locally:

```bash
uv run playwright install firefox
```

For Brave Search, set the hosted API credential in your environment before enabling the plugin:

```bash
export BRAVE_SEARCH_API_KEY="your-token"
```

The same plugin can also be used for current-events/news lookups through a bounded
`search_news()` path, which stays on Brave web search but applies recency and optional
source-domain filters rather than introducing a separate news API boundary.

Wikipedia research is available through a separate read-only plugin that supports bounded
article search plus page-summary fetches from Wikipedia-only endpoints.

For an automated reference run, the integration coverage in `tests/integration/test_workflow.py` exercises:

- one full dry-run path
- one fail-closed wallet path
- one tiny capped payment path using the fake wallet backend

## Enabling or disabling wallet spending

Wallet spending is controlled only through config:

```yaml
wallet_governor:
  base_url: "http://127.0.0.1:8080"
  spend_enabled: false
```

Set `spend_enabled: true` only when the local wallet governor service is available and you explicitly want governed payment calls to be allowed.

Do **not** connect a real Bitcoin Core wallet until the full guarded path, evidence rules, and operator review process are in the state you want for your own environment.
