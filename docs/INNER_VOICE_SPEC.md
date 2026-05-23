# Inner Voice Plugin Specification

## 1. Purpose

This document specifies a new **inner voice** capability for OpenClaw MoneyBot.

The inner voice is a **second-pass challenger** that reviews the main model's proposed
conclusions, plans, assumptions, and evidence and returns a structured critique.

It is intended to:

- challenge weak assumptions
- identify missing evidence
- identify stale or contradictory information
- surface overlooked policy, legal, budget, or operational risks
- recommend additional checks before irreversible steps

It is **not** intended to:

- become a second autonomous decision-maker
- replace `moneybot_policy_guard`
- replace `tos_legal_checker`
- replace `budget_and_roi_planner`
- execute tools or perform side effects directly

The inner voice should be implemented as a **plugin** with a tightly constrained interface.

## 2. Design intent

OpenClaw MoneyBot already uses a primary reasoning model. The goal of the inner voice is
to introduce a formalized dissent/rebuttal pass rather than a free-form multi-agent debate.

The correct mental model is:

- **main model** proposes
- **inner voice plugin** challenges
- **deterministic skills and workflow gates** decide what happens next

This keeps the architecture auditable and bounded.

## 3. Naming

The operator-facing concept is **Inner Voice**.

The implementation name should be:

- `inner_voice_plugin`

Alternative acceptable implementation names:

- `challenger_llm_plugin`
- `critical_review_plugin`

For consistency with the operator request, this document uses **inner voice plugin**.

## 4. Architecture position

The inner voice is a **governed plugin**.

It should sit in the existing layered architecture as follows:

```text
Local LLM(s)
  ↓
OpenClaw orchestration
  ↓
Narrow skills
  ↓
Deterministic validators and schemas
  ↓
inner_voice_plugin
  ↓
Ledger / evidence archive
```

Important constraints:

- the plugin is **advisory**
- the plugin is **read-only**
- the plugin must not call wallet, email, browser, shell, or external side-effect tools
- the plugin may only produce structured critique outputs

### 4.1 Runtime placement and persistence path

To stay consistent with the project architecture, the inner voice should be called as a
**local helper plugin** by orchestration, but it must not bypass the existing archive and
ledger boundaries.

The required runtime path is:

```text
stage result
  -> orchestrator builds InnerVoiceReviewRequest
  -> inner_voice_plugin calls configured LLM provider
  -> inner_voice_plugin returns normalized critique + persistence payloads
  -> receipt_and_evidence_archiver stores prompt/response artifacts
  -> ledger_skill or ledger_api records INNER_VOICE_REVIEW
  -> orchestrator applies deterministic stage policy
```

This means:

- the plugin owns provider interaction and response normalization
- orchestration owns stage selection and policy interpretation
- approved archive and ledger components own durable persistence

## 5. Relationship to current project assumptions

The current project specification and deployment assumptions are explicitly **local-LLM
first** and say the v1 project should not depend on hosted APIs such as OpenAI.

This new spec intentionally expands the possible provider set to include:

- OpenAI API
- Ollama
- llama-server

This creates a distinction:

### v1-safe deployment assumption

- prefer **local-only providers**
- use **Ollama** or **llama-server**
- keep the inner voice optional and disabled by default

### post-v1 or operator-overridden deployment assumption

- allow **OpenAI API** as an optional provider
- require explicit operator opt-in
- document that this departs from the original local-only deployment assumption

Therefore:

- the inner voice plugin may support OpenAI
- but OpenAI usage should be treated as an **explicit operator policy choice**
- and should not silently become the default

## 6. High-level requirements

The plugin must:

1. accept a structured critique request
2. call one configured LLM provider
3. return a schema-validated critique response
4. return archive payloads so prompt/response artifacts can be stored through
   `receipt_and_evidence_archiver`
5. return ledger-ready data so the result can be recorded through `ledger_skill` or
   `ledger_api`
6. fail closed on malformed outputs or policy-significant failures

The plugin must not:

1. execute external actions
2. mutate canonical plan objects directly
3. bypass deterministic workflow gates
4. receive secrets beyond the provider credential needed for the chosen backend

## 7. Plugin responsibilities

The plugin is responsible for:

- structured critique generation
- highlighting weak assumptions
- identifying missing evidence
- identifying stale evidence risks
- identifying contradictory evidence risks
- highlighting overlooked constraints
- suggesting follow-up checks
- providing a recommended confidence adjustment

The plugin is not responsible for:

- final allow/block decisions
- direct legal conclusions
- direct budget approval
- direct experiment approval
- direct tool use

## 8. Invocation points

The operator should be able to configure when the plugin runs.

Recommended invocation points:

1. after candidate opportunity ranking
2. after `tos_legal_checker`
3. after `budget_and_roi_planner`
4. before execution-adjacent steps
5. after `experiment_reviewer` when extracting lessons

### Recommended default policy

In a cautious rollout, invoke the inner voice:

- for medium-risk or high-risk opportunities
- for any plan involving spend
- for low-confidence or ambiguous decisions
- for opportunities with incomplete or stale evidence

### Optional later policy

