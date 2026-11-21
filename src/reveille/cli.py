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
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from .coordinator import compose, compose_offline
from .demo import demo_snapshots
from .evals.cache import ResultCache, default_dir
from .evals.scorecard import compare, run_suite, to_markdown, to_scorecard
from .schema import Briefing, SourceSnapshot
from .sources import home_assistant, things, unifi, wiki

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "fixtures"
BASELINE = REPO_ROOT / "evals" / "baseline.json"
JUDGE_HISTORY_DB = REPO_ROOT / "evals" / "judge_history.sqlite"


def _resolve_secret(value_env: str, cmd_env: str) -> str:
    """A live credential from an env var, or from running a command named in
    another env var (its stdout, trimmed). The command indirection lets a
    deployment wire any secret manager (1Password, pass, ...) without this
    repo hardcoding one -- e.g. ``HA_TOKEN_CMD='op-read-serialized op://...'``.
    """
    if value := os.environ.get(value_env):
        return value
    if cmd := os.environ.get(cmd_env):
        try:
            result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as err:
            raise SystemExit(f"${cmd_env} command failed (exit {err.returncode}): {cmd}") from err
        return result.stdout.strip()
    raise SystemExit(f"missing credential: set ${value_env} or ${cmd_env}")


def _env_flag(name: str, default: bool = True) -> bool:
    return os.environ.get(name, str(default)).lower() not in ("false", "0", "no")


def gather_snapshots(args: argparse.Namespace) -> list[SourceSnapshot]:
    snapshots: list[SourceSnapshot] = []
    if args.live_things:
        snapshots.append(things.from_database())
    else:
        snapshots.append(
            SourceSnapshot.model_validate_json((FIXTURES / "things_snapshot.json").read_text())
        )

    if args.live_ha:
        base_url = os.environ.get("HA_URL")
        if not base_url:
            raise SystemExit("--live-ha requires $HA_URL")
        token = _resolve_secret("HA_TOKEN", "HA_TOKEN_CMD")
        states = home_assistant.fetch(base_url, token, verify_ssl=_env_flag("HA_VERIFY_SSL"))
        snapshots.append(home_assistant.from_states(states))
    else:
        snapshots.append(home_assistant.from_fixture(FIXTURES / "ha_states.json"))

    if args.live_unifi:
        base_url = os.environ.get("UNIFI_URL")
        if not base_url:
            raise SystemExit("--live-unifi requires $UNIFI_URL")
        api_key = _resolve_secret("UNIFI_API_KEY", "UNIFI_API_KEY_CMD")
        site = os.environ.get("UNIFI_SITE", "default")
        payload = unifi.fetch(base_url, api_key, site, verify_ssl=_env_flag("UNIFI_VERIFY_SSL"))
        snapshots.append(unifi.from_payload(payload))
    else:
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


def cmd_evals(args: argparse.Namespace) -> int:
    snapshots = demo_snapshots()
    results = run_suite(FIXTURES / "briefings", snapshots)
    scorecard = to_scorecard(results)
    scorecard["generated_at"] = datetime.now(timezone.utc).isoformat()
    print(to_markdown(results))

    store = ResultCache(default_dir(REPO_ROOT))
    if args.clear_cache:
        print(f"\ncleared {store.clear()} cache entries")
    cache = None if args.no_cache else store

    if args.judge:
        from .evals import history
        from .evals.judge import AXES, cached_judge
        from .llm import AnthropicBackend

        print("\ncache: deterministic checks are skipped-deterministic (recomputed every run, never cached)")
        backend = AnthropicBackend()
        statuses: list[str] = []
        for path in sorted((FIXTURES / "briefings").glob("*.json")):
            try:
                briefing = Briefing.model_validate_json(path.read_text())
            except ValidationError:
                # A briefing that fails the schema can't be rendered; the schema check
                # already scores it 0, so there is nothing for the judge to read.
                statuses.append("skipped")
                print(f"\njudge[{path.stem}] (skipped): fails the schema, nothing to judge")
                continue
            verdict, status = cached_judge(backend, briefing.to_markdown(), cache)
            statuses.append(status)
            print(f"\njudge[{path.stem}] ({status}): {json.dumps(verdict)}")
            previous = history.trend(JUDGE_HISTORY_DB, path.stem, limit=1)
            if status == "hit" and previous and previous[0][1:] == tuple(verdict[axis] for axis in AXES):
                # A cached verdict this case already has on record is not a new
                # observation; re-appending it would double-count the trend.
                print("  history unchanged (cached verdict already recorded)")
                continue
            history.record(JUDGE_HISTORY_DB, path.stem, verdict)
            if previous:
                _, prev_a, prev_p, prev_c = previous[0]
                print(
                    f"  vs previous run: actionability {prev_a}->{verdict['actionability']}, "
                    f"prioritization {prev_p}->{verdict['prioritization']}, "
                    f"concision {prev_c}->{verdict['concision']}"
                )
        n = {status: statuses.count(status) for status in ("hit", "miss", "bypassed", "skipped")}
        extras = "".join(f", {n[status]} {status}" for status in ("bypassed", "skipped") if n[status])
        print(f"\njudge: {n['hit']} hits, {n['miss']} misses{extras} ({n['miss'] + n['bypassed']} model calls)")

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
    brief.add_argument("--live-ha", action="store_true", help="fetch Home Assistant states ($HA_URL)")
    brief.add_argument("--live-unifi", action="store_true", help="fetch UniFi controller data ($UNIFI_URL)")
    brief.add_argument("--wiki-dir", help="directory of markdown docs to include")
    brief.add_argument("--json", action="store_true", help="emit briefing JSON instead of markdown")
    brief.add_argument("--out", help="write output to a file")
    brief.set_defaults(func=cmd_brief)

    evals = sub.add_parser("evals", help="run the eval suite over fixture briefings")
    evals.add_argument("--update-baseline", action="store_true")
    evals.add_argument("--judge", action="store_true", help="also run the LLM-judge rubric")
    evals.add_argument("--no-cache", action="store_true", help="bypass the judge cache (no read, no write)")
    evals.add_argument("--clear-cache", action="store_true", help="delete cached judge verdicts, then run as normal")
    evals.set_defaults(func=cmd_evals)

    serve = sub.add_parser("serve", help="run the demo HTTP API (uvicorn)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8420)
    serve.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("reveille.api:app", host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
