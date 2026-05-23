# UNIT_TEST3_TODO.md

# OpenClaw MoneyBot - Unit Test Coverage Follow-up TODO 3

This TODO tracks the next focused unit-test pass after the latest full coverage review.

The goal is **not** to optimize for raw percentage alone. The goal is to add tests around:

- safety-critical backend boundaries
- fail-closed provider and parser behavior
- deterministic orchestration and debate branching
- bounded research/discovery normalization logic
- helper/model/config branches that could silently drift

Current reference point from the latest coverage run:

```text
TOTAL: 90%
```

Highest-value current hotspots:

- `plugins/browser_governor/backend.py` - 34%
- `plugins/inner_voice_plugin/providers.py` - 74%
- `plugins/wikipedia_research_plugin/service.py` - 75%
- `plugins/bluesky_discovery_plugin/service.py` - 76%
- `plugins/stock_market_data_plugin/service.py` - 77%
- `plugins/biomedical_research_plugin/service.py` - 78%
- `plugins/arxiv_research_plugin/service.py` - 79%
- `plugins/openalex_research_plugin/service.py` - 79%
- `plugins/inner_voice_plugin/debate.py` - 81%
- `orchestration/workflow.py` - 86%

Secondary validator/model/config gaps worth sweeping during the same pass:

- `plugins/browser_governor/models.py`
- `plugins/arxiv_research_plugin/models.py`
- `plugins/wikipedia_research_plugin/models.py`
- `plugins/brave_search_plugin/models.py`
- `shared/config.py`
- `shared/base.py`

---

# Priority legend

```text
P0 = safety-critical backend or provider boundary with fail-closed behavior
P1 = important service/parser/normalization branches and deterministic outcomes
P2 = secondary helper, validator, model, and config coverage improvements
```

---

# 1. P0 - Expand Browser Governor Backend Safety Coverage

## 1.1 Goal

Add direct unit coverage for the bounded Playwright backend and helper functions in:

```text
src/openclaw_moneybot/plugins/browser_governor/backend.py
```

The focus is path safety, host allowlisting, bounded step execution, and deterministic timeout/error behavior.

## 1.2 Profile-path resolution and allowlist enforcement

- [x] Add test: `_resolve_profile_dir()` strips unsafe characters while preserving safe `-` and `_`.
- [x] Add test: `_resolve_profile_dir()` raises when `profile_id` contains no safe characters after sanitization.
- [x] Add test: `_resolve_profile_dir()` always resolves under the configured profile root.
- [x] Add test: `_assert_allowed_host()` accepts an allowlisted host.
- [x] Add test: `_assert_allowed_host()` rejects a non-allowlisted host with the expected error.
- [x] Add test: `_assert_allowed_host()` rejects URLs with no hostname.
- [x] Add test: `_assert_allowed_host()` normalizes host case before allowlist comparison.

## 1.3 Page-capture and string-requirement helpers

- [x] Add test: `_read_page_text()` returns stripped body text.
- [x] Add test: `_read_page_text()` returns an empty string when body text is `None`.
- [x] Add test: `_capture_page()` preserves URL, title, HTML, screenshot bytes, and stripped body text.
- [x] Add test: `_require_string()` returns the original string when present.
- [x] Add test: `_require_string()` raises `BrowserAutomationError` when the field is missing.

## 1.4 Step execution branches

- [x] Add test: `_apply_step()` for `fill` sends the required selector, text, and timeout to the locator.
- [x] Add test: `_apply_step()` for `click` sends the required selector and timeout to the locator.
- [x] Add test: `_apply_step()` for `wait_for_text` delegates to `_wait_for_text()`.
- [x] Add test: `_apply_step()` fails closed when a required selector is missing.
- [x] Add test: `_apply_step()` fails closed when required fill text is missing.
- [x] Add test: `_apply_step()` fails closed when required wait text is missing.

## 1.5 Wait-loop behavior

- [x] Add test: `_wait_for_text()` succeeds when body text contains the expected text.
- [x] Add test: `_wait_for_text()` succeeds when selector-scoped text contains the expected text.
- [x] Add test: `_wait_for_text()` ignores interim `None` text values and continues polling.
- [x] Add test: `_wait_for_text()` raises `BrowserAutomationError` on timeout.

## 1.6 Top-level `execute()` flow