Allow operator configuration such as:

- run always
- run only on high-risk paths
- run only above a spend threshold
- run only when confidence is below a threshold
- run only before irreversible actions

## 9. Advisory vs blocking behavior

The plugin itself should remain **advisory**, but the workflow may treat certain outputs as
blocking conditions.

Recommended semantics:

- the plugin returns `recommended_disposition`
- orchestration interprets the result according to stage policy

Allowed dispositions:

- `proceed`
- `proceed_with_followups`
- `needs_review`
- `block_pending_checks`

Recommended v1-safe rule:

- inner voice can force **`needs_review`**
- inner voice should not directly force an irreversible `allow`

## 10. Provider support

The plugin must support three provider families:

1. OpenAI API
2. Ollama
3. llama-server

### 10.1 OpenAI API

Purpose:

- optional hosted challenger model

Requirements:

- API key via environment variable
- model name configurable
- base URL configurable for compatibility if needed
- explicit operator opt-in

### 10.2 Ollama

Purpose:

- local-first challenger runtime

Requirements:

- local or controlled base URL
- model name configurable
- health check support

### 10.3 llama-server

Purpose:

- local OpenAI-compatible inference endpoint

Requirements:

- local or controlled base URL
- model name configurable
- explicit compatibility mode if output formatting differs

## 11. Common provider abstraction

All providers must be normalized behind the same internal contract.

Connection model:

- the plugin connects to each provider through **direct provider-specific adapters**
- OpenAI is called through its HTTPS API directly
- Ollama is called through its local HTTP API directly
- llama-server is called through its OpenAI-compatible HTTP API directly
- the implementation should use the project's normal HTTP client stack directly rather than an
  LLM gateway or aggregation layer

Explicit non-requirement:

- do **not** use LiteLLM for inner voice provider access
- do **not** add a generic third-party LLM routing proxy between the plugin and the configured
  provider

Rationale:

- direct adapters keep the trust boundary smaller
- direct adapters make request/response behavior easier to audit
- direct adapters reduce the chance of hidden retries, silent fallbacks, implicit model
  routing, or accidental credential exposure through an extra abstraction layer

Suggested interface:

```text
generate_critique(request: InnerVoicePromptRequest) -> InnerVoiceRawResponse
health() -> ProviderHealthResult
```

Every provider adapter should expose:

- `provider_name`
- `base_url`
- `model_name`
- `timeout_seconds`
- `max_output_tokens`
- `supports_json_mode`
- `supports_system_prompt`

### 11.1 Normalized provider request contract

All adapters should accept the same normalized prompt envelope:

```text
InnerVoicePromptRequest
  request_id: str
  provider: ProviderName
  model_name: str
  system_prompt: str
  user_prompt: str
  response_schema_json: dict
  temperature: float
  top_p: float | None
  max_output_tokens: int
  timeout_seconds: int
```

Adapter rules:

- prompts are fully rendered before the adapter call
- adapters do not add provider-specific hidden instructions beyond minimal transport needs
- adapters must request one structured JSON object response
- adapters must return the raw response text, parsed JSON when available, finish reason, and
  token usage metadata if the provider exposes it
- adapters must be implemented in-repo for the supported provider families rather than
  delegating through LiteLLM

### 11.2 Normalized provider response contract

Every adapter must return:

```text
InnerVoiceRawResponse
  provider: ProviderName
  model_name: str
  response_text: str
  parsed_json: dict | None
  finish_reason: str | None
  prompt_tokens: int | None
  completion_tokens: int | None
  raw_payload: dict
```

Normalization rules:

- success requires exactly one top-level JSON object
- leading prose, trailing prose, markdown fences, or multiple JSON objects are malformed
- partial JSON or truncated JSON is malformed
- if the provider returns valid JSON that fails schema validation, treat it as a structured
  failure rather than best-effort coercion

### 11.3 Provider-family transport rules

#### OpenAI API

- use a responses/chat-completions path that can request a strict JSON object
- if strict JSON mode is unavailable for the selected endpoint/model, configuration is invalid
- `allow_hosted_provider` must be `true` before initialization succeeds

#### Ollama

- use the chat endpoint with JSON output mode when supported
- if schema-aware JSON output is unavailable, allow plain JSON mode only
- any non-JSON assistant text is malformed output

#### llama-server

- treat llama-server as an OpenAI-compatible endpoint
- require OpenAI-style JSON object output support for the selected runtime mode
- if compatibility quirks require post-processing beyond trimming whitespace, the adapter must
  document that behavior explicitly in code and tests

## 12. Configuration specification

The plugin should be disabled by default.

## 12.1 Top-level config block

Suggested config:

```yaml
inner_voice:
  enabled: false
  provider: "ollama"
  model_name: "llama3.1:8b"
  base_url: "http://127.0.0.1:11434"
  api_key_env_var: ""
  allow_non_local_provider: false
  timeout_seconds: 30
  temperature: 0.2
  top_p: 0.9
  max_output_tokens: 1200
  max_input_chars: 24000
  max_objections: 8
  max_evidence_items: 12
  max_chars_per_evidence: 1200
  archive_raw_prompt: true
  archive_raw_response: true
  archive_redaction_mode: "sanitize"
  persist_failures: true
  max_debate_rounds: 2
  archive_debate_transcript: true
  archive_debate_turn_metadata: true
  invocation_policy: "risk_based"
  run_after_stages:
    - "tos_legal_checker"
    - "budget_and_roi_planner"
    - "pre_execution"
  require_for_spend: true
  require_for_irreversible_actions: true
  low_confidence_threshold: 0.65
  stale_evidence_days: 30
  allow_hosted_provider: false

arbiter:
  provider: "openai"
  model_name: "gpt-4.1"
  base_url: "https://api.openai.com/v1"
  api_key_env_var: "OPENAI_API_KEY"
  allow_non_local_provider: true
  timeout_seconds: 45
  temperature: 0.1
  top_p: 0.9
  max_output_tokens: 1600
  max_input_chars: 32000
  archive_raw_prompt: true
  archive_raw_response: true
  archive_redaction_mode: "sanitize"
  persist_failures: true
  allow_hosted_provider: true
```

## 12.2 Field meanings

- `enabled`
  - master gate
- `provider`
  - one of `openai`, `ollama`, `llama_server`
- `model_name`
  - provider model identifier
- `base_url`
  - provider endpoint root
- `api_key_env_var`
  - environment variable for hosted provider auth
- `allow_non_local_provider`
  - must be true before a local-provider family may use a non-local base URL
- `timeout_seconds`
  - request timeout
- `temperature`
  - low by default to keep critique stable
- `top_p`
  - optional sampling control
- `max_output_tokens`
  - response bound
- `max_input_chars`
  - protects prompt size
- `max_objections`
  - bounds critique breadth
- `max_evidence_items`
  - maximum number of evidence summaries included in the prompt
- `max_chars_per_evidence`
  - per-evidence summary truncation bound
- `archive_raw_prompt`
  - whether to archive exact prompt text
- `archive_raw_response`
  - whether to archive raw provider output
- `archive_redaction_mode`
  - one of `sanitize`, `hash_sensitive_fields`, `disabled`
- `persist_failures`
  - whether failed required or optional invocations still create archive and ledger events
- `max_debate_rounds`
  - maximum number of OpenClaw-versus-Inner-Voice debate rounds before orchestration must stop
    the exchange or escalate
- `archive_debate_transcript`
  - whether the exchanged debate dialogue is archived as a transcript artifact
- `archive_debate_turn_metadata`
  - whether per-turn speaker, round, request-for-arbiter, and disposition metadata is persisted
- `invocation_policy`
  - how runtime decides when to call the plugin
- `run_after_stages`
  - workflow checkpoints
- `require_for_spend`
  - whether spend-related paths require an inner-voice result
- `require_for_irreversible_actions`
  - whether other irreversible steps require the plugin
- `low_confidence_threshold`
  - trigger threshold for uncertain plans
- `stale_evidence_days`
  - threshold used when flagging stale evidence
- `allow_hosted_provider`
  - must be true before `openai` is allowed

### 12.3 Arbiter configuration rules

The Arbiter is a required escalation component for debate resolution rather than an optional
feature flag.

Requirements:

- there is **no** separate `enabled` flag for the Arbiter in v1
- if debate mode exists, Arbiter configuration must exist
- the Arbiter may use a different provider family and model than both OpenClaw and the main
  inner voice
- the Arbiter should use the same direct-adapter approach as the inner voice and must not use
  LiteLLM
- Arbiter configuration should be explicit because it may use a more expensive model or a hosted
  provider

Arbiter fields mirror the inner-voice provider fields where applicable:

- `provider`
- `model_name`
- `base_url`
- `api_key_env_var`
- `allow_non_local_provider`
- `timeout_seconds`
- `temperature`
- `top_p`
- `max_output_tokens`
- `max_input_chars`
- `archive_raw_prompt`
- `archive_raw_response`
- `archive_redaction_mode`
- `persist_failures`
- `allow_hosted_provider`

### 12.4 Configuration edge rules

- v1 supports exactly one active provider configuration at a time
- `provider == openai` requires `allow_hosted_provider == true`
- `provider in {ollama, llama_server}` should default to loopback or another explicitly
  controlled local network address
- if `provider in {ollama, llama_server}` and the URL is not loopback or a Unix socket proxy,
  `allow_non_local_provider` must be true
- empty `api_key_env_var` is invalid when `provider == openai`
- `archive_raw_prompt` and `archive_raw_response` may be disabled only if a sanitized summary
  is still archived
- if debate mode is enabled, `max_debate_rounds` must be explicitly configured and must be at
  least `1`
- if debate mode is enabled, `archive_debate_transcript` should default to `true` for auditability
- Arbiter configuration is required even though there is no Arbiter `enabled` flag
- Arbiter provider/model may differ from inner voice provider/model
- if Arbiter uses `openai`, `allow_hosted_provider` for the Arbiter must be `true`
- if Arbiter uses `ollama` or `llama_server`, the same local-network restrictions apply unless
  `allow_non_local_provider == true`

## 13. Provider-specific config notes

