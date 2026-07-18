"""Suite runner + scorecard + regression compare.

An eval case is a briefing JSON file scored against the shared snapshot
fixtures. The suite emits a scorecard (JSON for machines, markdown for
humans); ``compare()`` diffs a scorecard against the committed baseline and
reports regressions, which is what makes the suite CI-gateable: a prompt or
pipeline change that quietly degrades grounding fails the build the same way
a broken unit test would.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..schema import SourceSnapshot
from .checks import CheckResult, run_checks

REGRESSION_TOLERANCE = 0.01


@dataclass
class CaseResult:
    case: str
    checks: list[CheckResult]

    @property
    def total(self) -> float:
        weight_sum = sum(check.weight for check in self.checks)
        return round(
            sum(check.score * check.weight for check in self.checks) / weight_sum, 4
        )


def load_snapshots(paths: list[Path]) -> list[SourceSnapshot]:
    return [SourceSnapshot.model_validate_json(path.read_text()) for path in paths]


def score_case(case_path: Path, snapshots: list[SourceSnapshot]) -> CaseResult:
    raw = json.loads(case_path.read_text())
    return CaseResult(case=case_path.stem, checks=run_checks(raw, snapshots))


def run_suite(cases_dir: Path, snapshots: list[SourceSnapshot]) -> list[CaseResult]:
    cases = sorted(cases_dir.glob("*.json"))
    if not cases:
        raise FileNotFoundError(f"no eval cases in {cases_dir}")
    return [score_case(path, snapshots) for path in cases]


def to_scorecard(results: list[CaseResult]) -> dict:
    return {
        "cases": {
            result.case: {
                "total": result.total,
                "checks": {
                    check.name: {"score": check.score, "passed": check.passed}
                    for check in result.checks
                },
            }
            for result in results
        }
    }


def to_markdown(results: list[CaseResult]) -> str:
    names = [check.name for check in results[0].checks]
    lines = [
        "| case | " + " | ".join(names) + " | total |",
        "|---" * (len(names) + 2) + "|",
    ]
    for result in results:
        cells = " | ".join(f"{check.score:.2f}" for check in result.checks)
        lines.append(f"| {result.case} | {cells} | **{result.total:.2f}** |")
    return "\n".join(lines)


def compare(baseline: dict, current: dict, tolerance: float = REGRESSION_TOLERANCE) -> list[str]:
    """Return regression descriptions; empty list = no regressions.

    New cases are fine (they extend coverage); a case that disappears or a
    score that drops more than ``tolerance`` is a regression.
    """
    regressions: list[str] = []
    for case, base in baseline.get("cases", {}).items():
        cur = current.get("cases", {}).get(case)
        if cur is None:
            regressions.append(f"{case}: case missing from current run")
            continue
        if cur["total"] < base["total"] - tolerance:
            regressions.append(f"{case}: total {base['total']} -> {cur['total']}")
        for name, base_check in base.get("checks", {}).items():
            cur_check = cur.get("checks", {}).get(name)
            if cur_check is None:
                regressions.append(f"{case}/{name}: check missing")
            elif cur_check["score"] < base_check["score"] - tolerance:
                regressions.append(
                    f"{case}/{name}: {base_check['score']} -> {cur_check['score']}"
                )
    return regressions
