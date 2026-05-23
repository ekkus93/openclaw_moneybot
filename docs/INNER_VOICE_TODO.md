# INNER_VOICE_TODO.md

# OpenClaw MoneyBot - Inner Voice, Debate, and Arbiter Implementation TODO

This TODO tracks the implementation of the **inner voice plugin**, the bounded
**OpenClaw-versus-Inner-Voice debate loop**, and the required **Arbiter** escalation path.

The goal is **not** to build an unbounded multi-agent system. The goal is to add a
**narrow, auditable, fail-closed disagreement layer** that:

- challenges weak assumptions from the main model
- records structured critique instead of freeform hidden reasoning
- permits bounded debate with transcript capture
- escalates unresolved disagreement to a required Arbiter
- preserves existing deterministic authority boundaries
- keeps all durable records linked through the ledger and evidence archive

This work must remain aligned with the current architecture:

```text
local LLM(s) -> orchestration -> narrow skills -> deterministic validators/schemas
-> governed plugins/services -> local ledger/archive/wallet/email
```

---

# Priority legend

```text
P0 = required foundation and safety-critical implementation work
P1 = important orchestration, observability, and rollout-completion work
P2 = operational polish, diagnostics, and post-v1 preparation
```

---

# 0. Global rules for the inner voice system

- [x] Keep the inner voice, debate, and Arbiter boundaries narrow and separately testable.
- [x] Keep the inner voice plugin advisory and read-only.
- [x] Keep the Arbiter limited to disagreement resolution between OpenClaw and the inner voice.
- [x] Do not allow inner voice or Arbiter code to call wallet, email, browser, shell, or other side-effect tools.
- [ ] Do not allow inner voice or Arbiter outputs to override deterministic policy, TOS/legal gates, budget caps, ledger requirements, or wallet controls.
- [x] Do not use LiteLLM or any generic third-party LLM routing proxy.
- [x] Use direct provider-specific adapters for OpenAI, Ollama, and llama-server.
- [x] Keep secrets out of prompts, transcripts, logs, exceptions, and persisted artifacts.
- [x] Fail closed on malformed output, missing required config, unsafe provider mode, and required-path failures.
- [x] Preserve full auditability through ledger-linked records and evidence archive artifacts.
- [x] Treat exchanged dialogue as auditable transcript content, not as hidden private chain-of-thought.
- [x] Require typed request/response models for every boundary: inner voice review, debate session, debate turn, and Arbiter resolution.
- [x] Require unit tests for happy paths, blocked paths, malformed-input paths, and persistence linkage.
- [x] Require integration tests for orchestration gating, transcript persistence, and Arbiter escalation.

---

# 1. P0 - Shared design and foundation work

## 1.1 Confirm final naming and scope

- [x] Confirm `inner_voice_plugin` as the implementation name.
- [x] Confirm `Arbiter` as the operator-facing disagreement resolver name.
- [x] Confirm that v1 scope includes:
  - [x] inner voice critique passes
  - [x] bounded debate
  - [x] debate transcript persistence
  - [x] required Arbiter escalation
- [x] Confirm that v1 scope excludes:
  - [x] unrestricted multi-agent swarms
  - [x] tool-using inner voice behavior
  - [x] Arbiter reruns on the same debate session
  - [x] operator-editable prompt templates

## 1.2 Repository structure and module layout

- [x] Create inner voice plugin package under `src/openclaw_moneybot/plugins/inner_voice_plugin/`.
- [x] Decide final file layout, such as:
  - [x] `__init__.py`
  - [x] `models.py`
  - [x] `service.py`
  - [x] `prompting.py`
  - [x] `providers.py`
  - [x] `debate.py`
  - [x] `arbiter.py`
  - [x] `errors.py`
- [x] Decide whether provider adapters live inside the plugin package or in a small shared LLM adapter area.
- [x] Keep provider transport logic isolated from orchestration policy logic.

## 1.3 Shared contracts and enums

