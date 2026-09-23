"""Estado atomico y legible del guardian T2/T3."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

from .paths import RESULTS, ensure_dirs


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("uso: guardian_status ESTADO ETAPA [DETALLE]")
    ensure_dirs()
    payload = {
        "status": sys.argv[1],
        "stage": sys.argv[2],
        "detail": sys.argv[3] if len(sys.argv) > 3 else "",
        "pid": os.getpid(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    temporary = RESULTS / "guardian_status.tmp"
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(RESULTS / "guardian_status.json")


if __name__ == "__main__":
    main()
