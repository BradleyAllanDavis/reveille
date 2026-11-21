"""Content-addressed on-disk cache for the one eval step that spends tokens.

Only the optional LLM-judge cell is cached. The six deterministic checks
recompute in microseconds from the fixture; hashing and storing their result
would cost more than redoing them, and a stale cached score is a worse failure
than a wasted millisecond. See docs/DECISIONS.md.

A cell's key is sha256 over a canonical JSON serialization of everything that
can change the answer: step id, component version, rubric text, model id, model
params, and the exact input. Change any one and the key changes, so a stale
verdict can never be served. Files are ``<key>.json``; anything unreadable or
malformed is treated as a miss, never an error.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

ENV_DIR = "REVEILLE_CACHE_DIR"
_KEY = re.compile(r"[0-9a-f]{64}")


def default_dir(repo_root: Path) -> Path:
    return Path(os.environ.get(ENV_DIR) or repo_root / "evals" / "judge_cache")


def cache_key(**parts: object) -> str:
    blob = json.dumps(parts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


class ResultCache:
    def __init__(self, directory: Path) -> None:
        self.dir = Path(directory)

    def get(self, key: str) -> dict | None:
        try:
            value = json.loads((self.dir / f"{key}.json").read_text())
        except (OSError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    def put(self, key: str, value: dict) -> None:
        # Write to a per-process temp name, then atomically replace: neither a crash
        # mid-write nor a concurrent run can leave a half-file under the real name.
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = self.dir / f"{key}.json.{os.getpid()}.tmp"
            tmp.write_text(json.dumps(value))
            os.replace(tmp, self.dir / f"{key}.json")
        except OSError:
            pass  # an unwritable cache degrades to no cache

    def clear(self) -> int:
        """Delete cache entries and their temp files: only files named ``<sha256>.json*``,
        never the directory or anything else in it, since the path is user-overridable."""
        removed = 0
        for path in self.dir.glob("*.json*") if self.dir.is_dir() else ():
            if _KEY.fullmatch(path.name.split(".")[0]) and path.is_file():
                try:
                    path.unlink()
                except OSError:
                    continue
                removed += 1
        return removed
