# UNIT_TEST2_TODO.md

# OpenClaw MoneyBot - Unit Test Coverage Follow-up TODO 2

This TODO tracks the next focused unit-test pass after the PLUGINS1 wave and the latest full coverage review.

The goal is **not** to chase raw percentages. The goal is to add tests around:

- branch-heavy safety decisions
- fail-closed validation behavior
- malformed ledger/event payload handling
- deterministic ranking, filtering, and export logic
- parser/helper edge cases that could silently drift

Current reference point from the latest coverage run:

```text
TOTAL: 93%
```

Highest-value remaining coverage hotspots:

- `skills/account_eligibility_checker/runner.py`
- `skills/duplicate_opportunity_detector/runner.py`
- `plugins/opportunity_index_plugin/service.py`
- `plugins/metrics_export_plugin/service.py`
- `plugins/counterparty_snapshot_plugin/service.py`

Secondary but still worthwhile follow-ups:

- `plugins/artifact_renderer_plugin/service.py`
- `plugins/download_quarantine_plugin/service.py`
- `plugins/inbox_observer_plugin/service.py`
- `skills/terms_change_monitor/runner.py`

---

# Priority legend

```text
P0 = branch-heavy safety or decision logic with meaningful fail-closed behavior
P1 = important plugin/query/parser branches and malformed-input handling
P2 = secondary helper, parser, and edge-case coverage improvements
```

---

# 1. P0 - Expand Account Eligibility Checker Decision Coverage

## 1.1 Goal

Add a comprehensive decision-matrix test pass for:

```text
src/openclaw_moneybot/skills/account_eligibility_checker/runner.py
```

The focus is the rule-text parsing logic that determines whether an opportunity is eligible, blocked, incomplete, or needs review.

## 1.2 Missing and profile-data branches

- [x] Add test: empty rule text adds `missing_rule_text`.
- [x] Add test: personal-account requirement blocks when `personal_account_allowed=False`.
- [x] Add test: non-bot social requirement blocks when `non_bot_social_identity_available=False`.
- [x] Add test: account-age requirement becomes incomplete when `platform_account_age_days=None`.
- [x] Add test: account-age requirement blocks when configured age is too low.
- [x] Add test: reputation requirement becomes review-required when `profile_reputation_available=None`.
- [x] Add test: reputation requirement blocks when `profile_reputation_available=False`.

## 1.3 Geo, citizenship, and age gating

- [x] Add test: matched geo phrase with no region data adds `region_unknown`.
- [x] Add test: matched geo phrase with disallowed region blocks with `geo_restriction`.
- [x] Add test: matched geo phrase with allowed region does not add geo failure codes.
- [x] Add test: citizenship/residency language without matched geo phrase adds `citizenship_or_residency_requirement`.
- [x] Add test: age requirement becomes incomplete when `age_years=None`.
- [x] Add test: age requirement blocks when under 18.
- [x] Add test: age requirement passes when age is 18 or above.

## 1.4 Business, tax, infrastructure, and repo-history branches

- [x] Add test: business-entity requirement becomes incomplete when `has_business_entity=None`.
- [x] Add test: business-entity requirement blocks when `has_business_entity=False`.
- [x] Add test: KYC/tax requirement becomes review-required when `tax_identity_available=None`.
- [x] Add test: KYC/tax requirement blocks when `tax_identity_available=False`.
- [x] Add test: private-infrastructure requirement becomes review-required when `private_infrastructure_available=None`.
- [x] Add test: private-infrastructure requirement blocks when `private_infrastructure_available=False`.
- [x] Add test: repository-history requirement becomes incomplete when `repository_history_available=None`.
- [x] Add test: repository-history requirement blocks when `repository_history_available=False`.
- [x] Add test: prior-contribution requirement blocks when `prior_contribution_tags` is empty.

## 1.5 OS, hardware, and payout-method parsing

- [x] Add test: required OS not in `operating_systems` blocks with the normalized OS reason.
- [x] Add test: required hardware not in `available_hardware` blocks with the normalized hardware reason.
- [x] Add test: BTC/crypto payout phrase blocks when asset not supported.
- [x] Add test: non-crypto payout phrase blocks when payout method not supported.
- [x] Add test: `payment_method_hint` path triggers unsupported payout-method blocking even when rule text is vague.
- [x] Add test: `asset_hint` path triggers unsupported asset blocking even when rule text is vague.
- [x] Add test: manual approval language adds `manual_payment_approval_needed`.

## 1.6 Final decision prioritization