No provider family should have a hard-coded default model in v1.

Requirements:

- `model_name` must be explicitly configured by the operator
- documentation may show examples, but examples are not defaults
- initialization should fail if the plugin is enabled and `model_name` is empty
- this avoids silently selecting a model whose cost, quality, or safety profile was not
  intentionally chosen

### 13.1 OpenAI config example

```yaml
inner_voice:
  enabled: false
  provider: "openai"
  model_name: "gpt-4.1"
  base_url: "https://api.openai.com/v1"
  api_key_env_var: "OPENAI_API_KEY"
  allow_hosted_provider: true
```

### 13.2 Ollama config example

```yaml
inner_voice:
  enabled: false
  provider: "ollama"
  model_name: "llama3.1:8b"
  base_url: "http://127.0.0.1:11434"
```

### 13.3 llama-server config example

```yaml
inner_voice:
  enabled: false
  provider: "llama_server"
  model_name: "meta-llama-3.1-8b-instruct"
  base_url: "http://127.0.0.1:8080/v1"
```

## 14. Input schema

The plugin should receive a narrow, structured request.

Suggested request model:

```text
InnerVoiceReviewRequest
  review_id: str
  stage: str
  subject_type: str
  subject_id: str
  claim_summary: str
  structured_context: dict
  evidence_summary: list[EvidenceSummary]
  constraints_summary: list[str]
  policy_summary: str | None
  tos_summary: str | None
  budget_summary: str | None
  review_goal: str
  max_objections: int
```

### 14.1 Canonical enums and field constraints

The following values should be fixed rather than left open-ended in implementation:

```text
ProviderName
  openai
  ollama
  llama_server

InnerVoiceStage
  opportunity_ranking
  tos_legal_check
  budget_planning
  pre_execution
  post_review

InnerVoiceSubjectType
  opportunity
  experiment_plan
  spend_request
  execution_step
  experiment_review

EvidenceType
  opportunity_snapshot
  rules_snapshot
  terms_snapshot
  policy_result
  tos_result
  budget_plan
  market_data
  receipt
  review_result
  other
```

Field rules:

- `review_id` must be globally unique per invocation
- `claim_summary` should be a normalized prose summary, not raw model chain-of-thought
- `structured_context` must contain only bounded, schema-friendly values
- `max_objections` must be between `1` and the configured maximum
- `captured_at` must be ISO 8601 UTC

### Suggested evidence summary shape

```text
EvidenceSummary
  evidence_id: str
  evidence_type: str
  source_url: str | None
  captured_at: str
  summary: str
  freshness_hint: str | None
```

### Input rules

- no secrets in prompt payloads
- no wallet secrets
- no personal credentials
- no raw private keys
- no unbounded raw documents unless explicitly truncated and normalized

### 14.2 Evidence selection and truncation rules

Prompt construction must select evidence deterministically in this order:

1. policy and TOS summaries relevant to the current stage
2. budget and spend summaries if money could move
3. the most recent source snapshots for the subject
4. contradictory or stale evidence markers
5. at most `max_evidence_items` normalized evidence summaries

Per-item rules:

- each evidence summary is truncated to `max_chars_per_evidence`
- truncation must append an explicit marker such as `[TRUNCATED]`
- duplicate evidence URLs or duplicate archive IDs are deduplicated before prompting
- raw HTML, screenshots, and attachments are never inlined directly; only normalized summaries
  and identifiers are included
- stale evidence labels are added before prompting rather than left for the model to infer

### 14.3 Arbiter input schema

The Arbiter receives a structured disagreement-resolution request rather than the raw internal
state of either model.

Suggested request model:

```text
ArbiterResolutionRequest
  arbiter_review_id: str
  debate_id: str
  stage: InnerVoiceStage
  subject_type: InnerVoiceSubjectType
  subject_id: str
  openclaw_review_id: str | None
  inner_voice_review_id: str | None
  openclaw_position_summary: str
  inner_voice_position_summary: str
  disagreement_summary: str
  transcript_archive_ids: list[str]
  transcript_summary: str
  evidence_summary: list[EvidenceSummary]
  constraints_summary: list[str]
  policy_summary: str | None
  tos_summary: str | None
  budget_summary: str | None
  resolution_goal: str
```

Arbiter input rules:

- the Arbiter reviews the disagreement context, not hidden chain-of-thought
- it should receive both sides' visible positions plus the debate transcript summary
- it may receive transcript artifact references or sanitized transcript text within configured
  bounds
- the request must make clear whether escalation was caused by `max_debate_rounds` or a
  `request_arbiter` turn

## 15. Output schema

The plugin must return a schema-validated structured response.

Suggested response model:

```text
InnerVoiceReviewResult
  review_id: str
  provider: str
  model_name: str
  stage: str
  subject_type: str
  subject_id: str
  overall_assessment: str
  recommended_disposition: str
  confidence_adjustment: float | None
  objections: list[InnerVoiceObjection]
  missing_evidence: list[str]
  stale_information_risks: list[str]
  overlooked_constraints: list[str]
  counterarguments: list[str]
  recommended_followups: list[str]
  raw_response_summary: dict
  evidence_archive_ids: list[str]
  ledger_record: LedgerRecord
```