- [x] Add test: `execute()` uses the first existing page when one is already present.
- [x] Add test: `execute()` falls back to `context.new_page()` when no page exists yet.
- [x] Add test: `execute()` creates the profile directory before launching the browser context.
- [x] Add test: `execute()` truncates execution to `config.max_steps`.
- [x] Add test: `execute()` re-checks the host allowlist after initial navigation and after each step.
- [x] Add test: `execute()` closes the browser context on success.
- [x] Add test: `execute()` closes the browser context when a step raises.
- [x] Add test: `execute()` wraps `PlaywrightError` as `BrowserAutomationError`.

---

# 2. P0 - Expand Inner Voice Provider Adapter Failure Coverage

## 2.1 Goal

Add deeper unit coverage for direct provider adapter behavior in:

```text
src/openclaw_moneybot/plugins/inner_voice_plugin/providers.py
```

The focus is health reporting, strict JSON enforcement, provider-specific malformed-response paths, and fail-closed adapter selection.

## 2.2 Base adapter health states

- [x] Add test: `health(enabled=False)` returns `disabled`.
- [x] Add test: `health(enabled=True)` returns `misconfigured` when `model_name` is blank.
- [x] Add test: OpenAI `health()` returns `missing_api_key` when the configured env var is unset.
- [x] Add test: `health()` returns `provider_unreachable` when the configured healthcheck endpoint fails.
- [x] Add test: `health()` returns `ok` when the healthcheck succeeds.
- [x] Add test: `health()` returns `ok` for adapters without a healthcheck path when config is otherwise valid.

## 2.3 Strict content and JSON parsing helpers

- [x] Add test: `_parse_strict_json_object()` rejects malformed JSON with `malformed_output`.
- [x] Add test: `_parse_strict_json_object()` rejects non-object JSON payloads.
- [x] Add test: `_string_content()` returns plain string content unchanged.
- [x] Add test: `_string_content()` joins text fragments from list-style OpenAI-compatible content parts.
- [x] Add test: `_string_content()` ignores non-mapping and non-text list items when text fragments are still present.
- [x] Add test: `_string_content()` raises when no usable text content exists.

## 2.4 OpenAI adapter request/response branches

- [x] Add test: `_ensure_json_compatible_configuration()` rejects non-`/v1` base URLs.
- [x] Add test: `_ensure_json_compatible_configuration()` rejects unsupported model families.
- [x] Add test: `generate()` fails closed when the OpenAI API key is missing.
- [x] Add test: `generate()` maps 401 and 403 responses to `invalid_auth`.
- [x] Add test: `generate()` maps other HTTP failures to `provider_error`.
- [x] Add test: `generate()` maps transport and timeout failures to `provider_unavailable`.
- [x] Add test: `generate()` rejects non-dict raw payloads.
- [x] Add test: `generate()` rejects missing or empty `choices`.
- [x] Add test: `generate()` rejects non-mapping choice payloads.
- [x] Add test: `generate()` rejects a choice with no mapping `message`.
- [x] Add test: `generate()` sets `finish_reason=None` when the provider returns a non-string value.
- [x] Add test: `generate()` ignores non-integer usage counters instead of crashing.
- [x] Add test: `generate()` includes `top_p` only when requested.

## 2.5 Ollama and llama-server branches

- [x] Add test: Ollama `generate()` rejects non-dict payloads.
- [x] Add test: Ollama `generate()` rejects missing message payloads.
- [x] Add test: Ollama `generate()` sets `finish_reason=None` when `done_reason` is non-string.
- [x] Add test: Ollama `generate()` ignores non-integer token counters safely.
- [x] Add test: llama-server `generate()` maps transport failures to `provider_unavailable`.
- [x] Add test: llama-server `generate()` maps HTTP failures to `provider_error`.
- [x] Add test: llama-server `generate()` rejects non-dict payloads.
- [x] Add test: llama-server `generate()` rejects missing or empty `choices`.
- [x] Add test: llama-server `generate()` rejects malformed choice and message payloads.
- [x] Add test: llama-server `generate()` ignores non-integer usage counters safely.

## 2.6 Adapter factory coverage

- [x] Add test: `build_provider_adapter()` returns `OpenAiProviderAdapter` for `ProviderName.OPENAI`.
- [x] Add test: `build_provider_adapter()` returns `OllamaProviderAdapter` for `ProviderName.OLLAMA`.
- [x] Add test: `build_provider_adapter()` returns `LlamaServerProviderAdapter` for `ProviderName.LLAMA_SERVER`.
- [x] Add test: `build_provider_adapter()` rejects unsupported providers fail-closed.

---

# 3. P1 - Expand Bluesky Discovery Normalization Coverage

