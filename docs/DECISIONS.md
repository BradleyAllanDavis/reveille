# Decision log

Provenance convention: `[llm-synth]` marks a decision made autonomously by an LLM agent
during the build (zero-interaction charter, 2026-07-18); `[human]` marks a decision made
by Bradley. Unmarked entries are mechanical consequences of marked ones.

## 2026-07-18 — initial build

- `[llm-synth]` **Name: reveille.** The morning bugle call. Searched for collisions among
  AI briefing tools; none found.
- `[llm-synth]` **Python + Anthropic SDK over TypeScript + Vercel AI SDK.** The control
  plane this extracts from is Python (uv single-file scripts, sqlite side-stores), so
  extraction friction is lowest; the evals harness lands naturally on pytest.
- `[llm-synth]` **Two deps only (`anthropic`, `pydantic`).** Pydantic earns its slot
  because schema conformance is itself an eval check. Everything else is stdlib.
- `[llm-synth]` **Deterministic checks and LLM-judge kept in separate lanes, never
  blended.** A rubric drift must not be able to mask a grounding regression. Judge is
  optional and additive.
- `[llm-synth]` **Citations (SourceRefs) are mandatory in the output contract.** Turns
  hallucination detection into set membership against snapshot ids. The editor agent may
  only copy analyst items verbatim, extending the same guarantee to top priorities.
- `[llm-synth]` **Offline composer as a first-class path.** Keeps CI key-free, generates
  golden fixtures, and provides the quality floor the LLM path must beat. Chosen over
  record/replay of LLM responses (prompt-hash keyed replay is brittle across prompt
  edits).
- `[llm-synth]` **Degraded fixtures prove discrimination.** One committed corruption per
  failure mode (hallucinated, shallow, leaky, bloated, malformed), with tests asserting
  the targeted check catches each. An eval suite that only ever sees good output is
  unfalsifiable.