- [x] Add test: any blocked rule forces final decision `BLOCKED` even when missing/review-required signals also exist.
- [x] Add test: review-required without blocks returns `NEEDS_REVIEW`.
- [x] Add test: missing-only scenario returns `INCOMPLETE`.
- [x] Add test: clean supported scenario returns `ELIGIBLE`.
- [x] Add test: reasons list remains deterministic and stable for mixed-signal inputs.

---

# 2. P0 - Expand Metrics Export Plugin Branch Coverage

## 2.1 Goal

Add deep branch coverage for:

```text
src/openclaw_moneybot/plugins/metrics_export_plugin/service.py
```

The focus is bounded export behavior, filter validation, row building, output formatting, and helper functions that normalize ledger-event payloads.

## 2.2 Export request validation

- [x] Add test: unsupported `export_type` raises the expected `ValueError`.
- [x] Add test: unsupported `output_format` raises the expected `ValueError`.
- [x] Add test: unsupported outcome filter on `strategy_summaries` raises the "not supported" error.
- [x] Add test: unsupported outcome value on `experiment_reviews` raises the expected `ValueError`.
- [x] Add test: unsupported outcome value on `payout_reconciliations` raises the expected `ValueError`.

## 2.3 Experiment review export branches

- [x] Add test: review-export path correctly reads nested `payload` records from generic ledger events.
- [x] Add test: review-export path correctly falls back when `experiment_review_id` is absent.
- [x] Add test: review-export path includes rows even when `get_opportunity()` returns `None`.
- [x] Add test: `start_day` filter excludes rows before the lower bound.
- [x] Add test: `end_day` filter excludes rows after the upper bound.
- [x] Add test: `opportunity_category` filter excludes mismatched categories.
- [x] Add test: `outcome_category` filter excludes mismatched review decisions.

## 2.4 Payout reconciliation export branches

- [x] Add test: payout-export path builds rows from payout reconciliation ledger events.
- [x] Add test: payout-export path handles missing typed opportunity records without crashing.
- [x] Add test: payout-export path excludes rows when status filter does not match.
- [x] Add test: payout-export summary counts payout statuses deterministically.

## 2.5 Strategy summary export branches

- [x] Add test: strategy-export path handles nested generic ledger payloads.
- [x] Add test: strategy-export path handles non-list `lesson_categories` by emitting an empty joined string.
- [x] Add test: strategy-export path counts `what_worked` and `what_failed` lists correctly.
- [x] Add test: strategy-export path excludes rows when category filter does not match.

## 2.6 Output-path and serialization helpers

- [x] Add test: `_resolve_output_path()` rejects export-root escape attempts.
- [x] Add test: `_write_output()` writes deterministic JSON for empty rows.
- [x] Add test: `_write_output()` writes CSV headers correctly when rows are empty.
- [x] Add test: `_csv_ready_row()` converts `None` to empty strings.
- [x] Add test: `_record_payload()` falls back to `event.payload` when nested `payload` is missing.
- [x] Add test: `_opportunity_id_for_event()` falls back to `event.related_id` when `related_record_id` is missing.
- [x] Add test: `_build_summary()` returns empty `outcome_counts` for row types without decision/status fields.
- [x] Add test: bounded export with no rows still records output, evidence, and ledger metadata safely.

---

# 3. P1 - Expand Opportunity Index Plugin Coverage

## 3.1 Goal

Add coverage for rebuild/query/indexing edge cases in:

```text
src/openclaw_moneybot/plugins/opportunity_index_plugin/service.py
```

## 3.2 Query and rebuild behavior

- [x] Add test: `query_similar()` rebuilds the index automatically when the index file is missing.
- [x] Add test: `query_similar()` returns no matches when scores remain below the 0.6 threshold.
- [x] Add test: `query_similar()` preserves deterministic score ordering for ties.
- [x] Add test: `update_opportunity()` replaces an existing entry instead of duplicating it.
- [x] Add test: `rebuild_index()` records the expected entry count in its ledger payload.

## 3.3 Entry-building from related ledger events

- [x] Add test: `_build_entry()` raises for an unknown opportunity ID.
- [x] Add test: `_build_entry()` picks up matching rule snapshot hashes from generic ledger records.
- [x] Add test: `_build_entry()` ignores malformed rule-snapshot payloads cleanly.
- [x] Add test: `_build_entry()` ignores rule snapshots for other opportunities.
- [x] Add test: `_build_entry()` picks up experiment-review decision labels when present.
- [x] Add test: `_build_entry()` ignores malformed or unrelated review events cleanly.
- [x] Add test: `_build_entry()` adds raw JSON tags and de-duplicates/sorts them.

## 3.4 Helper logic

