"""Puntuación con el evaluador OFICIAL, reutilizando ``dev/score_local.py``.

No se reimplementa ninguna métrica: se importa el ``evaluate.py`` de los
organizadores a través del script que el repositorio ya tiene. Si cambian los
pesos, esto cambia con ellos.

El juez de razonamiento queda **desactivado** (modo determinista y
reproducible). Ojo: apagarlo *redistribuye* los pesos —el grounding pasa de
0.05 a 0.175—, así que un número de aquí no es comparable con uno de
leaderboard. Sí lo es entre corridas medidas igual, que es para lo que se usa.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("USE_RATIONALE_JUDGE", "0")

REPO = Path(__file__).resolve().parents[3]
SCORE_LOCAL = REPO / "dev" / "score_local.py"
EVAL_REPO = Path.home() / "PycharmProjects" / "CHIMERA-agent-eval"

_sl: Any = None
_ev: Any = None


def _load():
    global _sl, _ev
    if _sl is None:
        spec = importlib.util.spec_from_file_location("chimera_score_local", SCORE_LOCAL)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["chimera_score_local"] = mod
        spec.loader.exec_module(mod)
        _sl = mod
        _ev = mod.load_evaluator(EVAL_REPO)
    return _sl, _ev


def score(output_root: Path | str, split: str = "all", count_missing: bool = True) -> dict[str, Any]:
    """Agregados oficiales de la tarea 1 para un directorio ``.../output``.

    ``output_root`` es el que contiene ``task1/<case_id>/``. ``split`` puede ser
    ``all``, ``dev`` o ``val``. ``count_missing=True`` puntúa como fallo el caso
    etiquetado sin predicción, que es lo que hace Grand Challenge.
    """
    sl, ev = _load()
    wanted = sl.read_split(REPO / "dev" / "splits", 1, split)
    agg = sl.score_task(ev, REPO / "data", Path(output_root), 1, wanted, count_missing)
    return agg or {}


def per_case(agg: dict[str, Any]) -> dict[str, dict]:
    """Filas por caso indexadas por ``case_id`` (incluye los componentes)."""
    out = {}
    for row in agg.get("_rows", []):
        cid = row.get("case_id") or row.get("pid") or row.get("id")
        if cid:
            out[cid] = row
    return out


def summarise(agg: dict[str, Any]) -> dict[str, Any]:
    """Los números que se comparan entre corridas."""
    rows = agg.get("_rows", [])
    passed = [r for r in rows if r.get("decision_score") == 1.0]

    def mean_of(key: str) -> float | None:
        vals = [r[key] for r in passed if r.get(key) is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    return {
        "n": agg.get("_scored", 0) + agg.get("_missing", 0),
        "n_missing": agg.get("_missing", 0),
        "ranking_score": round(agg["ranking_score"], 4) if agg.get("ranking_score") is not None else None,
        "mean_case_score": round(agg["mean_case_score"], 4) if agg.get("mean_case_score") is not None else None,
        "decision_gate": round(len(passed) / len(rows), 4) if rows else None,
        "f1_yes": round(agg["decision_f1_yes"], 4) if agg.get("decision_f1_yes") is not None else None,
        "variable_weight_score": mean_of("variable_weight_score"),
        "confidence_score": mean_of("confidence_score"),
        "important_decisive_factor_score": mean_of("important_decisive_factor_score"),
        "section_grounding_score": mean_of("section_grounding_score"),
        "tool_score": mean_of("tool_score"),
    }