### 15.1 Final typing decisions

The implementation should lock in the following additional rules:

- `recommended_disposition` is required and must use the fixed enum below
- `confidence_adjustment` is numeric only and bounded from `-1.0` to `0.0`
- the challenger should not positively increase confidence; it only reduces confidence or
  leaves it unchanged
- `raw_response_summary` must be a small normalized map, not the full provider payload
- `ledger_record` is produced by governed persistence code, not by the LLM

Suggested objection model:

```text
InnerVoiceObjection
  title: str
  severity: str
  reason: str
  evidence_basis: str | None
  suggested_resolution: str | None
```

### Severity values

- `low`
- `medium`
- `high`
- `block`

### Recommended disposition values

- `proceed`
- `proceed_with_followups`
- `needs_review`
- `block_pending_checks`

### 15.2 Arbiter output schema

Suggested result model:

```text
ArbiterResolutionResult
  arbiter_review_id: str
  debate_id: str
  provider: ProviderName
  model_name: str
  stage: InnerVoiceStage
  subject_type: InnerVoiceSubjectType
  subject_id: str
  final_resolution: str
  prevailing_side: str
  resolution_summary: str
  rationale_summary: str
  required_followups: list[str]
  unresolved_risks: list[str]
  raw_response_summary: dict
  evidence_archive_ids: list[str]
  ledger_record: LedgerRecord
```

Suggested Arbiter enums:

```text
ArbiterFinalResolution
  adopt_openclaw
  adopt_inner_voice
  proceed_with_followups
  needs_review
  block_pending_checks

ArbiterPrevailingSide
  openclaw
  inner_voice
  mixed
  neither
```

Arbiter output rules:

- the Arbiter resolves the disagreement between OpenClaw and the inner voice
- the Arbiter result is final among the LLM participants for that debate session
- the Arbiter may require follow-up actions or preserve `needs_review`
- the Arbiter may not override deterministic policy, legal gates, budget caps, ledger
  requirements, or wallet controls
- `raw_response_summary` should remain a normalized summary rather than a full provider payload

## 16. Prompt policy

The prompt should frame the model as a **skeptical reviewer**, not a planner.

Required behavioral instructions:

- challenge assumptions
- do not invent facts
- distinguish missing evidence from contrary evidence
- prefer concise, concrete objections
- fail conservative on ambiguity
- do not propose forbidden actions
- do not override policy rules
- do not ask for secrets

Suggested system framing:

```text
You are the inner voice of a constrained, audit-heavy experiment runner.
Your job is to identify weaknesses, overlooked risks, stale evidence, and unsupported
conclusions. You do not approve actions. You do not execute tools. You return only
structured critique.
```

## 17. Prompt construction rules

Prompt building should be deterministic:

- fixed field order
- bounded text length
- explicit truncation markers
- normalized timestamps
- normalized evidence summaries

Do not:

- dump raw large artifacts blindly
- include entire HTML pages without summarization
- include secrets or credentials

### 17.1 Per-stage prompt templates

The phrase "per-stage prompts fixed in code or configurable" refers to how the prompt text is
managed for different workflow stages such as `tos_legal_check`, `budget_planning`, and
`pre_execution`.

The likely prompt structure is:

- one shared core prompt that always defines the challenger role and output rules
- one smaller stage-specific prompt fragment that emphasizes what to challenge for that stage

Example:

- `tos_legal_check` prompt fragment emphasizes missing rules, eligibility, contradictions, and
  ambiguous terms
- `budget_planning` prompt fragment emphasizes downside risk, hidden costs, and unsupported ROI
  assumptions
- `pre_execution` prompt fragment emphasizes irreversibility, missing approvals, and stale
  evidence

Recommended v1 rule:

- keep per-stage prompt templates **fixed in code**
- version them with normal source control
- do not expose prompt-template editing in operator config for v1

Rationale:

- fixed prompts are easier to audit
- fixed prompts are easier to test
- fixed prompts reduce configuration drift and prompt-injection-like operator mistakes
- prompt customization can be considered post-v1 if there is a strong operational need

### 17.2 Archive and redaction policy

Prompt and response archival must be explicit and deterministic.

Required rules:

- a sanitized prompt summary is always archived
- a sanitized response summary is always archived
- if `archive_raw_prompt == true`, the raw prompt may be archived only after secret scanning and
  field-level sanitization
- if `archive_raw_response == true`, the raw provider response may be archived only after the
  same sanitization pass
- hosted-provider and local-provider outputs follow the same redaction rules

Minimum sanitization targets:

- API keys
- bearer tokens
- wallet metadata that could reveal secrets
- email addresses or credentials not already part of the approved record set
- copied raw document chunks that exceed configured archive bounds

Required persistence behavior:

- sanitized artifacts must preserve review ID, subject ID, stage, provider, model, and archive
  timestamps
- if raw archival is disabled or blocked by sanitization, store a deterministic placeholder
  noting why raw text was not retained

## 18. Safety requirements

The inner voice plugin must be governed by the same safety rules as the rest of MoneyBot.

Required safeguards:

