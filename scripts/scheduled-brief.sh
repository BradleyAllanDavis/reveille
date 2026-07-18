#!/usr/bin/env bash
# scheduled-brief.sh: cron/launchd entry point for a recurring reveille run.
# Writes dated markdown to $REVEILLE_OUT_DIR (default ~/reveille-briefings)
# and appends one line to its run.log per invocation. Exits nonzero on
# failure so the scheduler's own handling (launchd relaunch/backoff, cron
# mail) fires on a bad run instead of failing silently.
#
# Usage: scheduled-brief.sh [reveille brief flags, e.g. --offline]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${REVEILLE_OUT_DIR:-$HOME/reveille-briefings}"
mkdir -p "$OUT_DIR"
OUT_FILE="$OUT_DIR/$(date +%F).md"

cd "$REPO_ROOT"
if uv run reveille brief "$@" --out "$OUT_FILE"; then
  echo "$(date -u +%FT%TZ) ok $OUT_FILE" >> "$OUT_DIR/run.log"
else
  status=$?
  echo "$(date -u +%FT%TZ) FAILED (exit $status)" >> "$OUT_DIR/run.log"
  exit "$status"
fi
