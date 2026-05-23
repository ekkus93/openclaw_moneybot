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
- [ ] Do not allow inner voice or Arbiter code to call wallet, email, browser, shell, or other side-effect tools.
- [ ] Do not allow inner voice or Arbiter outputs to override deterministic policy, TOS/legal gates, budget caps, ledger requirements, or wallet controls.
- [x] Do not use LiteLLM or any generic third-party LLM routing proxy.
- [x] Use direct provider-specific adapters for OpenAI, Ollama, and llama-server.
- [ ] Keep secrets out of prompts, transcripts, logs, exceptions, and persisted artifacts.
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
- [ ] Confirm that v1 scope includes:
  - [x] inner voice critique passes
  - [x] bounded debate
  - [x] debate transcript persistence
  - [x] required Arbiter escalation
- [ ] Confirm that v1 scope excludes:
  - [x] unrestricted multi-agent swarms
  - [x] tool-using inner voice behavior
  - [x] Arbiter reruns on the same debate session
  - [x] operator-editable prompt templates

## 1.2 Repository structure and module layout

- [x] Create inner voice plugin package under `src/openclaw_moneybot/plugins/inner_voice_plugin/`.
- [ ] Decide final file layout, such as:
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
  - [ ] debate session start
  - [ ] debate session end
  - [ ] arbiter escalation request
  - [ ] arbiter invocation failure

---

# 2. P0 - Shared configuration implementation

## 2.1 Inner voice config model

- [x] Add `InnerVoiceConfig` to shared config loading.
- [ ] Implement fields for:
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
- [ ] Implement fields for:
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
- [ ] Validate raw archival disablement still preserves sanitized summaries.
- [ ] Validate config errors fail closed with explicit messages.

## 2.4 Config docs and examples

- [x] Add config examples for:
  - [x] local-only inner voice + local Arbiter
  - [x] local inner voice + hosted Arbiter
  - [x] hosted inner voice + hosted Arbiter with explicit opt-in
- [x] Make clear that example model names are examples, not defaults.

---

# 3. P0 - Implement provider adapter layer

## 3.1 Shared adapter interfaces

- [ ] Implement normalized provider request model:
  - [ ] `InnerVoicePromptRequest`
  - [ ] `ArbiterPromptRequest` or compatible shared prompt envelope
- [ ] Implement normalized provider response model:
  - [ ] `InnerVoiceRawResponse`
  - [ ] Arbiter raw response equivalent or shared result envelope
- [ ] Add common adapter metadata fields:
  - [ ] `provider_name`
  - [ ] `base_url`
  - [ ] `model_name`
  - [ ] `timeout_seconds`
  - [ ] `max_output_tokens`
  - [ ] `supports_json_mode`
  - [ ] `supports_system_prompt`

## 3.2 OpenAI adapter

- [ ] Implement direct HTTPS adapter for OpenAI.
- [ ] Request strict JSON object output.
- [ ] Capture finish reason and token usage when available.
- [ ] Reject unsupported endpoint/model combinations that cannot satisfy JSON requirements.
- [ ] Respect hosted-provider opt-in rules.

## 3.3 Ollama adapter

- [ ] Implement direct HTTP adapter for Ollama.
- [ ] Use chat/JSON output mode where supported.
- [ ] Reject non-JSON assistant output as malformed.
- [ ] Capture provider payload for normalized summary fields.

## 3.4 llama-server adapter

- [ ] Implement direct OpenAI-compatible adapter for llama-server.
- [ ] Validate compatibility assumptions around JSON output.
- [ ] Reject runtime modes that cannot satisfy structured output requirements.
- [ ] Document and test any minimal compatibility trimming/post-processing.

## 3.5 Adapter error handling

- [ ] Normalize provider-unavailable errors.
- [ ] Normalize timeout errors.
- [ ] Normalize invalid-auth errors.
- [ ] Normalize malformed JSON and schema-failure cases.
- [ ] Ensure adapters never silently retry or silently fall back to another provider/model.

## 3.6 Provider health checks