- disabled by default
- no direct side effects
- no direct wallet, browser, email, or shell access
- no secret-bearing prompts
- schema-validated output
- invalid output fails closed
- provider/network failures become explicit structured failures

## 19. Hosted provider policy

Because OpenAI support changes the original local-only assumption, the plugin must include
an explicit hosted-provider policy.

Recommended rule:

- if `provider == openai` and `allow_hosted_provider != true`, initialization fails

This prevents accidental rollout of a hosted dependency.

## 20. Failure behavior

The plugin should fail explicitly and predictably.

### Failure classes

- provider unavailable
- timeout
- invalid auth
- malformed provider output
- schema validation failure
- prompt too large
- required stage invocation missing

### Recommended handling

- low-risk optional invocation failure -> record failure, continue if policy allows
- spend-path failure -> `needs_review`
- irreversible-action failure -> `needs_review`
- malformed output -> `needs_review`
- provider timeout -> `needs_review`

The plugin must not silently skip itself on required paths.

### 20.1 Failure persistence rules

Failures must still leave an audit trail when `persist_failures == true`.

Required failure record fields:

- `review_id`
- `stage`
- `subject_type`
- `subject_id`
- `provider`
- `model_name`
- `failure_class`
- `failure_message`
- `was_required`
- `resolved_disposition`

Persistence rules:

- required-path failures must create an `INNER_VOICE_REVIEW` ledger record with failure status
- optional-path failures should also create a record unless the operator explicitly disables
  failure persistence
- provider/network failures should archive a sanitized request summary even if no valid model
  output exists
- missing required invocation should be recorded as both a workflow/policy event and an inner
  voice review failure event

## 21. Ledger and evidence requirements

Every invocation must be auditable.

Recommended behavior:

- archive prompt snapshot through `receipt_and_evidence_archiver`
- archive raw provider response or sanitized response through
  `receipt_and_evidence_archiver`
- record a ledger-linked result through `ledger_skill` or `ledger_api`
- link all artifacts to the reviewed subject

Suggested new record type:

- `INNER_VOICE_REVIEW`
- `INNER_VOICE_DEBATE`
- `ARBITER_REVIEW`

Suggested evidence types:

- `inner_voice_prompt`
- `inner_voice_response`
- `inner_voice_failure`
- `inner_voice_debate_transcript`
- `inner_voice_debate_summary`
- `arbiter_prompt`
- `arbiter_response`
- `arbiter_resolution_summary`

### 21.1 Debate logging and transcript requirements

If the workflow allows OpenClaw and the inner voice to debate before escalation or resolution,
that exchange must be logged as a first-class auditable artifact.

Primary requirement:

- the system should archive the **actual exchanged dialogue** of the debate so the operator can
  inspect what each model said
- this means the logged transcript should contain the claims, objections, rebuttals,
  concessions, and arbiter requests that were actually exchanged between models
- this does **not** mean claiming to capture hidden internal reasoning or inaccessible raw
  chain-of-thought

Suggested debate session model:

```text
InnerVoiceDebateSession
  debate_id: str
  stage: InnerVoiceStage
  subject_type: InnerVoiceSubjectType
  subject_id: str
  initiated_by: str
  max_rounds_configured: int
  completed_rounds: int
  ended_reason: str
  converged: bool
  arbiter_requested_by: str | None
  arbiter_review_id: str | None
  transcript_archive_ids: list[str]
  summary_archive_id: str | None
```

Suggested turn model:

```text
InnerVoiceDebateTurn
  debate_id: str
  round_index: int
  turn_index: int
  speaker: str
  turn_type: str
  message_text: str
  cited_evidence_ids: list[str]
  disposition_signal: str | None
  request_arbiter: bool
  created_at: str
```

Canonical debate enums:

```text
DebateSpeaker
  openclaw
  inner_voice

DebateTurnType
  proposal
  objection
  rebuttal
  concession
  request_arbiter
  resolution_note

DebateEndedReason
  converged
  max_rounds_reached
  request_arbiter
  orchestrator_escalation
  failure
```

Transcript logging rules:

- every turn must record `speaker`, `round_index`, `turn_index`, and `message_text`
- `message_text` should preserve the actual exchanged dialogue after sanitization rather than a
  lossy paraphrase
- turns must be persisted in order and remain immutable once written
- if either side requests escalation, that turn must set `request_arbiter = true`
- the debate record must store why the exchange ended and whether an Arbiter was called
- transcript artifacts must link back to `subject_id`, `stage`, and any resulting
  `INNER_VOICE_REVIEW` or Arbiter review record

Privacy and safety rules:

- debate transcript retention follows the same secret-scanning and sanitization rules as prompt
  and response archival
- if raw transcript text cannot be retained safely, store a sanitized transcript plus a
  deterministic placeholder describing the redaction
- do not market the transcript as the models' hidden private thoughts; it is the visible debate
  dialogue that the system exchanged

Operator-facing audit value:

- the operator should be able to read the debate transcript round by round
- the operator should be able to see where positions changed, where evidence was cited, and
  which side asked for arbitration