- [x] Add or confirm shared enums/types needed by the inner voice system.
  - [x] `ProviderName`
  - [x] `InnerVoiceStage`
  - [x] `InnerVoiceSubjectType`
  - [x] `EvidenceType` additions if needed
  - [x] `InnerVoiceDisposition`
  - [x] `InnerVoiceObjectionSeverity`
  - [x] `DebateSpeaker`
  - [x] `DebateTurnType`
  - [x] `DebateEndedReason`
  - [x] `ArbiterFinalResolution`
  - [x] `ArbiterPrevailingSide`
- [x] Add shared record-link conventions for linking inner voice and Arbiter events back to opportunities, plans, spend requests, execution steps, and experiment reviews.
- [x] Ensure every contract is serializable and safe for ledger persistence.

## 1.4 Shared record and evidence planning

- [x] Add or confirm record-type support for:
  - [x] `INNER_VOICE_REVIEW`
  - [x] `INNER_VOICE_DEBATE`
  - [x] `ARBITER_REVIEW`
- [x] Add or confirm evidence-type support for:
  - [x] `inner_voice_prompt`
  - [x] `inner_voice_response`
  - [x] `inner_voice_failure`
  - [x] `inner_voice_debate_transcript`
  - [x] `inner_voice_debate_summary`
  - [x] `arbiter_prompt`
  - [x] `arbiter_response`
  - [x] `arbiter_resolution_summary`
- [ ] Decide whether additional audit-event types are needed for:
  - [x] debate session start
  - [x] debate session end
  - [x] arbiter escalation request
  - [x] arbiter invocation failure

---

# 2. P0 - Shared configuration implementation

## 2.1 Inner voice config model

- [x] Add `InnerVoiceConfig` to shared config loading.
- [x] Implement fields for:
  - [x] `enabled`
  - [x] `provider`
  - [x] `model_name`
  - [x] `base_url`
  - [x] `api_key_env_var`
  - [x] `allow_non_local_provider`
  - [x] `timeout_seconds`
  - [x] `temperature`
  - [x] `top_p`
  - [x] `max_output_tokens`
  - [x] `max_input_chars`
  - [x] `max_objections`
  - [x] `max_evidence_items`
  - [x] `max_chars_per_evidence`
  - [x] `archive_raw_prompt`
  - [x] `archive_raw_response`
  - [x] `archive_redaction_mode`
  - [x] `persist_failures`
  - [x] `max_debate_rounds`
  - [x] `archive_debate_transcript`
  - [x] `archive_debate_turn_metadata`
  - [x] `invocation_policy`
  - [x] `run_after_stages`
  - [x] `require_for_spend`
  - [x] `require_for_irreversible_actions`
  - [x] `low_confidence_threshold`
  - [x] `stale_evidence_days`
  - [x] `allow_hosted_provider`

## 2.2 Arbiter config model

- [x] Add `ArbiterConfig` to shared config loading.
- [x] Implement fields for:
  - [x] `provider`
  - [x] `model_name`
  - [x] `base_url`
  - [x] `api_key_env_var`
  - [x] `allow_non_local_provider`
  - [x] `timeout_seconds`
  - [x] `temperature`
  - [x] `top_p`
  - [x] `max_output_tokens`
  - [x] `max_input_chars`
  - [x] `archive_raw_prompt`
  - [x] `archive_raw_response`
  - [x] `archive_redaction_mode`
  - [x] `persist_failures`
  - [x] `allow_hosted_provider`
- [x] Ensure there is **no Arbiter enable flag** in v1.

## 2.3 Config validation rules

- [x] Validate that inner voice `enabled=True` requires non-empty `model_name`.
- [x] Validate provider enum membership for inner voice and Arbiter.
- [x] Validate `openai` requires `allow_hosted_provider=True`.
- [x] Validate local-provider URLs default to loopback or explicitly allowed non-local endpoints.
- [x] Validate `max_debate_rounds >= 1`.
- [x] Validate transcript archival settings when debate mode is present.
- [x] Validate Arbiter config is present whenever debate/Arbiter workflow is implemented.
- [x] Validate raw archival disablement still preserves sanitized summaries.
- [x] Validate config errors fail closed with explicit messages.

## 2.4 Config docs and examples

