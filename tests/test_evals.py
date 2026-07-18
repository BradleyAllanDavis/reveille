"""The evals harness must discriminate: golden scores clean, every degraded
variant is caught by the check aimed at its failure mode, and compare()
turns a score drop into a CI failure."""

import json
from pathlib import Path

import pytest

from reveille.cli import _fixture_snapshots
from reveille.evals.checks import run_checks
from reveille.evals.scorecard import compare, run_suite, score_case, to_scorecard

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def snapshots():
    return _fixture_snapshots()


def by_name(checks):
    return {check.name: check for check in checks}


def load(case):
    return json.loads((FIXTURES / "briefings" / f"{case}.json").read_text())


def test_golden_passes_everything(snapshots):
    checks = by_name(run_checks(load("golden"), snapshots))
    assert all(check.passed for check in checks.values()), {
        name: check.details for name, check in checks.items() if not check.passed
    }


@pytest.mark.parametrize(
    ("case", "failing_check"),
    [
        ("hallucinated", "grounding"),
        ("shallow", "coverage"),
        ("leaky", "hygiene"),
        ("bloated", "budget"),
        ("malformed", "schema"),
    ],
)
def test_degraded_cases_are_caught(snapshots, case, failing_check):
    checks = by_name(run_checks(load(case), snapshots))
    assert not checks[failing_check].passed, f"{case} should fail {failing_check}"


def test_every_degraded_case_scores_below_golden(snapshots):
    golden = score_case(FIXTURES / "briefings" / "golden.json", snapshots).total
    for case in ("hallucinated", "shallow", "leaky", "bloated", "malformed"):
        total = score_case(FIXTURES / "briefings" / f"{case}.json", snapshots).total
        assert total < golden, f"{case} scored {total}, golden {golden}"


def test_compare_flags_regressions(snapshots):
    results = run_suite(FIXTURES / "briefings", snapshots)
    scorecard = to_scorecard(results)
    assert compare(scorecard, scorecard) == []

    worse = json.loads(json.dumps(scorecard))
    worse["cases"]["golden"]["total"] -= 0.1
    worse["cases"]["golden"]["checks"]["grounding"]["score"] -= 0.1
    regressions = compare(scorecard, worse)
    assert any("golden: total" in regression for regression in regressions)
    assert any("golden/grounding" in regression for regression in regressions)


def test_compare_flags_missing_case(snapshots):
    scorecard = to_scorecard(run_suite(FIXTURES / "briefings", snapshots))
    partial = json.loads(json.dumps(scorecard))
    del partial["cases"]["golden"]
    assert any("missing" in regression for regression in compare(scorecard, partial))
