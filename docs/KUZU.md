# Kuzu graph memory for OpenClaw MoneyBot

## Purpose

This document explains how Kuzu should fit into OpenClaw MoneyBot, how to configure it,
and what is in scope for **v1** versus **post-v1**.

The short version is:

- **v1:** Kuzu is **not** part of the running system.
- **post-v1:** Kuzu may be added as an **internal graph memory module/service**.
- SQLite remains the **canonical system of record** unless the architecture is
  deliberately changed later.

Kuzu should not be introduced as a broad autonomous memory layer or as a plugin that the
LLM can mutate directly. If adopted, it should be a tightly controlled internal component
used for graph-style relationship queries over structured, provenance-linked data.

## Why Kuzu

Kuzu is an embedded graph database with:

- a **predefined schema**
- **typed node and relationship properties**
- **on-disk** and **in-memory** modes
- Cypher-style `MATCH` queries
- no server daemon requirement

Relevant Kuzu docs:

- Installation: <https://kuzudb.github.io/docs/installation/>
- Getting started: <https://kuzudb.github.io/docs/get-started/>
- Data types: <https://kuzudb.github.io/docs/cypher/data-types/>
- `MATCH` queries: <https://kuzudb.github.io/docs/cypher/query-clauses/match/>

That makes it a reasonable option if MoneyBot later needs graph traversal without adding a
separate graph server.

## Architecture position

If Kuzu is added later, it should be treated as:

- an **internal graph memory module/service**
- a **derived read model**
- a **rebuildable projection** from SQLite-backed canonical records

It should **not** be treated as:

- the canonical ledger
- a direct replacement for SQLite
- a free-form memory store for arbitrary LLM output
- a general-purpose plugin with unconstrained write access

## v1 status

## In scope for v1

- This document
- design decisions
- rollout planning
- schema ideas
- test strategy
- configuration planning

## Explicitly out of scope for v1

- adding `kuzu` to dependencies
- creating a Kuzu-backed module/service
- adding Kuzu config to `AppConfig`
- writing Kuzu projection code
- storing production data in Kuzu
- querying Kuzu from orchestration or skills
- using Kuzu as the source of truth

## v1 configuration

There is **no live Kuzu configuration in v1**.

That means:

- no `kuzu:` block in the app config
- no Kuzu database path in runtime config
- no migration process
- no maintenance job
- no tests that require Kuzu

If you are working on v1, stop at planning and documentation.

## Post-v1 target design

## Core rule

SQLite remains canonical. Kuzu is populated from SQLite and can be deleted and rebuilt.

## Recommended internal structure

If Kuzu is added later, place it behind a narrow internal module boundary such as:

```text
src/openclaw_moneybot/graph_memory/
  __init__.py
  models.py
  schema.py
  projector.py
  queries.py
  maintenance.py
  service.py
```

Suggested responsibilities:

- `schema.py`
  - open the Kuzu database
  - create node tables
  - create relationship tables
  - manage schema version checks
- `projector.py`
  - read canonical SQLite records
  - build or refresh the graph projection
  - keep writes deterministic
- `queries.py`
  - contain approved Cypher queries
  - return typed outputs only
- `maintenance.py`
  - handle cleanup, retirement, and confidence decay
- `service.py`
  - provide the only interface used elsewhere in the app

## Recommended write policy

Only these layers should write to Kuzu:

1. schema initialization
2. projector
3. maintenance

The LLM, orchestration layer, and regular skills should not write arbitrary graph data
directly.

## Recommended runtime model

The safest initial rollout is:

1. start MoneyBot
2. ensure Kuzu schema exists
3. rebuild the graph from SQLite
4. run approved graph queries
5. run maintenance explicitly, not implicitly

This favors determinism and recoverability over cleverness.

## Post-v1 dependency setup

When you are ready to actually implement Kuzu, use the repo's Python and dependency
standards:

- Python **3.11**
- `uv`

Install the Python client with:

```bash
uv add kuzu
```