- [x] Add config examples for:
  - [x] local-only inner voice + local Arbiter
  - [x] local inner voice + hosted Arbiter
  - [x] hosted inner voice + hosted Arbiter with explicit opt-in
- [x] Make clear that example model names are examples, not defaults.

---

# 3. P0 - Implement provider adapter layer

## 3.1 Shared adapter interfaces

- [x] Implement normalized provider request model:
  - [x] `InnerVoicePromptRequest`
  - [x] `ArbiterPromptRequest` or compatible shared prompt envelope
- [x] Implement normalized provider response model:
  - [x] `InnerVoiceRawResponse`
  - [x] Arbiter raw response equivalent or shared result envelope
- [x] Add common adapter metadata fields:
  - [x] `provider_name`
  - [x] `base_url`
  - [x] `model_name`
  - [x] `timeout_seconds`
  - [x] `max_output_tokens`
  - [x] `supports_json_mode`
  - [x] `supports_system_prompt`

## 3.2 OpenAI adapter

- [x] Implement direct HTTPS adapter for OpenAI.
- [x] Request strict JSON object output.
- [x] Capture finish reason and token usage when available.
- [ ] Reject unsupported endpoint/model combinations that cannot satisfy JSON requirements.
- [x] Respect hosted-provider opt-in rules.

## 3.3 Ollama adapter

- [x] Implement direct HTTP adapter for Ollama.
- [x] Use chat/JSON output mode where supported.
- [x] Reject non-JSON assistant output as malformed.
- [x] Capture provider payload for normalized summary fields.

## 3.4 llama-server adapter

- [x] Implement direct OpenAI-compatible adapter for llama-server.
- [x] Validate compatibility assumptions around JSON output.
- [x] Reject runtime modes that cannot satisfy structured output requirements.
- [ ] Document and test any minimal compatibility trimming/post-processing.

## 3.5 Adapter error handling

- [x] Normalize provider-unavailable errors.
- [x] Normalize timeout errors.
- [x] Normalize invalid-auth errors.
- [x] Normalize malformed JSON and schema-failure cases.
- [x] Ensure adapters never silently retry or silently fall back to another provider/model.

## 3.6 Provider health checks

- [x] Implement `health()` for inner voice providers.
- [x] Implement `health()` for Arbiter providers.
- [x] Return stable health states such as:
  - [x] `ok`
  - [x] `missing_api_key`
  - [x] `provider_unreachable`
  - [x] `misconfigured`
  - [x] `disabled` where applicable for inner voice

---

# 4. P0 - Implement inner voice domain models

## 4.1 Review request models

- [x] Implement `InnerVoiceReviewRequest`.
- [x] Implement `EvidenceSummary`.
- [x] Enforce ISO 8601 UTC timestamps.
- [x] Enforce bounded, schema-friendly `structured_context`.
- [x] Enforce `max_objections` bounds.
- [x] Ensure `claim_summary` is visible-summary text, not chain-of-thought.

## 4.2 Review result models

- [x] Implement `InnerVoiceReviewResult`.
- [x] Implement `InnerVoiceObjection`.
- [x] Enforce disposition enum validation.
- [x] Enforce severity enum validation.
- [x] Enforce `confidence_adjustment` range from `-1.0` to `0.0`.
- [x] Ensure `raw_response_summary` is a compact normalized map.

## 4.3 Debate models

- [x] Implement `InnerVoiceDebateSession`.
- [x] Implement `InnerVoiceDebateTurn`.
- [x] Add fields for:
  - [x] `debate_id`
  - [x] `stage`
  - [x] `subject_type`
  - [x] `subject_id`
  - [x] `initiated_by`
  - [x] `max_rounds_configured`
  - [x] `completed_rounds`
  - [x] `ended_reason`
  - [x] `converged`
  - [x] `arbiter_requested_by`
  - [x] `arbiter_review_id`
  - [x] transcript artifact linkage
- [x] Add turn-level fields for:
  - [x] `round_index`
  - [x] `turn_index`
  - [x] `speaker`
  - [x] `turn_type`
  - [x] `message_text`
  - [x] `cited_evidence_ids`
  - [x] `disposition_signal`
  - [x] `request_arbiter`
  - [x] `created_at`