## 3.1 Goal

Add branch-heavy parser coverage for:

```text
src/openclaw_moneybot/plugins/bluesky_discovery_plugin/service.py
```

The focus is default-feed behavior, malformed response handling, and normalization of post metadata into stable bounded results.

## 3.2 Feed request and failure branches

- [x] Add test: `health()` reports `missing_default_feed_uri` when the configured default URI is blank.
- [x] Add test: `sample_feed()` rejects requests when the plugin is disabled.
- [x] Add test: `sample_feed()` rejects limits above `max_results`.
- [x] Add test: `sample_feed()` raises when neither request nor config provides a feed URI.
- [x] Add test: `sample_feed()` records the expected audit event on transport failure.
- [x] Add test: `sample_feed()` records the expected audit event on invalid HTTP/JSON responses.
- [x] Add test: `sample_feed()` rejects non-object top-level payloads.

## 3.3 Feed-list normalization

- [x] Add test: `_normalize_feed()` rejects responses without a list-valued `feed`.
- [x] Add test: `_normalize_feed()` stops at the requested limit even if more feed items are present.
- [x] Add test: `_normalize_feed()` skips non-dict feed items instead of crashing.
- [x] Add test: `_normalize_feed()` sets `cursor=None` for non-string cursors.

## 3.4 Per-post required-field validation

- [x] Add test: `_normalize_feed_item()` rejects missing `post` payloads.
- [x] Add test: `_normalize_feed_item()` rejects missing `uri`, `cid`, and `indexedAt`.
- [x] Add test: `_normalize_feed_item()` rejects missing `author` or `record` payloads.
- [x] Add test: `_normalize_feed_item()` rejects missing author `did` and `handle`.
- [x] Add test: `_normalize_feed_item()` rejects missing post text.

## 3.5 Helper normalization branches

- [x] Add test: `_post_url()` returns `None` for non-AT-URI post identifiers.
- [x] Add test: `_optional_string()` trims whitespace and converts blank strings to `None`.
- [x] Add test: link, label, count, and embed helpers tolerate malformed payload fragments without crashing.
- [x] Add test: feed-reason normalization returns a stable bounded value for missing and malformed reason payloads.

---

# 4. P1 - Expand Wikipedia Research Parser Coverage

## 4.1 Goal

Add coverage for search/page-summary normalization and failure branches in:

```text
src/openclaw_moneybot/plugins/wikipedia_research_plugin/service.py
```

## 4.2 Search request and failure branches

- [x] Add test: `search()` rejects requests when disabled.
- [x] Add test: `search()` rejects counts above `max_results`.
- [x] Add test: `search()` records the expected failure event on transport errors.
- [x] Add test: `search()` records the expected failure event on invalid HTTP/JSON responses.
- [x] Add test: `search()` rejects non-object top-level payloads.

## 4.3 Search result normalization

- [x] Add test: `_normalize_search_results()` rejects missing `query` payloads.
- [x] Add test: `_normalize_search_results()` rejects non-list `search` payloads.
- [x] Add test: `_normalize_search_results()` skips malformed search items instead of crashing.
- [x] Add test: `_normalize_search_results()` stops at the requested limit.
- [x] Add test: snippet normalization keeps valid snippets and tolerates missing snippet fields.

## 4.4 Page summary normalization

- [x] Add test: `get_page_summary()` rejects requests when disabled.
- [x] Add test: `get_page_summary()` clamps `request.max_extract_chars` to the configured maximum.
- [x] Add test: `get_page_summary()` records the expected failure event on transport errors.
- [x] Add test: `get_page_summary()` rejects non-object top-level payloads.
- [x] Add test: `_normalize_page_summary()` rejects missing required title/page/URL/extract fields.
- [x] Add test: `_normalize_page_summary()` trims or clips extracts deterministically to the configured limit.
- [x] Add test: `_summary_url()` percent-encodes titles safely.

---

# 5. P1 - Expand arXiv Research XML and Lookup Coverage

## 5.1 Goal

Add unit tests for Atom-feed parsing and lookup failures in:

```text
src/openclaw_moneybot/plugins/arxiv_research_plugin/service.py
```

## 5.2 Search and lookup failure paths

- [x] Add test: `search()` rejects requests when disabled.
- [x] Add test: `search()` rejects counts above `max_results`.
- [x] Add test: `search()` records the expected failure event on transport errors.
- [x] Add test: `search()` records the expected failure event on HTTP failures.
- [x] Add test: `get_paper()` records the expected failure event on transport errors.
- [x] Add test: `get_paper()` raises `paper not found` when the feed contains no entries.

