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

## Lineage (what was extracted from where)

| pattern | control-plane origin |
|---|---|
| Things schema constants, packed-date decode, mirror-first path | things-turbo / things.py reader |
| deterministic-signal-vs-model-disagreement framing | things-triage escalation cascade |
| scorecard-as-report verb, baseline discipline | things-triage scores side-store + report |
| key-free-by-default, subscription-vs-metered split | things-triage "no API key in the script" design |
| gate-then-run scheduling posture (roadmap) | claude-jobs exit-100 gates |