- [x] Add test: `_load_entries()` raises when the index file contains a non-list payload.
- [x] Add test: `_score_entry()` returns `exact_source_url` when URLs match exactly.
- [x] Add test: `_score_entry()` returns `near_exact_title` for very high title similarity.
- [x] Add test: `_score_entry()` returns `similar_title` for medium-high title similarity.
- [x] Add test: `_score_entry()` returns `counterparty_match` when counterparties match.
- [x] Add test: `_normalize()` collapses whitespace and handles `None`.
- [x] Add test: `_normalize_url()` strips trailing slashes and lowercases scheme/host.
- [x] Add test: `_reward_range()` returns `None`, `under_25`, `25_to_99`, and `100_plus` at the correct boundaries.
- [x] Add test: `_similarity_bucket()` maps exact/high/medium/low thresholds correctly.

---

# 4. P1 - Expand Duplicate Opportunity Detector Coverage

## 4.1 Goal

Add direct branch coverage for:

```text
src/openclaw_moneybot/skills/duplicate_opportunity_detector/runner.py
```

## 4.2 Matching branches

- [x] Add test: exact source URL match yields `HIGH` confidence and `exact_url_match`.
- [x] Add test: matching rules URL plus exact normalized title yields `normalized_rules_url_match`.
- [x] Add test: matching rules URL plus very high description similarity yields `normalized_rules_url_match`.
- [x] Add test: exact normalized title match without URL match yields `MEDIUM` confidence.
- [x] Add test: near-duplicate repost path requires similarity >= 0.92, same platform, and same payout.
- [x] Add test: high text similarity alone does not trigger `near_duplicate_repost` when platform differs.
- [x] Add test: high text similarity alone does not trigger `near_duplicate_repost` when payout differs.

## 4.3 Incomplete metadata and output stability

- [x] Add test: non-duplicate candidate with missing title triggers `metadata_incomplete_review`.
- [x] Add test: non-duplicate candidate with missing description triggers `metadata_incomplete_review`.
- [x] Add test: duplicate path returns `reuse_existing_opportunity_or_require_review`.
- [x] Add test: non-duplicate path returns `continue_normal_workflow`.
- [x] Add test: multiple matches preserve deterministic matched IDs and reasons ordering.
- [x] Add test: `_normalized()` handles `None`, mixed spacing, and casing deterministically.

---

# 5. P1 - Expand Counterparty Snapshot Plugin Coverage

## 5.1 Goal

Cover the remaining rejection, parser, and helper branches in:

```text
src/openclaw_moneybot/plugins/counterparty_snapshot_plugin/service.py
```

## 5.2 Capture rejections and fail-closed branches

- [x] Add test: unsupported source category is rejected.
- [x] Add test: non-allowlisted host is rejected.
- [x] Add test: non-allowlisted content type is rejected.
- [x] Add test: oversized content is rejected.
- [x] Add test: private/login-like path is rejected.
- [x] Add test: `robots_allowed: no` rejects capture fail-closed.

## 5.3 Previous-snapshot and comparison branches

- [x] Add test: `_find_previous_snapshot()` ignores malformed nested payloads.
- [x] Add test: `_find_previous_snapshot()` ignores snapshots for a different source category.
- [x] Add test: `_find_previous_snapshot()` ignores snapshots for a different counterparty.
- [x] Add test: `_find_previous_snapshot()` returns the most recent snapshot by captured timestamp.
- [x] Add test: `_changed_fields()` returns all fields when prior indicators are malformed.
- [x] Add test: `_changed_fields()` returns only changed fields when prior indicators are valid.

## 5.4 Parser and normalization helpers

- [x] Add test: `_parse_public_fields()` ignores blank lines and lines without separators.
- [x] Add test: `_parse_public_fields()` supports both `:` and `=` separators.
- [x] Add test: `_parse_public_fields()` converts digit-only values to integers.
- [x] Add test: `_parse_public_fields()` converts recognized boolean values to booleans.
- [x] Add test: `_extract_indicators()` falls back to the counterparty name when `display_name` is absent.
- [x] Add test: `_extract_indicators()` strips invalid email-like fields by returning `None`.
- [x] Add test: `_evidence_tier()` returns `INCOMPLETE`, `STRONG`, `PARTIAL`, and `WEAK` at the correct thresholds.
- [x] Add test: `_freshness_for()` returns `UNKNOWN` when `current_time=None`.
- [x] Add test: `_parse_bool()` returns `None` for unrecognized values.
- [x] Add test: `_bool_field()`, `_int_field()`, and `_string_field()` reject wrong types cleanly.

---

# 6. P2 - Expand Artifact Renderer Plugin Edge-Case Coverage

## 6.1 Goal

Add secondary coverage for:

```text
src/openclaw_moneybot/plugins/artifact_renderer_plugin/service.py
```

## 6.2 Template and validation branches