## 4.4 Arbiter models

- [x] Implement `ArbiterResolutionRequest`.
- [x] Implement `ArbiterResolutionResult`.
- [x] Add input fields for:
  - [x] `arbiter_review_id`
  - [x] `debate_id`
  - [x] `stage`
  - [x] `subject_type`
  - [x] `subject_id`
  - [x] `openclaw_review_id`
  - [x] `inner_voice_review_id`
  - [x] `openclaw_position_summary`
  - [x] `inner_voice_position_summary`
  - [x] `disagreement_summary`
  - [x] `transcript_archive_ids`
  - [x] `transcript_summary`
  - [x] `evidence_summary`
  - [x] `constraints_summary`
  - [x] `policy_summary`
  - [x] `tos_summary`
  - [x] `budget_summary`
  - [x] `resolution_goal`
- [x] Add output fields for:
  - [x] `final_resolution`
  - [x] `prevailing_side`
  - [x] `resolution_summary`
  - [x] `rationale_summary`
  - [x] `required_followups`
  - [x] `unresolved_risks`
  - [x] `raw_response_summary`
  - [x] artifact linkage

---

# 5. P0 - Implement prompt construction and sanitization

## 5.1 Inner voice prompt rendering

- [x] Implement deterministic prompt field ordering.
- [x] Implement bounded text size handling.
- [x] Implement explicit truncation markers.
- [x] Implement stage-specific fixed-in-code prompt fragments for:
  - [x] `opportunity_ranking`
  - [x] `tos_legal_check`
  - [x] `budget_planning`
  - [x] `pre_execution`
  - [x] `post_review`
- [x] Implement shared core challenger instructions.

## 5.2 Evidence preparation

- [x] Implement deterministic evidence ordering.
- [x] Implement evidence deduplication by URL/archive ID.
- [x] Implement `max_evidence_items`.
- [x] Implement `max_chars_per_evidence`.
- [x] Implement stale-evidence labelling before prompt construction.
- [x] Ensure raw HTML, screenshots, and attachments are summarized, not inlined.

## 5.3 Arbiter prompt rendering

- [x] Implement Arbiter prompt construction from structured disagreement context.
- [x] Ensure the Arbiter sees:
  - [x] both sides' visible positions
  - [x] disagreement summary
  - [x] transcript summary or bounded transcript content
  - [x] evidence summaries
  - [x] constraints/policy/TOS/budget summaries where relevant
- [x] Ensure the Arbiter prompt clarifies whether escalation came from max rounds or a request.

## 5.4 Secret scanning and sanitization

- [x] Implement secret scanning for prompt archival.
- [x] Implement secret scanning for raw response archival.
- [x] Implement secret scanning for debate transcript archival.
- [x] Redact or hash:
  - [x] API keys
  - [x] bearer tokens
  - [x] wallet-sensitive metadata
  - [x] disallowed email/credential data
  - [x] oversized copied document chunks
- [x] Implement deterministic placeholder artifacts when raw text cannot be safely retained.

---

# 6. P0 - Implement inner voice plugin service

## 6.1 Core service behavior

- [x] Implement service entrypoint for `review()` / `generate_critique()`.
- [x] Load config and choose exactly one configured provider.
- [x] Build normalized prompt request.
- [x] Call provider adapter.
- [x] Parse returned JSON.
- [x] Validate against `InnerVoiceReviewResult`.
- [x] Return normalized persistence payloads plus structured result.

## 6.2 Failure behavior

- [x] Detect and classify:
  - [x] provider unavailable
  - [x] timeout
  - [x] invalid auth
  - [x] malformed provider output
  - [x] schema validation failure
  - [x] prompt too large
  - [x] required stage invocation missing
- [ ] Produce explicit structured failure objects.
- [x] Ensure required-path failures resolve fail-closed.
- [x] Ensure optional-path failures remain auditable when `persist_failures=True`.

## 6.3 Persistence payload shaping

