"""Comprueba huella, corridas y pruebas al cierre."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile

from Ablation_study.harness.baseline import write_fingerprint

from .paths import RESULTS, ROOT, STUDY
from .evaluator import write_json

SUITES = (
    "Ablation_study/T2_T3/tests",
    "version_final_reto_send_v4/task_2/agent/tests",
    "version_final_reto_send_v4/task_2/experts_2/tests",
    "version_final_reto_send_v4/task_3/agent/tests",
)


def _suite(path: str) -> dict:
    process = subprocess.run(
        [str(ROOT / ".venv/bin/python"), "-m", "pytest", "-q", "-p", "no:cacheprovider", path],
        cwd=ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "path": path,
        "passed": process.returncode == 0,
        "returncode": process.returncode,
        "tail": "\n".join(process.stdout.splitlines()[-12:]),
    }


def main() -> None:
    initial = RESULTS / "huella_v4_inicio.txt"
    with tempfile.NamedTemporaryFile(dir=RESULTS, delete=False) as stream:
        closing = RESULTS / stream.name.split("/")[-1]
    try:
        write_fingerprint(closing)
        current = closing.read_bytes()
    finally:
        closing.unlink(missing_ok=True)
    (RESULTS / "huella_v4_cierre.txt").write_bytes(current)
    prereg = STUDY / "PREREGISTRO.md"
    frozen = json.loads((RESULTS / "congelacion.json").read_text())
    suites = [_suite(path) for path in SUITES]
    runs = json.loads((RESULTS / "D_F_effects.json").read_text())
    judge = json.loads((RESULTS / "J_session_validation.json").read_text())
    payload = {
        "v4_intacta": initial.read_bytes() == current,
        "preregistro_intacto": hashlib.sha256(prereg.read_bytes()).hexdigest() == frozen["preregistro_sha256"],
        "runs_accepted": runs["accepted"],
        "judge_complete": judge["complete"],
        "suites": suites,
    }
    payload["complete"] = all((
        payload["v4_intacta"], payload["preregistro_intacto"], payload["runs_accepted"],
        payload["judge_complete"], all(item["passed"] for item in suites),
    ))
    write_json(RESULTS / "cierre.json", payload)
    print(json.dumps({key: value for key, value in payload.items() if key != "suites"}, indent=2))
    if not payload["complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