- [ ] Implement `health()` for inner voice providers.
- [ ] Implement `health()` for Arbiter providers.
- [ ] Return stable health states such as:
  - [ ] `ok`
  - [ ] `missing_api_key`
  - [ ] `provider_unreachable`
  - [ ] `misconfigured`
  - [ ] `disabled` where applicable for inner voice

---

# 4. P0 - Implement inner voice domain models

## 4.1 Review request models

- [ ] Implement `InnerVoiceReviewRequest`.
- [ ] Implement `EvidenceSummary`.
- [ ] Enforce ISO 8601 UTC timestamps.
- [ ] Enforce bounded, schema-friendly `structured_context`.
- [ ] Enforce `max_objections` bounds.
- [ ] Ensure `claim_summary` is visible-summary text, not chain-of-thought.

## 4.2 Review result models

- [ ] Implement `InnerVoiceReviewResult`.
- [ ] Implement `InnerVoiceObjection`.
- [ ] Enforce disposition enum validation.
- [ ] Enforce severity enum validation.
- [ ] Enforce `confidence_adjustment` range from `-1.0` to `0.0`.
- [ ] Ensure `raw_response_summary` is a compact normalized map.

## 4.3 Debate models

- [ ] Implement `InnerVoiceDebateSession`.
- [ ] Implement `InnerVoiceDebateTurn`.
- [ ] Add fields for:
  - [ ] `debate_id`
  - [ ] `stage`
  - [ ] `subject_type`
  - [ ] `subject_id`
  - [ ] `initiated_by`
  - [ ] `max_rounds_configured`
  - [ ] `completed_rounds`
  - [ ] `ended_reason`
  - [ ] `converged`
  - [ ] `arbiter_requested_by`
  - [ ] `arbiter_review_id`
  - [ ] transcript artifact linkage
- [ ] Add turn-level fields for:
  - [ ] `round_index`
  - [ ] `turn_index`
  - [ ] `speaker`
  - [ ] `turn_type`
  - [ ] `message_text`
  - [ ] `cited_evidence_ids`
  - [ ] `disposition_signal`
  - [ ] `request_arbiter`
  - [ ] `created_at`

## 4.4 Arbiter models

- [ ] Implement `ArbiterResolutionRequest`.
- [ ] Implement `ArbiterResolutionResult`.
- [ ] Add input fields for:
  - [ ] `arbiter_review_id`
  - [ ] `debate_id`
  - [ ] `stage`
  - [ ] `subject_type`
  - [ ] `subject_id`
  - [ ] `openclaw_review_id`
  - [ ] `inner_voice_review_id`
  - [ ] `openclaw_position_summary`
  - [ ] `inner_voice_position_summary`
  - [ ] `disagreement_summary`
  - [ ] `transcript_archive_ids`
  - [ ] `transcript_summary`
  - [ ] `evidence_summary`
  - [ ] `constraints_summary`
  - [ ] `policy_summary`
  - [ ] `tos_summary`
  - [ ] `budget_summary`
  - [ ] `resolution_goal`
- [ ] Add output fields for:
  - [ ] `final_resolution`
  - [ ] `prevailing_side`
  - [ ] `resolution_summary`
  - [ ] `rationale_summary`
  - [ ] `required_followups`
  - [ ] `unresolved_risks`
  - [ ] `raw_response_summary`
  - [ ] artifact linkage

---

# 5. P0 - Implement prompt construction and sanitization

## 5.1 Inner voice prompt rendering

- [ ] Implement deterministic prompt field ordering.
- [ ] Implement bounded text size handling.
- [ ] Implement explicit truncation markers.
- [ ] Implement stage-specific fixed-in-code prompt fragments for:
  - [ ] `opportunity_ranking`
  - [ ] `tos_legal_check`
  - [ ] `budget_planning`
  - [ ] `pre_execution`
  - [ ] `post_review`
- [ ] Implement shared core challenger instructions.

## 5.2 Evidence preparation

- [ ] Implement deterministic evidence ordering.
- [ ] Implement evidence deduplication by URL/archive ID.
- [ ] Implement `max_evidence_items`.
- [ ] Implement `max_chars_per_evidence`.
- [ ] Implement stale-evidence labelling before prompt construction.
- [ ] Ensure raw HTML, screenshots, and attachments are summarized, not inlined.