- [x] Return archive payloads for:
  - [x] sanitized prompt summary
  - [x] raw prompt if allowed
  - [x] sanitized response summary
  - [x] raw response if allowed
- [x] Return ledger-ready payload for `INNER_VOICE_REVIEW`.
- [x] Include artifact linkage fields in the result.

---

# 7. P0 - Implement debate-loop orchestration

## 7.1 Debate eligibility and triggering

- [x] Decide where in orchestration debate mode is entered.
- [x] Trigger debate only on configured stages.
- [ ] Trigger debate only when disagreement handling is relevant for that stage.
- [x] Respect `max_debate_rounds` from config.

## 7.2 Debate round execution

- [x] Build the initial OpenClaw position summary for debate use.
- [x] Build the first inner voice objection pass.
- [x] Implement bounded round execution.
- [x] Ensure each round normally contains:
  - [x] one OpenClaw turn
  - [x] one inner voice turn
- [x] Allow early termination on convergence.
- [x] Allow explicit `request_arbiter` from either side.

## 7.3 Convergence evaluation

- [x] Implement structured convergence checks.
- [x] Determine convergence by:
  - [x] matching disposition
  - [x] no unresolved `high` or `block` objections
  - [x] no active Arbiter request
- [x] Avoid naive plain-text matching as the convergence criterion.

## 7.4 Debate end-state handling

- [x] Record `ended_reason = converged` when agreement is reached.
- [x] Record `ended_reason = max_rounds_reached` when debate ceiling is hit.
- [x] Record `ended_reason = request_arbiter` when escalation is requested.
- [ ] Record `ended_reason = orchestrator_escalation` when orchestration escalates for safety reasons.
- [x] Record `ended_reason = failure` when debate cannot complete safely.

---

# 8. P0 - Implement debate transcript persistence

## 8.1 Transcript capture

- [x] Persist every turn in order.
- [x] Preserve the exchanged dialogue text after sanitization.
- [x] Avoid lossy paraphrasing of turn content.
- [x] Capture round number, turn number, speaker, turn type, and arbiter request flag.
- [x] Capture cited evidence references.

## 8.2 Transcript artifact creation

- [x] Archive debate transcript through `receipt_and_evidence_archiver`.
- [x] Archive a debate summary artifact.
- [x] Support raw transcript archival when safe and configured.
- [x] Support sanitized transcript archival when raw text is not safe.

## 8.3 Debate ledger linkage

- [x] Create ledger-linked `INNER_VOICE_DEBATE` records.
- [x] Link debate records to:
  - [x] subject
  - [x] stage
  - [x] inner voice review IDs
  - [x] transcript artifact IDs
  - [x] later Arbiter record if invoked

## 8.4 Transcript audit UX

- [x] Ensure an operator can reconstruct the debate round by round from persisted records.
- [x] Ensure transcript records clearly distinguish:
  - [x] OpenClaw turns
  - [x] inner voice turns
  - [x] arbiter request turns
  - [x] resolution notes
- [x] Ensure the system never labels the transcript as hidden internal reasoning.

---

# 9. P0 - Implement Arbiter service

## 9.1 Arbiter invocation policy

- [x] Invoke Arbiter when:
  - [x] `max_debate_rounds` is reached without agreement
  - [x] either OpenClaw or inner voice requests Arbiter resolution
- [x] Ensure Arbiter is treated as required, not optional, in the debate-resolution path.
- [x] Ensure one Arbiter pass per debate session in v1.

## 9.2 Arbiter request building

- [x] Build `ArbiterResolutionRequest` from:
  - [x] debate session metadata
  - [x] OpenClaw position summary
  - [x] inner voice position summary
  - [x] disagreement summary
  - [x] transcript summary / artifacts
  - [x] evidence summaries
  - [x] constraints and stage summaries
- [x] Ensure request size stays within configured bounds.

## 9.3 Arbiter provider execution

- [x] Select Arbiter provider/model from Arbiter config.
- [x] Allow provider/model to differ from OpenClaw and inner voice.
- [x] Apply the same direct-adapter, no-LiteLLM rules.
- [x] Use lower temperature and structured JSON output.

