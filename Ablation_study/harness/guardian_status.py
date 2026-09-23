"""Escribe el estado observable del guardian de forma atomica."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json

from .paths import RESULTS


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("state", choices=("running", "complete", "failed"))
    parser.add_argument("stage")
    parser.add_argument("message", nargs="?", default="")
    args = parser.parse_args()
    path = RESULTS / "guardian_status.json"
    temporary = path.with_suffix(".tmp")
    previous = {}
    if path.is_file():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = {}
    payload = {
        "started_at": previous.get("started_at") or datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "state": args.state,
        "stage": args.stage,
        "message": args.message,
    }
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