## 5.3 Arbiter prompt rendering

- [ ] Implement Arbiter prompt construction from structured disagreement context.
- [ ] Ensure the Arbiter sees:
  - [ ] both sides' visible positions
  - [ ] disagreement summary
  - [ ] transcript summary or bounded transcript content
  - [ ] evidence summaries
  - [ ] constraints/policy/TOS/budget summaries where relevant
- [ ] Ensure the Arbiter prompt clarifies whether escalation came from max rounds or a request.

## 5.4 Secret scanning and sanitization

- [ ] Implement secret scanning for prompt archival.
- [ ] Implement secret scanning for raw response archival.
- [ ] Implement secret scanning for debate transcript archival.
- [ ] Redact or hash:
  - [ ] API keys
  - [ ] bearer tokens
  - [ ] wallet-sensitive metadata
  - [ ] disallowed email/credential data
  - [ ] oversized copied document chunks
- [ ] Implement deterministic placeholder artifacts when raw text cannot be safely retained.

---

# 6. P0 - Implement inner voice plugin service

## 6.1 Core service behavior

- [ ] Implement service entrypoint for `review()` / `generate_critique()`.
- [ ] Load config and choose exactly one configured provider.
- [ ] Build normalized prompt request.
- [ ] Call provider adapter.
- [ ] Parse returned JSON.
- [ ] Validate against `InnerVoiceReviewResult`.
- [ ] Return normalized persistence payloads plus structured result.

## 6.2 Failure behavior

- [ ] Detect and classify:
  - [ ] provider unavailable
  - [ ] timeout
  - [ ] invalid auth
  - [ ] malformed provider output
  - [ ] schema validation failure
  - [ ] prompt too large
  - [ ] required stage invocation missing
- [ ] Produce explicit structured failure objects.
- [ ] Ensure required-path failures resolve fail-closed.
- [ ] Ensure optional-path failures remain auditable when `persist_failures=True`.

## 6.3 Persistence payload shaping

- [ ] Return archive payloads for:
  - [ ] sanitized prompt summary
  - [ ] raw prompt if allowed
  - [ ] sanitized response summary
  - [ ] raw response if allowed
- [ ] Return ledger-ready payload for `INNER_VOICE_REVIEW`.
- [ ] Include artifact linkage fields in the result.

---

# 7. P0 - Implement debate-loop orchestration

## 7.1 Debate eligibility and triggering

- [ ] Decide where in orchestration debate mode is entered.
- [ ] Trigger debate only on configured stages.
- [ ] Trigger debate only when disagreement handling is relevant for that stage.
- [ ] Respect `max_debate_rounds` from config.

## 7.2 Debate round execution

- [ ] Build the initial OpenClaw position summary for debate use.
- [ ] Build the first inner voice objection pass.
- [ ] Implement bounded round execution.
- [ ] Ensure each round normally contains:
  - [ ] one OpenClaw turn
  - [ ] one inner voice turn
- [ ] Allow early termination on convergence.
- [ ] Allow explicit `request_arbiter` from either side.

## 7.3 Convergence evaluation

- [ ] Implement structured convergence checks.
- [ ] Determine convergence by:
  - [ ] matching disposition
  - [ ] no unresolved `high` or `block` objections
  - [ ] no active Arbiter request
- [ ] Avoid naive plain-text matching as the convergence criterion.

## 7.4 Debate end-state handling

- [ ] Record `ended_reason = converged` when agreement is reached.
- [ ] Record `ended_reason = max_rounds_reached` when debate ceiling is hit.
- [ ] Record `ended_reason = request_arbiter` when escalation is requested.
- [ ] Record `ended_reason = orchestrator_escalation` when orchestration escalates for safety reasons.
- [ ] Record `ended_reason = failure` when debate cannot complete safely.

---

# 8. P0 - Implement debate transcript persistence

## 8.1 Transcript capture