## 9.4 Arbiter response handling

- [x] Parse returned JSON.
- [x] Validate against `ArbiterResolutionResult`.
- [x] Enforce final-resolution enum constraints.
- [x] Normalize compact `raw_response_summary`.

## 9.5 Arbiter finality rules

- [x] Treat Arbiter resolution as final among the LLM participants for the debate session.
- [x] Do not rerun Arbiter on the same debate session in v1.
- [x] Ensure Arbiter result ends further OpenClaw-versus-inner-voice debate for that session.
- [ ] Ensure deterministic policy still outranks Arbiter output.

## 9.6 Arbiter failure handling

- [x] Classify Arbiter provider/network/malformed-output failures.
- [x] Ensure required Arbiter failure resolves workflow to `needs_review`.
- [x] Archive sanitized request summary on Arbiter failure.
- [x] Persist `ARBITER_REVIEW` failure records with explicit failure fields.

---

# 10. P0 - Implement deterministic orchestration interpretation

## 10.1 Inner voice result interpretation

- [ ] Implement stage-by-stage interpretation matrix.
- [ ] Ensure `block` objections and configured thresholds route to `needs_review` when required.
- [ ] Ensure inner voice `proceed` never authorizes irreversible action by itself.

## 10.2 Debate result interpretation

- [ ] Ensure converged debate feeds a single structured result back into orchestration.
- [ ] Ensure debate transcript IDs remain linked to downstream review records.

## 10.3 Arbiter result interpretation

- [ ] If Arbiter returns `adopt_openclaw`, continue with that position subject to deterministic gates.
- [ ] If Arbiter returns `adopt_inner_voice`, continue with that position subject to deterministic gates.
- [ ] If Arbiter returns `proceed_with_followups`, create required follow-up work.
- [ ] If Arbiter returns `needs_review` or `block_pending_checks`, prevent auto-advance.
- [ ] Ensure no LLM result can lower an existing deterministic `block` or `needs_review`.

## 10.4 Spend and irreversible-action handling

- [ ] Ensure required-path failures resolve to `needs_review`.
- [ ] Ensure spend and irreversible actions require the configured inner voice path.
- [ ] Ensure spend and irreversible actions also respect Arbiter failure behavior where Arbiter is required.

---

# 11. P1 - Integrate with archive and ledger services

## 11.1 Evidence archival integration

- [x] Wire prompt/response/debate/Arbiter artifact creation through `receipt_and_evidence_archiver`.
- [x] Preserve audit metadata:
  - [x] review IDs
  - [x] debate IDs
  - [x] subject IDs
  - [x] stage
  - [x] provider
  - [x] model name
  - [x] timestamps

## 11.2 Ledger integration

- [x] Wire `INNER_VOICE_REVIEW` creation through `ledger_skill` or `ledger_api`.
- [x] Wire `INNER_VOICE_DEBATE` creation through `ledger_skill` or `ledger_api`.
- [x] Wire `ARBITER_REVIEW` creation through `ledger_skill` or `ledger_api`.
- [x] Ensure failure events are also persisted when configured.

## 11.3 Cross-record linkage

- [x] Link inner voice passes to debate sessions.
- [x] Link debate sessions to Arbiter records.
- [x] Link all artifacts back to the subject under review.
- [x] Preserve immutable prior-pass and prior-debate history.

---

# 12. P1 - Add testing coverage

## 12.1 Config tests

- [x] Test valid inner voice config loads.
- [x] Test valid Arbiter config loads.
- [x] Test missing `model_name` rejection when enabled.
- [x] Test hosted-provider opt-in enforcement.
- [x] Test invalid URL/provider combinations fail.
- [x] Test `max_debate_rounds` minimum enforcement.

## 12.2 Provider adapter unit tests

- [x] Test OpenAI request shaping.
- [x] Test OpenAI response parsing.
- [x] Test Ollama request shaping.
- [x] Test Ollama response parsing.
- [x] Test llama-server request shaping.
- [x] Test llama-server response parsing.
- [x] Test malformed JSON handling for all providers.
- [x] Test auth/timeouts/unreachable-host failures for all providers.

