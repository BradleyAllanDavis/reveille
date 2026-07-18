# Graph Report - reveille  (2026-07-18)

## Corpus Check
- 48 files · ~21,886 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 251 nodes · 426 edges · 27 communities (19 shown, 8 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 36 edges (avg confidence: 0.73)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `aeaca2cf`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- SourceSnapshot
- coordinator.py
- cli.py
- _fixture_snapshots
- run_checks
- test_things.py
- test_evals.py
- test_adapters.py
- make_fixtures.py
- reveille
- reveille
- graphify reference: extra exports and benchmark
- graphify reference: query, path, explain
- history.py
- graphify reference: add a URL and watch a folder
- graphify reference: commit hook and native CLAUDE.md integration
- graphify reference: incremental update and cluster-only
- test_history.py
- graphify reference: GitHub clone and cross-repo merge
- graphify reference: transcribe video and audio
- CLAUDE.md
- CLAUDE.md
- extraction-spec.md
- scheduled-brief.sh

## God Nodes (most connected - your core abstractions)
1. `SourceSnapshot` - 27 edges
2. `run_checks()` - 15 edges
3. `LLMBackend` - 12 edges
4. `What You Must Do When Invoked` - 12 edges
5. `Entity` - 11 edges
6. `_fixture_snapshots()` - 10 edges
7. `cmd_evals()` - 10 edges
8. `compose_offline()` - 10 edges
9. `CheckResult` - 10 edges
10. `Briefing` - 10 edges

## Surprising Connections (you probably didn't know these)
- `snapshots()` --calls--> `_fixture_snapshots()`  [INFERRED]
  tests/test_evals.py → src/reveille/cli.py
- `test_every_degraded_case_scores_below_golden()` --calls--> `score_case()`  [INFERRED]
  tests/test_evals.py → src/reveille/evals/scorecard.py
- `main()` --calls--> `compose_offline()`  [INFERRED]
  scripts/make_fixtures.py → src/reveille/coordinator.py
- `test_resolve_secret_fails_loud_when_neither_set()` --calls--> `_resolve_secret()`  [INFERRED]
  tests/test_cli.py → src/reveille/cli.py
- `test_resolve_secret_prefers_direct_env()` --calls--> `_resolve_secret()`  [INFERRED]
  tests/test_cli.py → src/reveille/cli.py

## Import Cycles
- None detected.

## Communities (27 total, 8 thin omitted)

### Community 0 - "SourceSnapshot"
Cohesion: 0.11
Nodes (27): Entity, One normalized fact from a source (a task, a sensor state, a client, a doc)., SourceSnapshot, fetch(), from_fixture(), from_states(), Any, datetime (+19 more)

### Community 1 - "coordinator.py"
Cohesion: 0.14
Nodes (24): BaseModel, Protocol, RuntimeError, AnalystError, _complete_json(), compose(), compose_offline(), The coordinator: fan-out analysts, fan-in editor.  Two composition paths, same o (+16 more)

### Community 2 - "cli.py"
Cohesion: 0.12
Nodes (27): Namespace, cmd_brief(), cmd_evals(), _env_flag(), gather_snapshots(), main(), CLI: `reveille brief` composes; `reveille evals` scores.  The two subcommands mi, A live credential from an env var, or from running a command named in     anothe (+19 more)

### Community 3 - "_fixture_snapshots"
Cohesion: 0.20
Nodes (12): dump(), main(), Regenerate the golden briefing fixture + its degraded variants.  The golden case, _fixture_snapshots(), analyst_reply(), FakeBackend, Multi-agent path with a fake backend: fan-out/fan-in, JSON repair retry, and the, Replays canned replies; records every prompt for assertions. (+4 more)

### Community 4 - "run_checks"
Cohesion: 0.47
Nodes (10): check_budget(), check_coverage(), check_grounding(), check_hygiene(), check_priorities(), check_schema(), CheckContext, CheckResult (+2 more)

### Community 5 - "test_things.py"
Cohesion: 0.19
Nodes (12): from_database(), date, Path, Things 3 adapter: the local SQLite database -> SourceSnapshot.  Read-only by con, resolve_db_path(), db(), packed(), date (+4 more)

### Community 6 - "test_evals.py"
Cohesion: 0.39
Nodes (7): by_name(), load(), The evals harness must discriminate: golden scores clean, every degraded variant, snapshots(), test_degraded_cases_are_caught(), test_every_degraded_case_scores_below_golden(), test_golden_passes_everything()

### Community 7 - "test_adapters.py"
Cohesion: 0.27
Nodes (7): _fake_urlopen(), kinds(), Raw source payloads map to the normalized snapshot correctly., A urllib.request.urlopen replacement serving canned JSON bodies in     call orde, test_ha_extracts_actionable_states(), test_ha_fetch_sends_bearer_token_and_feeds_from_states(), test_unifi_fetch_hits_health_and_sta_and_unwraps_data()

### Community 8 - "make_fixtures.py"
Cohesion: 0.08
Nodes (24): For /graphify add and --watch, For /graphify query, For the commit hook and native CLAUDE.md integration, For --update and --cluster-only, /graphify, Honesty Rules, Interpreter guard for subcommands, Part A - Structural extraction for code files (+16 more)

### Community 13 - "reveille"
Cohesion: 0.13
Nodes (13): 2026-07-18 — initial build, 2026-07-18 — phase 2: live sources, scheduling, judge history, Decision log, Lineage (what was extracted from where), Architecture, Live sources (optional), Provenance, Quickstart (+5 more)

### Community 14 - "graphify reference: extra exports and benchmark"
Cohesion: 0.22
Nodes (8): graphify reference: extra exports and benchmark, Step 6b - Wiki (only if --wiki flag), Step 7 - Neo4j export (only if --neo4j or --neo4j-push flag), Step 7a - FalkorDB export (only if --falkordb or --falkordb-push flag), Step 7b - SVG export (only if --svg flag), Step 7c - GraphML export (only if --graphml flag), Step 7d - MCP server (only if --mcp flag), Step 8 - Token reduction benchmark (only if total_words > 5000)

### Community 15 - "graphify reference: query, path, explain"
Cohesion: 0.33
Nodes (5): For /graphify explain, For /graphify path, graphify reference: query, path, explain, Step 0 — Constrained query expansion (REQUIRED before traversal), Step 1 — Traversal

### Community 16 - "history.py"
Cohesion: 0.40
Nodes (5): Path, Judge-score history: a local sqlite side-store so editorial-quality trend is vis, Most recent rows for one case, newest first., record(), trend()

### Community 17 - "graphify reference: add a URL and watch a folder"
Cohesion: 0.50
Nodes (3): For /graphify add, For --watch, graphify reference: add a URL and watch a folder

### Community 18 - "graphify reference: commit hook and native CLAUDE.md integration"
Cohesion: 0.50
Nodes (3): For git commit hook, For native CLAUDE.md integration, graphify reference: commit hook and native CLAUDE.md integration

### Community 19 - "graphify reference: incremental update and cluster-only"
Cohesion: 0.50
Nodes (3): For --cluster-only, For --update (incremental re-extraction), graphify reference: incremental update and cluster-only

## Knowledge Gaps
- **56 isolated node(s):** `reveille`, `scheduled-brief.sh script`, `graphify`, `Usage`, `What graphify is for` (+51 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SourceSnapshot` connect `SourceSnapshot` to `coordinator.py`, `cli.py`, `_fixture_snapshots`, `run_checks`, `test_things.py`?**
  _High betweenness centrality (0.117) - this node is a cross-community bridge._
- **Why does `from_database()` connect `test_things.py` to `SourceSnapshot`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `run_checks()` connect `run_checks` to `SourceSnapshot`, `cli.py`, `_fixture_snapshots`, `test_evals.py`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `run_checks()` (e.g. with `test_offline_composer_passes_its_own_evals()` and `test_degraded_cases_are_caught()`) actually correct?**
  _`run_checks()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `reveille`, `scheduled-brief.sh script`, `graphify` to the rest of the system?**
  _56 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `SourceSnapshot` be split into smaller, more focused modules?**
  _Cohesion score 0.10752688172043011 - nodes in this community are weakly interconnected._
- **Should `coordinator.py` be split into smaller, more focused modules?**
  _Cohesion score 0.14112903225806453 - nodes in this community are weakly interconnected._