"""Carga estable del evaluador oficial y utilidades de serializacion."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from .paths import EVAL_REPO


def load_evaluator():
    os.environ.setdefault("USE_RATIONALE_JUDGE", "0")
    evaluation = EVAL_REPO / "evaluation"
    if not (evaluation / "evaluate.py").is_file():
        raise FileNotFoundError(f"No se encontro el evaluador oficial en {evaluation}")
    if str(evaluation) not in sys.path:
        sys.path.insert(0, str(evaluation))
    import evaluate  # noqa: PLC0415

    return evaluate


def json_ready(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_ready(value), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