## 5.3 Atom feed parsing

- [x] Add test: `_parse_feed()` rejects malformed XML.
- [x] Add test: `_parse_feed()` rejects a non-Atom root element.
- [x] Add test: `_parse_feed()` returns `total_results=None` when `totalResults` is missing or non-numeric.
- [x] Add test: `_parse_feed()` parses valid `totalResults` when present.

## 5.4 Entry normalization helpers

- [x] Add test: `_parse_entry()` rejects missing required title/summary/published/updated/id fields.
- [x] Add test: `_parse_entry()` preserves multiple authors deterministically.
- [x] Add test: `_parse_entry()` picks the PDF link only from the expected relation/type.
- [x] Add test: required-text helper raises with stable error text for missing elements.
- [x] Add test: optional-text helper trims whitespace and converts blanks to `None`.
- [x] Add test: search-query and sort helper methods map values to the expected API parameters.

---

# 6. P1 - Expand OpenAlex Search and Work Normalization Coverage

## 6.1 Goal

Add branch coverage for:

```text
src/openclaw_moneybot/plugins/openalex_research_plugin/service.py
```

## 6.2 API-key and request gating

- [x] Add test: `health()` reports `missing_api_key` when the configured env var is unset or blank.
- [x] Add test: `search()` rejects requests when disabled.
- [x] Add test: `search()` rejects counts above `max_results`.
- [x] Add test: `search()` fails closed when the API key is missing.
- [x] Add test: `get_work()` fails closed when the API key is missing.

## 6.3 Search and work failure branches

- [x] Add test: `search()` records the expected failure event on transport errors.
- [x] Add test: `search()` records the expected failure event on invalid HTTP/JSON responses.
- [x] Add test: `search()` rejects non-object top-level payloads.
- [x] Add test: `get_work()` records the expected failure event on transport errors.
- [x] Add test: `get_work()` rejects non-object work payloads.

## 6.4 Search-result and work normalization

- [x] Add test: `_normalize_search_results()` rejects missing `meta`.
- [x] Add test: `_normalize_search_results()` tolerates non-integer `meta.count` by returning `None`.
- [x] Add test: `_normalize_search_results()` rejects non-list `results`.
- [x] Add test: `_normalize_search_results()` skips malformed list items instead of crashing.
- [x] Add test: `_normalize_work()` falls back from `display_name` to `title`.
- [x] Add test: `_normalize_work()` rejects works missing both `display_name` and `title`.
- [x] Add test: author, topic, abstract, and open-access helpers normalize malformed payload fragments safely.

## 6.5 Helper coverage

- [x] Add test: `_api_key()` trims whitespace and treats blank env-var values as missing.
- [x] Add test: `_search_filter_params()` returns an empty dict when no filters are requested.
- [x] Add test: `_search_filter_params()` combines publication-year and OA filters deterministically.
- [x] Add test: `_work_lookup_path()` strips the OpenAlex URL prefix and percent-encodes the remaining ID.

---

# 7. P1 - Expand Biomedical Research Provider-Split Coverage

## 7.1 Goal

Add targeted unit coverage for provider-specific branches in:

```text
src/openclaw_moneybot/plugins/biomedical_research_plugin/service.py
```

## 7.2 Shared request and failure handling

- [ ] Add test: `search()` rejects requests when disabled.
- [ ] Add test: `search()` rejects counts above `max_results`.
- [ ] Add test: `get_paper()` rejects requests when disabled.
- [ ] Add test: provider-specific search failures record the expected audit event names.
- [ ] Add test: provider-specific lookup failures record the expected audit event names.
- [ ] Add test: `_provider_label()` returns stable provider labels for PubMed and Europe PMC.

## 7.3 PubMed branches

- [ ] Add test: `_search_pubmed()` rejects non-object search payloads.
- [ ] Add test: `_search_pubmed()` rejects missing `esearchresult`.
- [ ] Add test: `_search_pubmed()` rejects non-list `idlist`.
- [ ] Add test: `_search_pubmed()` returns an empty result set without calling fetch when the search ID list is empty.
- [ ] Add test: `_get_pubmed_paper()` raises when the fetched XML contains no matching paper.
- [ ] Add test: PubMed term-building includes publication-year filtering when requested.

## 7.4 Europe PMC branches