- the operator should be able to tell whether escalation happened because of unresolved
  disagreement, configured round limits, or an explicit arbiter request

### 21.2 Arbiter persistence requirements

Every Arbiter invocation must be auditable and linked back to the debate it resolved.

Required behavior:

- archive the Arbiter prompt snapshot through `receipt_and_evidence_archiver`
- archive the Arbiter raw response or sanitized response through
  `receipt_and_evidence_archiver`
- record an `ARBITER_REVIEW` ledger-linked record through `ledger_skill` or `ledger_api`
- link the Arbiter record to:
  - `debate_id`
  - `subject_id`
  - `stage`
  - the triggering inner voice review IDs where available
  - debate transcript artifact IDs

Failure behavior:

- if the Arbiter is required and fails, the workflow resolves to `needs_review`
- Arbiter failures must archive a sanitized request summary even when no valid resolution is
  produced
- Arbiter failure records must preserve `debate_id`, `subject_id`, `stage`, `provider`,
  `model_name`, `failure_class`, and `failure_message`

## 22. Staleness handling

The plugin should help identify stale knowledge, but should not be the only mechanism for
staleness enforcement.

Required inputs:

- timestamps on evidence
- timestamps on related summaries where available

Expected output categories:

- stale evidence risk
- missing evidence
- contradictory evidence

Suggested rule:

- if evidence is older than `stale_evidence_days`, the prompt should explicitly label it as
  potentially stale

## 23. Workflow integration expectations

The inner voice should integrate with workflow by producing structured critique, not by
mutating the workflow itself.

Recommended downstream behaviors:

- if objections include `block` severity -> route to `needs_review`
- if `missing_evidence` is non-empty -> schedule follow-up checks
- if `stale_information_risks` is non-empty -> refresh source material
- if `confidence_adjustment` is strongly negative -> reduce downstream confidence

### 23.1 Deterministic stage interpretation matrix

The orchestration layer should apply the critique result using a fixed policy table.

| Stage | Result condition | Required runtime effect |
| --- | --- | --- |
| `opportunity_ranking` | `recommended_disposition = proceed` and no `block` objections | candidate may continue to normal policy/legal flow |
| `opportunity_ranking` | `recommended_disposition in {needs_review, block_pending_checks}` or any `block` objection | candidate is held for review and cannot auto-advance |
| `tos_legal_check` | any `high` or `block` objection, contradictory evidence, or malformed output | route to `needs_review`; do not advance to budget approval automatically |
| `budget_planning` | missing evidence, stale critical evidence, or confidence adjustment `<= -0.35` | require follow-up checks before any spend path |
| `pre_execution` | any failure, any `block` objection, or `recommended_disposition != proceed` | block execution-adjacent transition and route to `needs_review` |
| `post_review` | critique only affects learning/review records | may not retroactively approve prior blocked actions |

### 23.2 Spend and irreversible-action rules

Additional deterministic rules:

- if a path involves spend and `require_for_spend == true`, missing invocation or invocation
  failure resolves to `needs_review`
- if a path is irreversible and `require_for_irreversible_actions == true`, any non-successful
  invocation resolves to `needs_review`
- `proceed` from the inner voice is never sufficient by itself to authorize spend, publish,
  send, submit, or execute
- the inner voice may raise the workflow to `needs_review`, but it may not lower any existing
  `block` or `needs_review` decision from another governed component

### 23.3 Multiple challenger passes

v1 should allow multiple challenger passes for the same subject when the workflow or operator
requests another critique pass.

Examples:

- a second pass after follow-up evidence is gathered
- a second pass at a later stage for the same opportunity or experiment plan
- a retry pass after a prior malformed output or timeout

Required rules:

- each pass gets a unique `review_id`
- each pass links to the same `subject_type` and `subject_id`
- each pass records `pass_index` starting at `1`
- each pass may optionally reference `prior_review_id`
- prior pass records remain immutable and auditable
- a later pass may supersede an earlier recommendation operationally, but it must not overwrite
  prior records
- orchestration must apply the latest valid pass according to stage policy while retaining the
  full review chain

### 23.4 Debate-loop logging expectations

If debate mode is enabled, orchestration should treat the debate as a bounded structured
exchange, not an open-ended chat.

Required behavior:

- the maximum number of rounds must come from config via `max_debate_rounds`
- each round should normally contain one OpenClaw turn and one Inner Voice turn unless the
  exchange terminates early
- if the models converge before the round limit, record `ended_reason = converged`
- if the round limit is reached without convergence, record `ended_reason = max_rounds_reached`
- if either side requests arbitration and the configured escalation policy allows it, record
  `ended_reason = request_arbiter`
- if the orchestrator escalates for safety reasons, record `ended_reason = orchestrator_escalation`
- the transcript must remain linked to any later Arbiter invocation

### 23.5 Arbiter invocation rules

The Arbiter is invoked when a debate must be resolved and the OpenClaw LLM and the main inner
voice have not reached agreement.

The Arbiter must be called when either of the following is true:

1. `max_debate_rounds` is reached and the participants are still not in agreement
2. either OpenClaw or the inner voice explicitly requests Arbiter resolution