## 12.3 Inner voice service tests

- [x] Test successful critique generation.
- [x] Test schema validation failure path.
- [x] Test prompt-too-large path.
- [x] Test failure persistence behavior.
- [x] Test archive payload shaping.

## 12.4 Debate-loop tests

- [x] Test transcript ordering across multiple rounds.
- [x] Test early convergence.
- [x] Test max-round escalation.
- [x] Test `request_arbiter=True` from OpenClaw.
- [x] Test `request_arbiter=True` from inner voice.
- [x] Test debate immutability and linkage.

## 12.5 Arbiter tests

- [x] Test Arbiter request shaping from disagreement context.
- [x] Test Arbiter successful final resolution.
- [x] Test Arbiter result linkage to debate session.
- [x] Test Arbiter failure produces `needs_review` on required path.
- [x] Test Arbiter does not rerun within the same v1 debate session.

## 12.6 Integration tests

- [x] Test stage-triggered inner voice invocation.
- [ ] Test spend-path behavior with inner voice and debate.
- [ ] Test irreversible-action path behavior with inner voice and debate.
- [x] Test transcript and artifact persistence end-to-end.
- [x] Test Arbiter escalation end-to-end.
- [ ] Test deterministic policy still outranks LLM and Arbiter outputs.

---

# 13. P1 - Operator-facing documentation updates

## 13.1 README and architecture docs

- [x] Update `README.md` with inner voice and Arbiter config documentation once implemented.
- [x] Update `docs/OPENCLAW_MONEYBOT_ARCHITECTURE.md` with:
  - [x] inner voice plugin inventory entry
  - [x] debate-loop architecture note
  - [x] Arbiter escalation note

## 13.2 Runtime and operational docs

- [x] Document required environment variables.
- [x] Document local-provider setup expectations for Ollama and llama-server.
- [x] Document hosted-provider opt-in expectations.
- [x] Document what transcript logging captures and what it does not capture.

---

# 14. P1 - Operational metrics and observability

## 14.1 Metrics implementation

- [ ] Emit or persist metrics for:
  - [ ] inner voice invocation count by stage
  - [ ] `needs_review` rate by stage
  - [ ] objection severity distribution
  - [ ] debate session count by stage
  - [ ] average completed debate rounds
  - [ ] arbiter request rate
  - [ ] arbiter invocation rate
  - [ ] arbiter prevailing-side distribution
  - [ ] arbiter failure rate
  - [ ] follow-up check creation rate
  - [ ] provider failure rate
  - [ ] average prompt size
  - [ ] average response size
  - [ ] average transcript size

## 14.2 Diagnostics and audit ergonomics

- [ ] Add stable summaries for `raw_response_summary`.
- [ ] Ensure archived summaries are understandable without raw provider payloads.
- [ ] Ensure debate and Arbiter records are queryable by subject, stage, and outcome.

---

# 15. P2 - Rollout hardening and follow-up work

## 15.1 Progressive rollout controls

- [ ] Start with selected high-risk stages only.
- [ ] Start with transcript capture enabled by default.
- [ ] Measure noise/usefulness before broader rollout.

## 15.2 Post-v1 preparation tasks

- [ ] Note follow-up design items for post-v1:
  - [ ] operator-configurable prompt templates with guardrails
  - [ ] branching review trees
  - [ ] Arbiter reruns only when genuinely new evidence arrives
  - [ ] richer transcript viewers or audit tools

## 15.3 Final acceptance checklist

- [x] Inner voice critique path works with schema validation and fail-closed behavior.
- [x] Debate loop is bounded by config and fully auditable.
- [x] Transcript artifacts preserve exchanged dialogue safely.
- [x] Arbiter is invoked on max-round or explicit-request escalation.
- [x] Arbiter result is final for the v1 debate session.
- [ ] Deterministic policy remains the ultimate authority.
- [x] Ledger and evidence linkage are complete for review, debate, and Arbiter records.
- [x] Unit, integration, mypy, ruff, and pytest all pass.