- [ ] Add test: `_search_europe_pmc()` rejects non-object payloads.
- [ ] Add test: `_get_europe_pmc_paper()` rejects non-object payloads.
- [ ] Add test: `_get_europe_pmc_paper()` raises when no matching paper is returned.
- [ ] Add test: Europe PMC query-building includes publication-year filtering when requested.
- [ ] Add test: `_normalize_europe_pmc_results()` tolerates missing/non-integer hit counts.
- [ ] Add test: `_normalize_europe_pmc_results()` skips malformed result items instead of crashing.

## 7.5 Paper normalization helpers

- [ ] Add test: PubMed XML parsing rejects malformed XML.
- [ ] Add test: PubMed article parsing keeps multiple abstract sections in deterministic order.
- [ ] Add test: Europe PMC normalization trims blank optional strings to `None`.
- [ ] Add test: DOI/PMID/PMCID helper branches normalize missing identifiers safely.
- [ ] Add test: integer/date/string helper functions tolerate malformed provider values safely.

---

# 8. P1 - Expand Stock Market Data Provider and Parser Coverage

## 8.1 Goal

Add direct unit coverage for provider-error and normalization branches in:

```text
src/openclaw_moneybot/plugins/stock_market_data_plugin/service.py
```

## 8.2 Request gating and provider failures

- [ ] Add test: `health()` reports `missing_api_key` when the configured env var is unset or blank.
- [ ] Add test: `get_quote()` rejects requests when disabled.
- [ ] Add test: `get_daily_bars()` rejects requests when disabled.
- [ ] Add test: `get_daily_bars()` rejects counts above `max_daily_bars`.
- [ ] Add test: `_required_api_key()` fails closed when the API key is missing.
- [ ] Add test: `_query()` records `transport_error` on transport failures.
- [ ] Add test: `_query()` records `invalid_response` on invalid HTTP/JSON failures.
- [ ] Add test: `_query()` rejects non-object payloads.
- [ ] Add test: `_query()` maps provider `Error Message`, `Note`, and `Information` fields into fail-closed errors.

## 8.3 Quote normalization

- [ ] Add test: `get_quote()` rejects missing `Global Quote`.
- [ ] Add test: `_normalize_quote()` rejects missing required symbol and price fields.
- [ ] Add test: `_normalize_quote()` tolerates missing optional numeric fields by returning `None`.
- [ ] Add test: `_normalize_quote()` parses percentage strings into numeric percentage values.

## 8.4 Daily-bars normalization

- [ ] Add test: `_normalize_daily_bars()` rejects missing `Time Series (Daily)`.
- [ ] Add test: `_normalize_daily_bars()` uses provider symbol from metadata when it differs from the requested symbol.
- [ ] Add test: `_normalize_daily_bars()` leaves `last_refreshed=None` when metadata is missing or malformed.
- [ ] Add test: `_normalize_daily_bars()` skips malformed trading-day rows instead of crashing.
- [ ] Add test: `_normalize_daily_bars()` returns bars in deterministic trading-day order and truncates to `count`.

## 8.5 Scalar parsing helpers

- [ ] Add test: `_required_string()` trims whitespace and rejects blanks.
- [ ] Add test: `_required_float()` rejects malformed numeric values.
- [ ] Add test: `_optional_float()`, `_optional_int()`, and `_optional_string()` return `None` for blank or malformed values.
- [ ] Add test: `_optional_percentage()` strips `%` and returns `None` for malformed inputs.

---

# 9. P1 - Expand Inner Voice Debate and Metrics Coverage

## 9.1 Goal

Add more direct unit coverage for:

```text
src/openclaw_moneybot/plugins/inner_voice_plugin/debate.py
```

The focus is debate end-state branching, archive/audit payload stability, and metrics aggregation helpers.

## 9.2 Debate session branching

- [ ] Add test: `run_debate()` rejects stages not enabled in `run_after_stages`.
- [ ] Add test: `run_debate()` records `request_arbiter` when the inner voice requests escalation immediately.
- [ ] Add test: `run_debate()` records `request_arbiter` when OpenClaw requests escalation.
- [ ] Add test: `run_debate()` records `max_rounds_reached` when the debate ceiling is hit without convergence.
- [ ] Add test: `run_debate()` records `orchestrator_escalation` when the resolution guard returns a reason.
- [ ] Add test: `run_debate()` persists the escalation reason into the summary and ledger payload.
- [ ] Add test: `run_debate()` raises `InnerVoiceDebateError` with structured failure details on downstream failures.

## 9.3 Transcript and summary archival helpers

