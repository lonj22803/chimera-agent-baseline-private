"""Comprueba las invariantes de cierre y registra las suites de la V4."""

from __future__ import annotations

from datetime import date
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

from .baseline import ROOT, write_fingerprint
from .paths import RESULTS, V4_ROOT

BASELINE = RESULTS / "tests_base.json"
FINGERPRINT = RESULTS / "huella_v4.txt"
CLOSING_FINGERPRINT = RESULTS / "huella_v4_cierre.txt"
RESULT = RESULTS / "cierre.json"
DOCUMENTED_EXCEPTIONS = {".dockerignore", "resources/guidelines_db/chroma.sqlite3"}


def _counts(output: str) -> tuple[int, int, int]:
    passed = sum(int(value) for value in re.findall(r"(\d+) passed", output))
    failed = sum(int(value) for value in re.findall(r"(\d+) failed", output))
    warnings = sum(int(value) for value in re.findall(r"(\d+) warnings?", output))
    return passed, failed, warnings


def _run_suite_once(path: str) -> dict[str, Any]:
    target = ROOT / path
    if not target.exists():
        return {"path": path, "status": "missing", "passed": 0, "failed": 0}
    command = [
        str(ROOT / ".venv" / "bin" / "python"),
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        path,
    ]
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    process = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    passed, failed, warnings = _counts(process.stdout)
    return {
        "path": path,
        "status": "passed" if process.returncode == 0 else "failed",
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "returncode": process.returncode,
        "tail": "\n".join(process.stdout.splitlines()[-12:]),
    }


def _run_suite(path: str) -> dict[str, Any]:
    first = _run_suite_once(path)
    if path != "version_final_reto_send_v4/common/tests" or first["status"] != "failed":
        return first
    second = _run_suite_once(path)
    second["retried_after_failure"] = True
    second["first_attempt"] = {
        "passed": first["passed"],
        "failed": first["failed"],
        "returncode": first["returncode"],
        "tail": first["tail"],
    }
    return second


def _git_paths() -> list[str]:
    output = subprocess.check_output(
        ["git", "status", "--short", "--untracked-files=all"], cwd=ROOT, text=True
    )
    paths = []
    for line in output.splitlines():
        value = line[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths.append(value)
    return paths


def run() -> dict[str, Any]:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    suites = [_run_suite(row["path"]) for row in baseline["suites"]]
    study = _run_suite("Ablation_study/ablacion_tests")

    with tempfile.NamedTemporaryFile(dir=RESULTS, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        write_fingerprint(temporary)
        current = temporary.read_bytes()
    finally:
        temporary.unlink(missing_ok=True)
    CLOSING_FINGERPRINT.write_bytes(current)
    reference = FINGERPRINT.read_bytes()

    expected = {row["path"]: row for row in baseline["suites"]}
    same_tests = all(
        row["status"] == expected[row["path"]]["status"]
        and row["passed"] == expected[row["path"]]["passed"]
        and row["failed"] == expected[row["path"]]["failed"]
        for row in suites
    )
    paths = _git_paths()
    unexpected = sorted(
        path
        for path in paths
        if not path.startswith("Ablation_study/") and path not in DOCUMENTED_EXCEPTIONS
    )
    supervisor = V4_ROOT / "common" / "tests" / "test_supervisor.py"
    payload = {
        "date": date.today().isoformat(),
        "v4_intacta": current == reference,
        "fingerprint_reference": str(FINGERPRINT.relative_to(ROOT)),
        "fingerprint_closing": str(CLOSING_FINGERPRINT.relative_to(ROOT)),
        "suites_match_baseline": same_tests,
        "suites": suites,
        "study_suite": study,
        "git_status_paths": paths,
        "documented_exceptions": sorted(DOCUMENTED_EXCEPTIONS & set(paths)),
        "unexpected_paths_outside_study": unexpected,
        "tree_scope_ok": not unexpected,
        "operational_layer": {
            "classification": "OPERATIVA",
            "supervisor_test_present": supervisor.is_file(),
            "touched_by_study": any(path.startswith("version_final_reto_send_v4/") for path in paths),
        },
    }
    payload["complete"] = bool(
        payload["v4_intacta"]
        and same_tests
        and study["status"] == "passed"
        and payload["tree_scope_ok"]
        and payload["operational_layer"]["supervisor_test_present"]
        and not payload["operational_layer"]["touched_by_study"]
    )
    RESULT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    payload = run()
    print(
        json.dumps(
            {
                "complete": payload["complete"],
                "v4_intacta": payload["v4_intacta"],
                "suites_match_baseline": payload["suites_match_baseline"],
                "study_passed": payload["study_suite"]["passed"],
            },
            sort_keys=True,
        )
    )
    return 0 if payload["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