- [x] Add test: malformed `required_fields` type raises.
- [x] Add test: placeholder marker `TODO` in any field value raises.
- [x] Add test: placeholder marker `TBD` in any field value raises.
- [x] Add test: unknown evidence reference raises.
- [x] Add test: template payload that is not a JSON object raises.

## 6.3 Path-safety branches

- [x] Add test: template path escape attempt is rejected.
- [x] Add test: absolute `output_subdir` is rejected.
- [x] Add test: `..` in `output_subdir` is rejected.
- [x] Add test: resolved render path escape is rejected even after normalization.

---

# 7. P2 - Expand Download Quarantine Plugin Coverage

## 7.1 Goal

Add secondary coverage for:

```text
src/openclaw_moneybot/plugins/download_quarantine_plugin/service.py
```

## 7.2 Promotion and rejection branches

- [x] Add test: promote rejects unknown scan ID.
- [x] Add test: promote rejects non-staged metadata status.
- [x] Add test: host-not-allowlisted branch returns `host_not_allowlisted`.
- [x] Add test: extension-not-allowed branch returns `extension_not_allowed`.
- [x] Add test: MIME-not-allowed branch returns `mime_type_not_allowed`.
- [x] Add test: executable signature branch returns `executable_content_blocked`.

## 7.3 ZIP validation helpers

- [x] Add test: `_validate_zip()` rejects too many entries.
- [x] Add test: `_validate_zip()` rejects excessive uncompressed nested size.
- [x] Add test: `_validate_zip()` rejects absolute paths inside the archive.
- [x] Add test: `_validate_zip()` rejects `..` traversal inside the archive.
- [x] Add test: `_safe_name()` rejects absolute paths.
- [x] Add test: `_safe_name()` rejects traversal-style file names.

---

# 8. P2 - Expand Inbox Observer and Terms Change Monitor Coverage

## 8.1 Goal

Add smaller but useful branch coverage for:

```text
src/openclaw_moneybot/plugins/inbox_observer_plugin/service.py
src/openclaw_moneybot/skills/terms_change_monitor/runner.py
```

## 8.2 Inbox observer follow-ups

- [x] Add test: empty/unsupported inbound message body falls into the unknown classification path deterministically.
- [x] Add test: unsupported attachments are marked consistently as quarantined/unsupported.
- [x] Add test: malformed attachment metadata does not crash observation.
- [x] Add test: excerpt truncation stays deterministic at the configured boundary.

## 8.3 Terms-change monitor follow-ups

- [x] Add test: malformed prior snapshot payload falls back safely.
- [x] Add test: no meaningful change yields the no-change severity path.
- [x] Add test: blocking/legal-risk phrase produces the highest severity path.
- [x] Add test: summary/reason outputs remain deterministic for ambiguous-but-nonblocking changes.

---

# 9. Shared test infrastructure follow-ups

## 9.1 Fixtures and helpers

- [x] Add or refine shared builders for generic ledger-record events used by export/index/snapshot tests.
- [x] Add helper builders for eligibility profiles so branch matrices can stay readable.
- [x] Add helper builders for duplicate-opportunity fingerprints with concise overrides.
- [x] Keep all new fixtures offline, deterministic, and local-only.

## 9.2 Test quality rules

- [x] Prefer direct branch assertions over broad snapshot-style assertions.
- [x] Assert exact reason codes, decisions, and bounded next steps where behavior is policy-relevant.
- [x] Cover malformed-input paths explicitly rather than relying only on happy-path fixtures.
- [x] Avoid duplicating integration coverage when a smaller unit test can isolate the branch directly.

---

# 10. Final validation and completion criteria

## 10.1 Validation tasks

- [x] Run `uv run --python 3.11 ruff check .`
- [x] Run `uv run --python 3.11 mypy .`
- [x] Run `uv run --python 3.11 pytest`
- [x] Run coverage again and compare the targeted modules against the current baseline.

## 10.2 Acceptance criteria

- [x] `account_eligibility_checker` has direct tests for the remaining major rule-decision branches.
- [x] `metrics_export_plugin` has direct tests for export-type-specific row building, filter validation, and helper fallbacks.
- [x] `opportunity_index_plugin` and `duplicate_opportunity_detector` have direct tests for their remaining ranking/matching branches.
- [x] `counterparty_snapshot_plugin` has direct tests for reject paths, helper parsing, and evidence-tier/freshness logic.
- [x] Secondary plugin gaps (`artifact_renderer_plugin`, `download_quarantine_plugin`, `inbox_observer_plugin`) have targeted edge-case coverage added where the remaining misses matter.
- [x] New tests remain deterministic, offline, and aligned with the project safety model.
