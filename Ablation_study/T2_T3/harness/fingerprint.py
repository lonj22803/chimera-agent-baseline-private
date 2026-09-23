"""Congela la huella de V4 y los anclajes ejecutables de T2/T3."""

from __future__ import annotations

import hashlib
import json
import subprocess

from Ablation_study.harness.baseline import write_fingerprint

from .evaluator import write_json
from .paths import RESULTS, ROOT, STUDY, ensure_dirs


def main() -> None:
    ensure_dirs()
    fingerprint = RESULTS / "huella_v4_inicio.txt"
    write_fingerprint(fingerprint)
    reference_candidates = (
        ROOT / "Ablation_study" / "results" / "huella_v4_cierre.txt",
        ROOT / "Ablation_study" / "results" / "huella_v4.txt",
    )
    reference = next((path for path in reference_candidates if path.is_file()), None)
    prereg = STUDY / "PREREGISTRO.md"
    result = {
        "branch": subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=ROOT, text=True
        ).strip(),
        "preregistro_sha256": hashlib.sha256(prereg.read_bytes()).hexdigest(),
        "fingerprint_sha256": hashlib.sha256(fingerprint.read_bytes()).hexdigest(),
        "reference": str(reference.relative_to(ROOT)) if reference else None,
        "v4_matches_t1_close": bool(reference and reference.read_bytes() == fingerprint.read_bytes()),
    }
    write_json(RESULTS / "congelacion.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
