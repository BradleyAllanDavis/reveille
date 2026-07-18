"""CLI: `reveille brief` composes; `reveille evals` scores.

The two subcommands mirror the repo's two halves. `brief` runs the source
adapters and the coordinator; `evals` runs the harness over the committed
fixture cases (or a briefing you just generated) and compares against the
baseline — exit 1 on regression makes it a CI gate.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .coordinator import compose, compose_offline
from .evals.scorecard import compare, load_snapshots, run_suite, to_markdown, to_scorecard
from .schema import Briefing, SourceSnapshot
from .sources import home_assistant, things, unifi, wiki

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "fixtures"
BASELINE = REPO_ROOT / "evals" / "baseline.json"


def gather_snapshots(args: argparse.Namespace) -> list[SourceSnapshot]:
    snapshots: list[SourceSnapshot] = []
    if args.live_things:
        snapshots.append(things.from_database())
    else:
        snapshots.append(
            SourceSnapshot.model_validate_json((FIXTURES / "things_snapshot.json").read_text())
        )
    snapshots.append(home_assistant.from_fixture(FIXTURES / "ha_states.json"))
    snapshots.append(unifi.from_fixture(FIXTURES / "unifi_payload.json"))
    if args.wiki_dir:
        snapshots.append(wiki.from_directory(args.wiki_dir))
    return snapshots


def cmd_brief(args: argparse.Namespace) -> int:
    snapshots = gather_snapshots(args)
    if args.offline:
        briefing = compose_offline(snapshots)
    else:
        from .llm import AnthropicBackend

        briefing = asyncio.run(compose(snapshots, AnthropicBackend()))
    if args.json:
        output = briefing.model_dump_json(indent=2)
    else:
        output = briefing.to_markdown()
    if args.out:
        Path(args.out).write_text(output)
        print(f"wrote {args.out}")
    else:
        print(output)
    return 0


def _fixture_snapshots() -> list[SourceSnapshot]:
    normalized = [FIXTURES / "things_snapshot.json"]
    snapshots = load_snapshots(normalized)
    snapshots.append(home_assistant.from_fixture(FIXTURES / "ha_states.json"))
    snapshots.append(unifi.from_fixture(FIXTURES / "unifi_payload.json"))
    return snapshots


def cmd_evals(args: argparse.Namespace) -> int:
    snapshots = _fixture_snapshots()
    results = run_suite(FIXTURES / "briefings", snapshots)
    scorecard = to_scorecard(results)
    scorecard["generated_at"] = datetime.now(timezone.utc).isoformat()
    print(to_markdown(results))

    if args.judge:
        from .evals.judge import judge_sync
        from .llm import AnthropicBackend

        backend = AnthropicBackend()
        for path in sorted((FIXTURES / "briefings").glob("*.json")):
            briefing = Briefing.model_validate_json(path.read_text())
            verdict = judge_sync(backend, briefing.to_markdown())
            print(f"\njudge[{path.stem}]: {json.dumps(verdict)}")

    if args.update_baseline:
        BASELINE.parent.mkdir(exist_ok=True)
        BASELINE.write_text(json.dumps(scorecard, indent=2) + "\n")
        print(f"\nbaseline updated: {BASELINE}")
        return 0

    if BASELINE.exists():
        regressions = compare(json.loads(BASELINE.read_text()), scorecard)
        if regressions:
            print("\nREGRESSIONS:", file=sys.stderr)
            for regression in regressions:
                print(f"  - {regression}", file=sys.stderr)
            return 1
        print("\nno regressions vs baseline")
    else:
        print("\nno baseline committed yet (run with --update-baseline)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reveille")
    sub = parser.add_subparsers(dest="command", required=True)

    brief = sub.add_parser("brief", help="compose a morning briefing")
    brief.add_argument("--offline", action="store_true", help="deterministic composer, no API")
    brief.add_argument("--live-things", action="store_true", help="read the local Things database")
    brief.add_argument("--wiki-dir", help="directory of markdown docs to include")
    brief.add_argument("--json", action="store_true", help="emit briefing JSON instead of markdown")
    brief.add_argument("--out", help="write output to a file")
    brief.set_defaults(func=cmd_brief)

    evals = sub.add_parser("evals", help="run the eval suite over fixture briefings")
    evals.add_argument("--update-baseline", action="store_true")
    evals.add_argument("--judge", action="store_true", help="also run the LLM-judge rubric")
    evals.set_defaults(func=cmd_evals)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