- [ ] Persist every turn in order.
- [ ] Preserve the exchanged dialogue text after sanitization.
- [ ] Avoid lossy paraphrasing of turn content.
- [ ] Capture round number, turn number, speaker, turn type, and arbiter request flag.
- [ ] Capture cited evidence references.

## 8.2 Transcript artifact creation

- [ ] Archive debate transcript through `receipt_and_evidence_archiver`.
- [ ] Archive a debate summary artifact.
- [ ] Support raw transcript archival when safe and configured.
- [ ] Support sanitized transcript archival when raw text is not safe.

## 8.3 Debate ledger linkage

- [ ] Create ledger-linked `INNER_VOICE_DEBATE` records.
- [ ] Link debate records to:
  - [ ] subject
  - [ ] stage
  - [ ] inner voice review IDs
  - [ ] transcript artifact IDs
  - [ ] later Arbiter record if invoked

## 8.4 Transcript audit UX

- [ ] Ensure an operator can reconstruct the debate round by round from persisted records.
- [ ] Ensure transcript records clearly distinguish:
  - [ ] OpenClaw turns
  - [ ] inner voice turns
  - [ ] arbiter request turns
  - [ ] resolution notes
- [ ] Ensure the system never labels the transcript as hidden internal reasoning.

---

# 9. P0 - Implement Arbiter service

## 9.1 Arbiter invocation policy

- [ ] Invoke Arbiter when:
  - [ ] `max_debate_rounds` is reached without agreement
  - [ ] either OpenClaw or inner voice requests Arbiter resolution
- [ ] Ensure Arbiter is treated as required, not optional, in the debate-resolution path.
- [ ] Ensure one Arbiter pass per debate session in v1.

## 9.2 Arbiter request building

- [ ] Build `ArbiterResolutionRequest` from:
  - [ ] debate session metadata
  - [ ] OpenClaw position summary
  - [ ] inner voice position summary
  - [ ] disagreement summary
  - [ ] transcript summary / artifacts
  - [ ] evidence summaries
  - [ ] constraints and stage summaries
- [ ] Ensure request size stays within configured bounds.

## 9.3 Arbiter provider execution

- [ ] Select Arbiter provider/model from Arbiter config.
- [ ] Allow provider/model to differ from OpenClaw and inner voice.
- [ ] Apply the same direct-adapter, no-LiteLLM rules.
- [ ] Use lower temperature and structured JSON output.

## 9.4 Arbiter response handling

- [ ] Parse returned JSON.
- [ ] Validate against `ArbiterResolutionResult`.
- [ ] Enforce final-resolution enum constraints.
- [ ] Normalize compact `raw_response_summary`.

## 9.5 Arbiter finality rules

- [ ] Treat Arbiter resolution as final among the LLM participants for the debate session.
- [ ] Do not rerun Arbiter on the same debate session in v1.
- [ ] Ensure Arbiter result ends further OpenClaw-versus-inner-voice debate for that session.
- [ ] Ensure deterministic policy still outranks Arbiter output.

## 9.6 Arbiter failure handling

- [ ] Classify Arbiter provider/network/malformed-output failures.
- [ ] Ensure required Arbiter failure resolves workflow to `needs_review`.
- [ ] Archive sanitized request summary on Arbiter failure.
- [ ] Persist `ARBITER_REVIEW` failure records with explicit failure fields.

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
- [ ] Preserve audit metadata:
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
- [ ] Test prompt-too-large path.
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
- [ ] Update `docs/OPENCLAW_MONEYBOT_ARCHITECTURE.md` with:
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

- [ ] Inner voice critique path works with schema validation and fail-closed behavior.
- [ ] Debate loop is bounded by config and fully auditable.
- [ ] Transcript artifacts preserve exchanged dialogue safely.
- [ ] Arbiter is invoked on max-round or explicit-request escalation.
- [ ] Arbiter result is final for the v1 debate session.
- [ ] Deterministic policy remains the ultimate authority.
- [ ] Ledger and evidence linkage are complete for review, debate, and Arbiter records.
- [ ] Unit, integration, mypy, ruff, and pytest all pass.
