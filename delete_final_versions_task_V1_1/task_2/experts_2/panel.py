"""Panel desplegado de tarea 2; precálculo en lote y evaluación en vivo.

Los modelos usan sklearn/joblib ya instalados. Las clases históricas se
resuelven desde common, nunca desde los directorios originales.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
COMMON = HERE.parents[1] / "common"
if str(COMMON) not in sys.path:
    sys.path.insert(0, str(COMMON))
from chimera_experts import dataset_task2 as d2, io
from chimera_experts.uncertainty_multiclass import make_verdict
from chimera_experts.reasoning_task2 import gate_target, GATED_VARIABLES
from delete_final_versions_task_V1_1.common import serial_predict
from delete_final_versions_task_V1_1.common.vocab import case_values, variable_block
from chimera_agent_baseline.output.schema import TASK2_VARIABLES

DATA = ROOT / "data" / "task2"
CACHE = HERE / "artifacts" / "panel_cache.json"
EXPERTS = {f"expert_{n}": HERE / "model" / f"expert_{n}.joblib"
           for n in ("one", "two", "three", "four", "five")}
REASONING = HERE / "model" / "reasoning_task2.joblib"
PROJECTOR = HERE / "model" / "embedding_projector.joblib"
REPLICAS = {"expert_two": "expert_one", "expert_four": "expert_one"}


def load_bundle(path):
    return joblib.load(path)


def align(case, bundle: dict, projector) -> np.ndarray:
    """Vector del caso con **exactamente** las columnas del entrenamiento.

    ``build_matrix`` poda columnas sin varianza y demasiado dispersas, y esa
    poda se calcula sobre la cohorte que recibe. Llamarla con un solo caso
    dejaría casi todas las columnas fuera —una sola fila no tiene varianza— y
    el vector no encajaría con el modelo. Aquí se construye sin podar y se
    reordena por ``feature_names``, que es el contrato que el experto guardó.
    Una variable que el caso no trae queda NaN, y de ahí sale la incertidumbre
    por datos ausentes en vez de un error.
    """
    X, names = d2.build_matrix([case], bundle["blocks"], projector=projector, drop_constant=False)
    index = {n: j for j, n in enumerate(names)}
    wanted = bundle["feature_names"]
    out = np.full((1, len(wanted)), np.nan)
    for j, n in enumerate(wanted):
        if n in index:
            out[0, j] = X[0, index[n]]
    return out


def constant_trace(case, reasoning):
    """Compuerta 1.2: sólo constantes, con la puerta de grado medida."""
    weights = {v: reasoning.weight_mode[v] if v not in GATED_VARIABLES or gate_target(case)
               else 'not_used' for v in TASK2_VARIABLES}
    return {"confidence": reasoning.confidence_mode,
            "variable_weights": weights, "reveal_sequence": []}


def elect(experts):
    available = [(k, v) for k, v in experts.items()
                 if v.get("available") and k not in REPLICAS]
    for rung in ("firm", "supports", "discuss"):
        tier = [(k, v) for k, v in available if v["ladder"] == rung]
        if tier:
            k, v = max(tier, key=lambda kv: kv[1].get("loo_accuracy") or 0.0)
            return {"expert": k, "decision": v["decision"], "ladder": rung,
                    "open": rung == "discuss",
                    "scope": "Deployed; expert_three's historical 3 spokesperson cases are in-sample."}
    raise RuntimeError("Ningún experto disponible")


def run_cases(cases, bundles, reasoning, projector):
    """Un pase por experto sobre todas las filas; mismas columnas que align."""
    if not cases:
        return {}
    panels = {c.case_id: {"case_id": c.case_id, "experts": {},
              "available_sources": c.available_sources,
              "trace": constant_trace(c, reasoning), "mode": "deployed"} for c in cases}
    completeness = d2.completeness_vector(cases)
    for name, bundle in bundles.items():
        if bundle is None:
            raise RuntimeError(f"Falta el experto requerido: {name}")
        X = np.vstack([align(c, bundle, projector) for c in cases])
        model = bundle["model"]
        tensors = (model.probability_tensor(X) if hasattr(model, "probability_tensor")
                   else model.predict_proba(X)[:, None, None, :])
        nodes = model.node_probabilities(X) if hasattr(model, "node_probabilities") else {}
        for i, c in enumerate(cases):
            entry = make_verdict(tensors[i], d2.CLASSES, float(completeness[i])).to_dict()
            # La traducción histórica de peldaño no se publica como confianza validada.
            entry["rung_confidence_unvalidated"] = entry.pop("confidence")
            trace = panels[c.case_id]["trace"]
            entry.update(available=True, role=bundle.get("role", name),
                         loo_accuracy=bundle["loo_accuracy"],
                         ladder_protocol=bundle.get("ladder_protocol", "leave_one_out"),
                         replica_of=REPLICAS.get(name), voting_voice=name not in REPLICAS,
                         confidence=trace["confidence"], variable_weights=trace["variable_weights"],
                         variable_policy="moda; form baseline, not model attribution")
            if nodes:
                entry["nodes"] = {k: float(v[i]) for k, v in nodes.items()}
            values = case_values(c.prompt, task=2)
            values["fh"] = str(c.clinical.get("family_history") or "not recorded")
            entry["turn"] = (
                f"{name}: {entry['decision']}; margin {entry['margin']:.4f}.\n" +
                variable_block(trace["variable_weights"], values, trace["confidence"],
                               "constant baseline; confidence_from_rung was not measurable",
                               task=2, scope="form baseline, not model attribution"))
            panels[c.case_id]["experts"][name] = entry
    for panel in panels.values():
        panel["spokesperson"] = elect(panel["experts"])
    return panels


def run_case(case, bundles, reasoning, projector):
    panel = run_cases([case], bundles, reasoning, projector)[case.case_id]
    return panel, panel["trace"]


#: Los 329 MB de bosques se desunpicklan una vez por proceso. En Grand Challenge
#: eso es una vez por caso, y es el tramo más caro del arranque después de vLLM:
#: 16,5 s medidos aquí. Memoizarlo permite que ``warmup`` lo arranque en un hilo
#: mientras carga el modelo y que la junta se lo encuentre hecho.
_LIVE = None


def _live_models():
    global _LIVE
    if _LIVE is None:
        live = {"bundles": {k: load_bundle(p) for k, p in EXPERTS.items()},
                "reasoning": load_bundle(REASONING), "projector": load_bundle(PROJECTOR)}
        # Entrenados con n_jobs=-1; puntuando una fila eso es sólo coste de pool.
        serial_predict.serialize_bundles(live["bundles"])
        _LIVE = live
    return _LIVE


def build_cache(data_root=DATA, out=CACHE):
    cases = io.load_cases(Path(data_root), task=2)
    live = _live_models()
    data = {"mode": "deployed", "cases": run_cases(cases, **live),
            "replicas": REPLICAS, "confidence_policy": "constant"}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    return data


class Panel:
    def __init__(self, path=CACHE):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {"cases": {}}
        self.cases = self.data["cases"]
        self._live = None

    def has(self, case_id):
        return case_id in self.cases

    def ensure(self, case_id, case_files):
        if self.has(case_id):
            return False
        if self._live is None:
            self._live = _live_models()
        case = io.Case(case_id=case_id, task=2, prompt=case_files.get("prompt") or {},
                       clinical=case_files.get("clinical") or {},
                       embeddings={k: v for k, v in (case_files.get("features") or {}).items()
                                   if isinstance(v, list)})
        self.cases[case_id] = run_cases([case], **self._live)[case_id]
        return True

    def verdicts(self, case_id, mode="deployed"):
        if mode != "deployed":
            raise ValueError("Sólo deployed: no hay veredictos LOO completos para modo honest")
        return self.cases[case_id]


def main():
    ap = argparse.ArgumentParser(description="Precalcula los cinco expertos sin reentrenar")
    ap.add_argument("--data", type=Path, default=DATA)
    ap.add_argument("--out", type=Path, default=CACHE)
    args = ap.parse_args()
    result = build_cache(args.data, args.out)
    print(f"{len(result['cases'])} casos -> {args.out}")


if __name__ == "__main__":
    main()
