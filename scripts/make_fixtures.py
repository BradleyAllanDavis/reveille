"""Regenerate the golden briefing fixture + its degraded variants.

The golden case is the deterministic composer's output over the committed
source fixtures — regenerate after changing the composer or fixtures, then
re-baseline (`reveille evals --update-baseline`). The degraded variants are
mechanical corruptions of the golden briefing, one per failure mode the
harness must catch; they are what proves the evals discriminate rather than
rubber-stamp.
"""

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from reveille.cli import _fixture_snapshots  # noqa: E402
from reveille.coordinator import compose_offline  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "fixtures" / "briefings"


def dump(name: str, data: dict) -> None:
    (OUT / f"{name}.json").write_text(json.dumps(data, indent=2, default=str) + "\n")
    print(f"wrote {name}.json")


def main() -> None:
    briefing = compose_offline(_fixture_snapshots())
    briefing.generated_at = briefing.generated_at.replace(
        year=2026, month=7, day=18, hour=12, minute=5, second=0, microsecond=0
    )
    golden = json.loads(briefing.model_dump_json())
    dump("golden", golden)

    # hallucinated: cites an entity id that exists in no snapshot
    bad = copy.deepcopy(golden)
    bad["top_priorities"][0]["refs"] = [{"source": "things", "id": "TT-9999"}]
    bad["sections"][0]["items"][0]["refs"] = [{"source": "things", "id": "TT-9999"}]
    dump("hallucinated", bad)

    # shallow: drops the urgent items entirely (misses overdue task + open door)
    shallow = copy.deepcopy(golden)
    shallow["top_priorities"] = shallow["top_priorities"][-1:]
    for section in shallow["sections"]:
        section["items"] = [item for item in section["items"] if item["priority"] > 1]
    dump("shallow", shallow)

    # leaky: a secret-shaped string ends up in the output
    leaky = copy.deepcopy(golden)
    leaky["sections"][0]["items"][0]["detail"] = (
        "raised by automation using key sk-ant-api03-FAKEFAKEFAKEFAKE"
    )
    dump("leaky", leaky)

    # bloated: blows the reading budget
    bloated = copy.deepcopy(golden)
    bloated["executive_summary"] = " ".join(["morning"] * 120)
    dump("bloated", bloated)

    # malformed: breaks the output contract (priority out of range, missing field)
    malformed = copy.deepcopy(golden)
    malformed["top_priorities"][0]["priority"] = 9
    del malformed["executive_summary"]
    dump("malformed", malformed)


if __name__ == "__main__":
    main()