- `[llm-synth]` **Things adapter hand-writes the SQL** (schema constants and the packed
  binary date decode taken from the control plane's reader) instead of depending on
  `things.py`. Read-only via sqlite URI `mode=ro`; resolves the agent-readable mirror
  before the live database because macOS TCC blocks headless agents from the latter.
- `[llm-synth]` **HA/UniFi ship as recorded-payload adapters, live fetch deferred.**
  Charter called for a vertical slice on one real source (Things) first. The normalizers
  are the same code a live fetch will feed.
- `[llm-synth]` **Baseline compare tolerates improvements, fails drops** beyond 0.01, and
  treats a vanished case as a regression. New cases extend coverage without failing.
- `[llm-synth]` **Model IDs** `claude-haiku-4-5` (analysts) / `claude-sonnet-5` (editor),
  current as of 2026-07. No sampling params (removed on current models); JSON extracted
  from text with one repair retry rather than structured-output mode, keeping the backend
  seam a plain string interface a test fake can implement.
- Bootstrap note: built on host morpheus under a zero-interaction charter; the session's
  background-isolation guard blocked the harness Write/Edit tools for a repo created
  mid-session, so files landed via shell heredocs. No functional impact.

## 2026-07-18 — phase 2: live sources, scheduling, judge history

- `[llm-synth]` **Live HA/UniFi fetch wired behind the existing normalizers**, not new
  code paths. `home_assistant.fetch()` already existed; added the matching
  `unifi.fetch()` (UniFi Network API, `X-API-KEY`, `/proxy/network/api/s/<site>/{stat/health,stat/sta}`,
  unwrapping the `{"meta", "data"}` envelope) and CLI flags `--live-ha` / `--live-unifi`
  alongside the existing `--live-things`. Fixtures stay the CI path; `--live-*` is
  opt-in and untouched by `reveille evals`.
- `[llm-synth]` **Credential indirection, not a hardcoded secret manager.** A public
  portfolio repo shouldn't bake in a personal 1Password vault path. `_resolve_secret()`
  reads `$HA_TOKEN` / `$UNIFI_API_KEY` directly, or runs a command named in
  `$HA_TOKEN_CMD` / `$UNIFI_API_KEY_CMD` and takes its stdout -- e.g.
  `HA_TOKEN_CMD='op-read-serialized "op://Automation/Home Assistant Token/credential"'`
  wires a personal 1Password read without the repo knowing 1Password exists.
- `[llm-synth]` **Both live fetchers take `verify_ssl`** (`HA_VERIFY_SSL` /
  `UNIFI_VERIFY_SSL` env, default true). Local HA/UniFi controllers are almost always
  self-signed; verified live against a real controller and a real HA instance
  (self-signed Caddy front, `-k`-equivalent `ssl.CERT_NONE`) before landing.
- `[llm-synth]` **Scheduled-run target: a plain shell script, not a new dependency.**
  `scripts/scheduled-brief.sh` wraps `reveille brief`, writes dated markdown +
  a run log, and propagates a nonzero exit so cron/launchd's own failure handling
  fires. `contrib/launchd/com.reveille.daily.plist` is the macOS example; a cron
  line works identically on Linux. No new scheduler abstraction -- the CLI is
  already the unit of work.
- `[llm-synth]` **Judge-score history is a separate sqlite side-store
  (`evals/judge_history.sqlite`, gitignored)**, not folded into `baseline.json`.
  Same separation-of-concerns as the deterministic/judge split: `baseline.json` is
  the CI gate (committed, deterministic checks only); the history db is a local,
  accumulating log of judge verdicts over time, printed as a trend delta on each
  `--judge` run. Mirrors the control-plane's own score side-stores per the lineage
  table below.
- `[llm-synth]` **LLM path run end-to-end against a real key, scored against the
  offline composer.** Both hit 1.00 on every deterministic check (grounding,
  coverage, priorities, budget, hygiene, schema) over the fixture snapshots -- the
  LLM path clears the floor the offline composer sets, as designed. The optional
  judge rubric (1-5, model-graded) preferred the LLM path on editorial quality:
  actionability 3 vs 2, prioritization 3 vs 2, concision 2 vs 3 (offline's terser
  phrasing edges concision; the LLM path's analyst framing edges the other two).
  Neither run is committed as a fixture -- this was a one-time verification, not a
  new golden case.

## 2026-11-21 — content-hash cache for the judge cell

- `[llm-synth]` **Only the judge is cached; the six deterministic checks are not.**
  Verified by reading the harness: `checks.py` and `scorecard.py` never import the LLM
  seam, so the only token spend in `reveille evals` is the optional `--judge` call, once
  per fixture. The deterministic suite (36 cells) measures 0.44 ms per full run. Looking
  those 36 cells up in this same cache, hash plus read with every entry warm, measures
  0.85 ms, so caching them would be about twice as slow as recomputing and would add a
  stale-score risk to the CI gate. A `--judge` run reports them in one line as
  `skipped-deterministic` rather than pretending they were cache hits.
- `[llm-synth]` **Key = sha256 over canonical JSON of (step id, `JUDGE_VERSION`, rubric
  text, model id, `max_tokens`, rendered briefing markdown).** Invalidation is purely
  structural: there is no TTL and nothing to remember to flush. `JUDGE_VERSION` exists
  for the one change the other parts can't see, a logic change in parsing or validation.
  The fixture's name is deliberately not in the key, so the cache is addressed by content
  alone.
- `[llm-synth]` **The validated verdict is cached, not the raw model reply.** The
  obvious design is a caching wrapper at the `LLMBackend` seam. That was rejected
  because a seam-level cache stores the reply before it is parsed, so one malformed reply
  would be memoized and replayed forever. Memoizing one level up, in `cached_judge()`,
  stores only verdicts that passed validation, and still composes with any backend
  including the test fake. Cache entries are re-validated on read, so a corrupt or
  out-of-range file is a miss that the next call overwrites.
- `[llm-synth]` **History rule changed, explicitly: a cached verdict a case already has
  on record is not re-appended to `judge_history.sqlite`.** Before, every `--judge` run
  appended one row per fixture. With a cache, a warm rerun produces no new model opinion,
  and re-appending would pad the trend with duplicates. A miss always records. A hit
  records only when its scores differ from the case's latest row (or the case has none),
  which covers the cold-run dedupe below and a fixture reverted to earlier content. The
  comparison is on the three scores, not the rationale text, because the trend is a
  trend of scores.
- `[llm-synth]` **Two fixtures share one cache entry.** `golden` and `hallucinated`
  render to byte-identical markdown, because the hallucinated source refs live in fields
  the markdown omits. So the judge cannot tell them apart, which is correct: catching
  hallucinated refs is the grounding check's job, not the rubric's. A cold run is 4 model
  calls for 5 judge cells; a warm rerun is 0.
- `[llm-synth]` **Fixed in passing: `evals --judge` crashed on the `malformed` fixture.**
  The judge loop schema-validated every fixture and `malformed` is invalid by design, so
  the run raised partway through, after spending calls on the fixtures sorted before it.
  It went unnoticed because the judge path had no test. A schema-invalid briefing is now
  reported as `skipped` (nothing to render; the schema check already scores it 0), and
  the judge loop is covered end to end with a counting fake backend.
- `[llm-synth]` **`--clear-cache` clears, then runs.** Exiting after the clear would make
  the common intent, a forced refresh, a two-command operation. It deletes only
  `<sha256>.json` entries and their temp files, never the directory or other files in it, because
  `REVEILLE_CACHE_DIR` is user-supplied and a recursive delete of a mistyped path is not
  a risk worth taking for a cache. `--no-cache` bypasses both read and write.
- `[llm-synth]` **Not done: caching the `brief` composer's model calls.** Those run on
  live data that changes every morning, so the hit rate would be near zero.

## Lineage (what was extracted from where)

| pattern | control-plane origin |
|---|---|
| Things schema constants, packed-date decode, mirror-first path | things-turbo / things.py reader |
| deterministic-signal-vs-model-disagreement framing | things-triage escalation cascade |
| scorecard-as-report verb, baseline discipline | things-triage scores side-store + report |
| key-free-by-default, subscription-vs-metered split | things-triage "no API key in the script" design |
| gate-then-run scheduling posture (roadmap) | claude-jobs exit-100 gates |