Agreement should be evaluated by orchestration using structured outputs rather than informal text
matching.

Suggested convergence criteria:

- both sides reach the same disposition
- no unresolved `high` or `block` objections remain between them
- no side still requests arbitration

Required rules:

- once the Arbiter is called for a debate session, that Arbiter resolution is final for v1
- v1 performs one Arbiter pass per debate session
- v1 does not rerun the Arbiter on the same debate session after resolution
- the Arbiter may use a different provider family or model than the two debating models
- the Arbiter resolves any disagreement between OpenClaw and the inner voice, but only within
  that disagreement-resolution role
- deterministic policy still outranks all LLM outputs, including the Arbiter

### 23.6 Arbiter resolution semantics

The Arbiter is not another debate participant. It is a final disagreement resolver for the
current debate session.

Resolution rules:

- if the Arbiter adopts OpenClaw, orchestration proceeds with the OpenClaw position subject to
  deterministic gates
- if the Arbiter adopts the inner voice, orchestration proceeds with the inner voice position
  subject to deterministic gates
- if the Arbiter returns `proceed_with_followups`, those follow-ups become required workflow work
- if the Arbiter returns `needs_review` or `block_pending_checks`, the workflow must not
  auto-advance
- the Arbiter result replaces further OpenClaw-versus-inner-voice debate for that same v1 debate
  session

## 24. Memory and learning integration

The plugin may later contribute to long-term memory, but only through governed paths.

Allowed future uses:

- archive critique results
- feed critique outcomes into Kuzu/graph memory later
- use review results to refine heuristics

Not allowed:

- writing unvalidated free-form critique directly into canonical memory

## 25. Health checks

The plugin should expose a health model similar to other plugins.

Suggested statuses:

- `ok`
- `missing_api_key`
- `provider_unreachable`
- `misconfigured`
- `disabled`

## 26. Testing requirements

The plugin needs strong offline tests.

### Unit tests

- config validation
- provider adapter request shaping
- provider adapter response parsing
- Arbiter request shaping
- Arbiter response parsing
- malformed output handling
- prompt truncation behavior
- severity/disposition validation

### Integration tests

- run after configured stages
- required-for-spend path blocks on failure
- required-for-irreversible path blocks on failure
- advisory low-risk path can continue if optional
- ledger/evidence linkage is correct
- debate transcript ordering, round counts, and escalation linkage are correct
- Arbiter invocation occurs when max debate rounds are reached without convergence
- Arbiter invocation occurs when either side requests arbitration
- Arbiter result is final for the debate session and is linked to the transcript and review chain
- Arbiter failure on a required resolution path produces `needs_review`

### Fixture approach

- mock provider HTTP responses
- test all providers with transport fixtures
- never require live OpenAI, Ollama, or llama-server in CI

### 26.1 Operational usefulness metrics

The rollout should measure whether the challenger is useful rather than noisy.

Recommended metrics:

- invocation count by stage
- `needs_review` rate by stage
- objection severity distribution
- debate session count by stage
- average completed debate rounds
- arbiter request rate
- arbiter invocation rate
- arbiter prevailing-side distribution
- arbiter failure rate
- follow-up check creation rate
- confirmed issue rate after operator or downstream review
- false-positive rate where critique was dismissed without action
- provider failure rate
- average prompt and response sizes
- average transcript size

## 27. Recommended rollout plan

### Phase 0: spec only

- complete this document
- agree on name and behavior

### Phase 1: local-provider-only implementation

- support `ollama`
- support `llama_server`
- keep `openai` config defined but disabled by policy unless explicitly enabled
- implement the required Arbiter path with one final-resolution pass per debate session

### Phase 2: workflow-gated rollout

- invoke only on selected high-risk stages
- archive all outputs
- measure usefulness and noise

### Phase 3: hosted-provider opt-in

- allow OpenAI only through explicit operator config
- keep local-first as the default

### Phase 4: memory integration

- optionally connect critique outcomes into graph memory or heuristic retention

## 28. Open questions to resolve before implementation

Most critical design questions are resolved above. The remaining implementation-planning
questions are narrower:

1. which concrete data fields should be included in the minimal `raw_response_summary`
2. whether post-v1 should allow operator-configurable prompt templates with guardrails
3. whether post-v1 should support branching review trees beyond a simple linear pass chain
4. whether post-v2 should allow Arbiter reruns only when genuinely new evidence arrives

## 29. Recommended default policy

If implementation starts now, the safest default is:

- plugin disabled by default
- local providers preferred
- OpenAI allowed only with explicit opt-in
- low temperature
- advisory outputs
- fail closed on required stages
- archive prompt and response
- no direct side effects
- use the Arbiter as the required final disagreement resolver after bounded debate

## 30. Summary

The inner voice plugin should be a narrowly-scoped challenger layer that questions the main
model's conclusions without becoming a second uncontrolled agent.

The critical design choices are:

- structured input/output
- provider abstraction
- advisory-only role
- explicit invocation policy
- bounded debate plus required Arbiter resolution
- fail-closed behavior
- full ledger/evidence traceability

If implemented this way, it can improve decision quality and safety without weakening the
project's existing architecture.
