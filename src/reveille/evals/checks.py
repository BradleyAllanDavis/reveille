"""Deterministic eval checks over a (snapshots, briefing) pair.

Every check is mechanical — no model in the loop — so the core suite is fast,
free, and byte-for-byte reproducible in CI. Each returns a score in [0, 1]
plus a pass/fail against its own threshold; the scorecard weights them into a
single number that can be regression-compared against a committed baseline.

The checks encode the failure modes that actually matter for an agent-written
briefing:

- schema:    output contract holds (a briefing a renderer can't parse is not
             a briefing)
- grounding: every citation resolves to a real snapshot entity — the
             hallucination detector
- coverage:  urgent source facts (today/overdue tasks, priority-1 signals)
             actually surface — the omission detector
- priorities: top-priorities discipline (bounded, ordered, grounded)
- budget:    a briefing that takes 10 minutes to read failed at its job
- hygiene:   no secret-shaped strings in output that may leave the machine
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from ..schema import Briefing, SourceSnapshot

URGENT_KINDS = {"today_task", "overdue_task", "open_contact", "subsystem_degraded"}

MAX_SUMMARY_WORDS = 80
MAX_ITEMS_PER_SECTION = 6
MAX_TOP_PRIORITIES = 5

SECRET_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"sk-ant-[A-Za-z0-9_-]{10,}",       # Anthropic API keys
        r"AKIA[0-9A-Z]{16}",                # AWS access keys
        r"ghp_[A-Za-z0-9]{20,}",            # GitHub PATs
        r"xox[baprs]-[A-Za-z0-9-]{10,}",    # Slack tokens
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"eyJ[A-Za-z0-9_-]{20,}\.eyJ",      # JWTs
    )
]


@dataclass
class CheckResult:
    name: str
    score: float          # 0..1
    passed: bool
    weight: float = 1.0
    details: str = ""


@dataclass
class CheckContext:
    raw: dict                     # briefing as parsed JSON (pre-validation)
    snapshots: list[SourceSnapshot]
    briefing: Briefing | None = None
    entity_index: dict[str, set[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.entity_index = {snap.source: snap.ids() for snap in self.snapshots}


def check_schema(ctx: CheckContext) -> CheckResult:
    try:
        ctx.briefing = Briefing.model_validate(ctx.raw)
    except ValidationError as err:
        return CheckResult("schema", 0.0, False, weight=2.0, details=str(err)[:500])
    return CheckResult("schema", 1.0, True, weight=2.0)


def check_grounding(ctx: CheckContext) -> CheckResult:
    assert ctx.briefing is not None
    refs = ctx.briefing.all_refs()
    if not refs:
        return CheckResult("grounding", 0.0, False, weight=2.0, details="briefing cites nothing")
    bad = [ref.key for ref in refs if ref.id not in ctx.entity_index.get(ref.source, set())]
    score = 1.0 - len(bad) / len(refs)
    return CheckResult(
        "grounding",
        round(score, 4),
        not bad,
        weight=2.0,
        details=f"unresolvable refs: {bad[:10]}" if bad else f"{len(refs)} refs, all resolve",
    )


def check_coverage(ctx: CheckContext) -> CheckResult:
    assert ctx.briefing is not None
    urgent = {
        (snap.source, entity.id)
        for snap in ctx.snapshots
        for entity in snap.entities
        if entity.kind in URGENT_KINDS
    }
    if not urgent:
        return CheckResult("coverage", 1.0, True, details="no urgent entities in snapshots")
    cited = {(ref.source, ref.id) for ref in ctx.briefing.all_refs()}
    missed = urgent - cited
    score = 1.0 - len(missed) / len(urgent)
    return CheckResult(
        "coverage",
        round(score, 4),
        not missed,
        weight=1.5,
        details=f"missed urgent: {sorted(missed)[:10]}" if missed else f"all {len(urgent)} covered",
    )


def check_priorities(ctx: CheckContext) -> CheckResult:
    assert ctx.briefing is not None
    top = ctx.briefing.top_priorities
    problems: list[str] = []
    if len(top) > MAX_TOP_PRIORITIES:
        problems.append(f"{len(top)} top priorities (max {MAX_TOP_PRIORITIES})")
    if any(not item.refs for item in top):
        problems.append("top priority without refs")
    if [item.priority for item in top] != sorted(item.priority for item in top):
        problems.append("top priorities not ordered by priority")
    score = max(0.0, 1.0 - 0.34 * len(problems))
    return CheckResult("priorities", round(score, 4), not problems, details="; ".join(problems))


def check_budget(ctx: CheckContext) -> CheckResult:
    assert ctx.briefing is not None
    problems: list[str] = []
    words = len(ctx.briefing.executive_summary.split())
    if words > MAX_SUMMARY_WORDS:
        problems.append(f"executive summary {words} words (max {MAX_SUMMARY_WORDS})")
    for section in ctx.briefing.sections:
        if len(section.items) > MAX_ITEMS_PER_SECTION:
            problems.append(f"section {section.source}: {len(section.items)} items")
    score = max(0.0, 1.0 - 0.5 * len(problems))
    return CheckResult("budget", round(score, 4), not problems, details="; ".join(problems))


def check_hygiene(ctx: CheckContext) -> CheckResult:
    text = json.dumps(ctx.raw)
    hits = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]
    return CheckResult(
        "hygiene",
        0.0 if hits else 1.0,
        not hits,
        weight=2.0,
        details=f"secret-shaped strings matched: {hits}" if hits else "",
    )


def run_checks(raw: dict, snapshots: list[SourceSnapshot]) -> list[CheckResult]:
    ctx = CheckContext(raw=raw, snapshots=snapshots)
    results = [check_schema(ctx)]
    if ctx.briefing is None:
        # Schema failed: dependent checks are unrunnable and score 0 rather
        # than silently vanishing from the scorecard.
        for name, weight in (
            ("grounding", 2.0), ("coverage", 1.5), ("priorities", 1.0), ("budget", 1.0)
        ):
            results.append(CheckResult(name, 0.0, False, weight=weight, details="schema invalid"))
        results.append(check_hygiene(ctx))
        return results
    results += [
        check_grounding(ctx),
        check_coverage(ctx),
        check_priorities(ctx),
        check_budget(ctx),
        check_hygiene(ctx),
    ]
    return results