- [ ] Add test: transcript archival respects the placeholder/raw-text configuration branches.
- [ ] Add test: debate summary archival includes resolution notes only when present.
- [ ] Add test: debate summary archival includes `orchestrator_escalation_reason` only when present.
- [ ] Add test: turn-metadata export remains deterministic and stable for mixed turn types.

## 9.4 Metrics snapshot helpers

- [ ] Add test: `build_metrics_snapshot()` counts debate end reasons correctly across mixed sessions.
- [ ] Add test: `build_metrics_snapshot()` counts Arbiter resolutions and follow-up rates correctly.
- [ ] Add test: `build_metrics_snapshot()` tolerates malformed or partial provider-response summaries.
- [ ] Add test: `_summary_int_value()` returns `None` for missing, non-dict, and non-int summary values.

---

# 10. P2 - Expand Workflow Disagreement Helper Coverage

## 10.1 Goal

Add more unit-focused coverage for disagreement interpretation helpers in:

```text
src/openclaw_moneybot/orchestration/workflow.py
```

The focus is deterministic helper logic that should remain stable independent of end-to-end integration tests.

## 10.2 Debate helper decisions

- [ ] Add test: `resolve_model_disagreement()` rejects calls when the coordinator is not configured.
- [ ] Add test: `resolve_model_disagreement()` rejects irrelevant stage/subject pairs.
- [ ] Add test: `settle_model_disagreement()` re-raises debate failures for non-required paths.
- [ ] Add test: `settle_model_disagreement()` uses `error.failure.record_id` when present.
- [ ] Add test: `settle_model_disagreement()` falls back to `request.debate_id` or `"debate_unavailable"` when failure details are absent.

## 10.3 Interpretation and helper branches

- [ ] Add test: `interpret_model_disagreement()` raises when `final_resolution_source` is Arbiter-backed but no Arbiter result is present.
- [ ] Add test: `_debate_subject_is_relevant()` covers every configured stage/subject matrix branch.
- [ ] Add test: `_requires_fail_closed_debate_path()` is true only for required pre-execution spend/execution-step paths.
- [ ] Add test: `_debate_orchestrator_escalation_reason()` returns `None` for non-required paths and non-followup resolutions.
- [ ] Add test: `_resolved_disposition_from_outcome_parts()` covers debate-only, adopt-openclaw, adopt-inner-voice, proceed-with-followups, and needs-review branches.
- [ ] Add test: `_latest_disposition_from_turns()` returns the newest matching speaker disposition or `None`.

---

# 11. P2 - Sweep Remaining Model and Config Validator Gaps

## 11.1 Goal

Close secondary unit-test gaps in lower-coverage model/config files that are likely to drift if left uncovered.

Target files:

```text
src/openclaw_moneybot/plugins/browser_governor/models.py
src/openclaw_moneybot/plugins/arxiv_research_plugin/models.py
src/openclaw_moneybot/plugins/wikipedia_research_plugin/models.py
src/openclaw_moneybot/plugins/brave_search_plugin/models.py
src/openclaw_moneybot/shared/config.py
src/openclaw_moneybot/shared/base.py
```

## 11.2 Validator and model follow-ups

- [ ] Add test: browser governor model validators reject invalid step combinations and preserve allowed ones.
- [ ] Add test: arXiv/Wikipedia/Brave model validators reject malformed URLs/IDs and preserve normalized valid inputs.
- [ ] Add test: shared base model helpers preserve the repo’s strict validation behavior for malformed payloads.
- [ ] Add test: shared config validators cover blank-env, trimming, bounds, and local-only safety branches still listed as uncovered.
- [ ] Add test: config parsing remains deterministic for optional provider, governor, and rollout fields with blank-string input.

---

# 12. P2 - Final Validation and Coverage Review

## 12.1 Implementation checklist

- [ ] Add or update the relevant unit test modules for each targeted service/backend.
- [ ] Keep all new tests offline with mock transports, fake clients, or fake page/context objects.
- [ ] Prefer direct unit tests for helper/parser branches over broad integration tests for these gaps.

## 12.2 Validation checklist

- [ ] Run `uv run --python 3.11 ruff check .`
- [ ] Run `uv run --python 3.11 mypy .`
- [ ] Run `uv run --python 3.11 pytest`
- [ ] Run `uv run --python 3.11 pytest --cov=src/openclaw_moneybot --cov-report=term-missing:skip-covered`
- [ ] Re-review the lowest-covered modules and decide whether any meaningful gaps remain after the UNIT_TEST3 pass.
