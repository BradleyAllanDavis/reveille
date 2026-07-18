# Graph Report - .  (2026-07-18)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 142 nodes · 319 edges · 13 communities (12 shown, 1 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 32 edges (avg confidence: 0.72)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b99d908a`
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

## God Nodes (most connected - your core abstractions)
1. `SourceSnapshot` - 27 edges
2. `run_checks()` - 15 edges
3. `LLMBackend` - 12 edges
4. `Entity` - 11 edges
5. `_fixture_snapshots()` - 10 edges
6. `cmd_evals()` - 10 edges
7. `compose_offline()` - 10 edges
8. `CheckResult` - 10 edges
9. `Briefing` - 10 edges
10. `AnalystError` - 9 edges

## Surprising Connections (you probably didn't know these)
- `test_every_degraded_case_scores_below_golden()` --calls--> `score_case()`  [INFERRED]
  tests/test_evals.py → src/reveille/evals/scorecard.py
- `test_classification()` --calls--> `from_database()`  [INFERRED]
  tests/test_things.py → src/reveille/sources/things.py
- `test_opens_read_only()` --calls--> `from_database()`  [INFERRED]
  tests/test_things.py → src/reveille/sources/things.py
- `main()` --calls--> `_fixture_snapshots()`  [INFERRED]
  scripts/make_fixtures.py → src/reveille/cli.py
- `main()` --calls--> `compose_offline()`  [INFERRED]
  scripts/make_fixtures.py → src/reveille/coordinator.py

## Import Cycles
- None detected.

## Communities (13 total, 1 thin omitted)

### Community 0 - "SourceSnapshot"
Cohesion: 0.11
Nodes (28): Entity, Core data contracts.  Two halves, deliberately decoupled so the evals harness ca, One normalized fact from a source (a task, a sensor state, a client, a doc)., SourceSnapshot, fetch(), from_fixture(), from_states(), Any (+20 more)

### Community 1 - "coordinator.py"
Cohesion: 0.15
Nodes (23): BaseModel, Protocol, RuntimeError, AnalystError, _complete_json(), compose(), compose_offline(), The coordinator: fan-out analysts, fan-in editor.  Two composition paths, same o (+15 more)

### Community 2 - "cli.py"
Cohesion: 0.18
Nodes (19): Namespace, cmd_brief(), cmd_evals(), gather_snapshots(), main(), CLI: `reveille brief` composes; `reveille evals` scores.  The two subcommands mi, CaseResult, compare() (+11 more)

### Community 3 - "_fixture_snapshots"
Cohesion: 0.26
Nodes (10): _fixture_snapshots(), analyst_reply(), FakeBackend, Multi-agent path with a fake backend: fan-out/fan-in, JSON repair retry, and the, Replays canned replies; records every prompt for assertions., test_compose_fans_out_and_merges(), test_json_repair_retry(), test_offline_composer_passes_its_own_evals() (+2 more)

### Community 4 - "run_checks"
Cohesion: 0.47
Nodes (10): check_budget(), check_coverage(), check_grounding(), check_hygiene(), check_priorities(), check_schema(), CheckContext, CheckResult (+2 more)

### Community 5 - "test_things.py"
Cohesion: 0.32
Nodes (7): db(), packed(), date, Things adapter against a synthetic database with the real schema shape.  Builds, Things binary date: bits [16..26] year, [12..15] month, [7..11] day., test_classification(), test_opens_read_only()

### Community 6 - "test_evals.py"
Cohesion: 0.48
Nodes (6): by_name(), load(), The evals harness must discriminate: golden scores clean, every degraded variant, test_degraded_cases_are_caught(), test_every_degraded_case_scores_below_golden(), test_golden_passes_everything()

### Community 7 - "test_adapters.py"
Cohesion: 0.40
Nodes (3): kinds(), Raw source payloads map to the normalized snapshot correctly., test_ha_extracts_actionable_states()

### Community 8 - "make_fixtures.py"
Cohesion: 0.67
Nodes (3): dump(), main(), Regenerate the golden briefing fixture + its degraded variants.  The golden case

## Knowledge Gaps
- **1 isolated node(s):** `reveille`
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SourceSnapshot` connect `SourceSnapshot` to `coordinator.py`, `cli.py`, `_fixture_snapshots`, `run_checks`?**
  _High betweenness centrality (0.320) - this node is a cross-community bridge._
- **Why does `from_database()` connect `SourceSnapshot` to `test_things.py`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._
- **Why does `run_checks()` connect `run_checks` to `SourceSnapshot`, `cli.py`, `_fixture_snapshots`, `test_evals.py`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `run_checks()` (e.g. with `test_offline_composer_passes_its_own_evals()` and `test_degraded_cases_are_caught()`) actually correct?**
  _`run_checks()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `_fixture_snapshots()` (e.g. with `main()` and `test_compose_fans_out_and_merges()`) actually correct?**
  _`_fixture_snapshots()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `reveille` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `SourceSnapshot` be split into smaller, more focused modules?**
  _Cohesion score 0.1051693404634581 - nodes in this community are weakly interconnected._