Kuzu also has a standalone CLI if you want local inspection during development:

```bash
curl -L -O https://github.com/kuzudb/kuzu/releases/download/v0.11.3/kuzu_cli-linux-x86_64.tar.gz
tar xzf kuzu_cli-linux-x86_64.tar.gz
./kuzu
```

The CLI is optional. The Python client is the relevant integration point for MoneyBot.

## Post-v1 filesystem layout

Keep Kuzu data local and separate from the SQLite ledger:

```text
data/
  moneybot.sqlite3
  graph_memory.kuzu/
archive/
workspace/
```

Recommended path:

- `data/graph_memory.kuzu`

Do not place Kuzu files:

- inside the evidence archive
- inside temp directories
- inside user home dotfiles by default

## Proposed future config block

The following is a **post-v1 proposed config**, not something implemented today:

```yaml
graph_memory:
  enabled: false
  backend: "kuzu"
  database_path: "data/graph_memory.kuzu"
  rebuild_on_startup: true
  projection_mode: "full_rebuild"
  max_query_results: 100
  maintenance_enabled: true
  stale_after_days: 30
  heuristic_decay_days: 90
  archive_before_delete: true
```

### Field intent

- `enabled`
  - gates all graph-memory behavior
- `backend`
  - future-proofing if another backend is ever evaluated
- `database_path`
  - on-disk Kuzu path
- `rebuild_on_startup`
  - whether to rebuild the derived graph during startup
- `projection_mode`
  - start with `full_rebuild`; add incremental modes only later if needed
- `max_query_results`
  - bounds query output size
- `maintenance_enabled`
  - allows explicit cleanup tasks
- `stale_after_days`
  - baseline staleness threshold
- `heuristic_decay_days`
  - when to start decaying low-confidence derived knowledge
- `archive_before_delete`
  - whether cleanup first writes archival summaries back to SQLite before removing graph data

## Recommended v1-to-post-v1 rollout order

### Phase 1: documentation only

- keep this document current
- decide whether Kuzu is worth adding at all
- identify the exact graph queries SQL cannot answer comfortably

### Phase 2: internal module skeleton

- add the dependency
- create the internal module layout
- add tests using in-memory Kuzu
- do not wire the module into runtime behavior yet

### Phase 3: schema and full rebuild projection

- create a small schema
- project from SQLite using a full rebuild
- expose a tiny typed query API

### Phase 4: maintenance and staleness handling

- add confidence decay
- add stale-node retirement
- add explicit maintenance jobs

### Phase 5: incremental refresh, if truly needed

- only after profiling and real demand
- keep full rebuild support permanently as the recovery path

## Recommended first graph schema

Start small. Do not attempt to model everything at once.

### Suggested node tables

- `Opportunity`
- `PolicyDecision`
- `BudgetPlan`
- `ExperimentReview`
- `Counterparty`
- `Heuristic`

### Suggested relationship tables

- `EVALUATED_BY`
- `PLANNED_AS`
- `REVIEWED_AS`
- `INVOLVES_COUNTERPARTY`
- `DERIVED_FROM`
- `CONTRADICTS`
- `RELATED_TO`

### Suggested common node properties

- `id STRING PRIMARY KEY`
- `source_record_id STRING`
- `created_at TIMESTAMP`
- `last_seen_at TIMESTAMP`
- `valid_from TIMESTAMP`
- `valid_to TIMESTAMP`
- `confidence_score DOUBLE`
- `status STRING`

Not every node needs every field, but all derived knowledge should carry enough metadata
for provenance and staleness handling.

## Example future Kuzu schema

This example is illustrative for post-v1 design work:

```python
import kuzu

db = kuzu.Database("data/graph_memory.kuzu")
conn = kuzu.Connection(db)

conn.execute(
    """
    CREATE NODE TABLE Opportunity(
      id STRING PRIMARY KEY,
      status STRING,
      created_at TIMESTAMP,
      last_seen_at TIMESTAMP
    )
    """
)

conn.execute(
    """
    CREATE NODE TABLE Heuristic(
      id STRING PRIMARY KEY,
      body STRING,
      heuristic_type STRING,
      confidence_score DOUBLE,
      valid_from TIMESTAMP,
      valid_to TIMESTAMP,
      source_record_id STRING
    )
    """
)

conn.execute(
    """
    CREATE REL TABLE DERIVED_FROM(
      FROM Heuristic TO Opportunity,
      created_at TIMESTAMP
    )
    """
)
```

This stays aligned with Kuzu's typed schema model and MoneyBot's preference for explicit,
testable contracts.

## Projection strategy

## Recommended first strategy: full rebuild

For post-v1, start with:

- read canonical SQLite records
- delete and rebuild the Kuzu projection
- validate node and relationship counts

Why this is preferred initially:

- simpler to reason about
- easier to test
- easier to recover from bugs
- avoids drift between SQLite and Kuzu

## Incremental projection

Incremental projection can be added later, but only after:

- full rebuild works well
- the update path is profiled
- query latency or startup rebuild time becomes a real issue

## Cleanup and staleness management

Kuzu does not remove stale data automatically for you. MoneyBot must define cleanup rules.

### Recommended post-v1 rules

1. **retire, do not immediately delete**
   - prefer `valid_to` first
2. **decay low-confidence heuristics**
   - especially derived rules based on old experiments
3. **archive before destructive cleanup**
   - if deleting graph-only derived structures, first write archival summaries to SQLite
4. **rebuild as recovery**
   - if cleanup logic goes wrong, delete the Kuzu database and rebuild from SQLite

### Suggested staleness fields

- `last_seen_at`
- `valid_from`
- `valid_to`
- `confidence_score`

### Suggested cleanup cases

- heuristics derived from very old experiments
- relationships tied to expired policy decisions
- outdated counterparty links no longer supported by current evidence

## Query boundary

Do not expose free-form graph queries everywhere in the app.

Instead, create a narrow query API, for example:

- `find_related_opportunities(...)`
- `find_conflicting_heuristics(...)`
- `find_counterparty_risk_paths(...)`
- `find_stale_policy_dependencies(...)`

Each query should:

- have a typed request
- have a typed response
- enforce result limits
- preserve provenance IDs in the output

## Provenance requirements

Every derived graph object should be traceable.

At minimum, keep:

- SQLite source record ID
- related evidence ID if applicable
- creation time
- originating summary/review/experiment ID

Kuzu should help answer relationship questions, not become an unexplained pool of facts.

## Testing plan

When post-v1 implementation begins, add:

### Unit tests

- schema creation
- projection from fixture SQLite data
- query correctness
- staleness retirement rules
- full rebuild idempotence

### Integration tests

- startup rebuild behavior
- query results over realistic fixture data
- maintenance task behavior
- recovery from deleting and rebuilding the graph store

### Test runtime mode

Use **in-memory Kuzu** for most tests:

```python
db = kuzu.Database(":memory:")
```

Kuzu's docs support in-memory mode when the database path is omitted or set to
`""` or `:memory:`.

## Operational guidance

If Kuzu is adopted post-v1:

- keep it local-only
- do not expose it on the network
- do not let external agents write to it
- do not store secrets in graph properties
- keep rebuild tooling simple and documented

## When not to add Kuzu

Do **not** add Kuzu just because "knowledge graph" sounds attractive.

Stay on SQLite only if:

- your real questions are still answerable with SQL
- you do not yet need multi-hop relationship traversal
- the maintenance burden would outweigh the value

MoneyBot does not need a graph database unless graph queries materially improve the system.

## Decision summary

### v1

- do not integrate Kuzu into runtime
- do not add dependency or config
- keep SQLite canonical
- document the intended design

### post-v1

- add Kuzu only as an internal graph memory module/service
- populate it from SQLite
- keep it rebuildable
- expose only bounded, typed graph queries
- implement explicit staleness and cleanup rules
