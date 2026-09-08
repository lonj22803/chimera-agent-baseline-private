"""Inferencia: el panel de expertos de la tarea 2 sobre uno o todos los casos.

Produce por caso los dos ficheros que el reto exige —
``prostate-treatment-decision.json`` y
``prostate-treatment-decision-reasoning.json``— y un tercero,
``expert-panel.json``, que no es para el reto sino para la junta: lleva la
distribución de cada experto sobre las cuatro conductas, su incertidumbre
descompuesta, su tramo de fiabilidad y, en el caso de la cascada, las tres
respuestas intermedias por separado.

Ese tercer fichero es el que hace que la junta pueda deliberar en lugar de
votar. Un experto que sólo dice ``active_treatment`` no se puede rebatir; uno
que dice *«tratar con margen 0.11 ± 0.19 sobre vigilancia, porque el nodo de
grado da 0.78 y el de aptitud 0.91»* sí.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "delete_expert_modelate"))

from chimera_experts import dataset_task2 as d2  # noqa: E402
from chimera_experts import io  # noqa: E402
from chimera_experts.uncertainty_multiclass import make_verdict  # noqa: E402

DATA = ROOT / "data" / "task2"
HERE = Path(__file__).resolve().parent

#: Los expertos que se cargan si están entrenados. Un experto ausente no rompe
#: el panel: se anota como no disponible, que es información para la junta.
EXPERTS = {
    "expert_one": HERE / "expert_one" / "model" / "expert_one.joblib",
    "expert_two": HERE / "expert_two" / "model" / "expert_two.joblib",
    "expert_three": HERE / "expert_three" / "model" / "expert_three.joblib",
    "expert_four": HERE / "expert_four" / "model" / "expert_four.joblib",
    "expert_five": HERE / "expert_five" / "model" / "expert_five.joblib",
}
REASONING = HERE / "reasoning_model" / "model" / "reasoning_task2.joblib"


def load_bundle(path: Path):
    return joblib.load(path) if path.exists() else None


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


def run_case(case, bundles: dict, reasoning, projector) -> dict:
    panel = {"case_id": case.case_id, "experts": {}, "available_sources": case.available_sources}
    comp = float(d2.completeness_vector([case])[0])

    for name, bundle in bundles.items():
        if bundle is None:
            panel["experts"][name] = {"available": False}
            continue
        X = align(case, bundle, projector)
        model = bundle["model"]
        if hasattr(model, "probability_tensor"):
            T = model.probability_tensor(X)[0]
        else:
            T = model.predict_proba(X)[None, ...]
        verdict = make_verdict(T, d2.CLASSES, comp)
        entry = verdict.to_dict()
        entry["available"] = True
        entry["role"] = bundle.get("role", name)
        entry["loo_accuracy"] = bundle.get("loo_accuracy")
        if hasattr(model, "node_probabilities"):
            entry["nodes"] = {k: float(v[0]) for k, v in model.node_probabilities(X).items()}
        panel["experts"][name] = entry

    panel["spokesperson"] = elect(panel["experts"])
    trace = reasoning.predict_trace(case) if reasoning is not None else {
        "confidence": "clear", "variable_weights": {}, "reveal_sequence": []
    }
    return panel, trace


def elect(experts: dict) -> dict:
    """El portavoz no es la mayoría: es el experto de mayor fiabilidad medida.

    Entre los que alcanzan el tramo más alto, gana el de mejor acierto
    leave-one-out. Promediar expertos que leen las mismas variables no es una
    segunda opinión —sus errores están correlacionados— y disfrazaría de
    consenso un único punto de vista. Si ninguno pasa de ``discuss``, el panel
    lo dice y deja la decisión abierta: para eso existe la escalera.
    """
    avail = [(k, v) for k, v in experts.items() if v.get("available")]
    if not avail:
        return {"expert": None, "decision": None, "reason": "ningún experto disponible"}
    for rung in ("firm", "supports", "discuss"):
        tier = [(k, v) for k, v in avail if v["ladder"] == rung]
        if tier:
            k, v = max(tier, key=lambda kv: kv[1].get("loo_accuracy") or 0.0)
            return {"expert": k, "decision": v["decision"], "ladder": rung,
                    "margin": v["margin"], "confidence": v["confidence"],
                    "open": rung == "discuss",
                    "reason": f"tramo {rung}, mejor acierto LOO del tramo"}
    return {"expert": None, "decision": None, "reason": "sin tramo asignable"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", default=str(HERE / "outputs"))
    args = ap.parse_args()

    from chimera_experts import features_wsi

    all_cases = io.load_cases(DATA, task=2)
    projector = features_wsi.EmbeddingProjector(8).fit(all_cases)
    bundles = {k: load_bundle(p) for k, p in EXPERTS.items()}
    reasoning = load_bundle(REASONING)

    targets = all_cases if args.all else [c for c in all_cases if c.case_id == args.case]
    if not targets:
        raise SystemExit(f"caso no encontrado: {args.case}")

    out_root = Path(args.out)
    for case in targets:
        panel, trace = run_case(case, bundles, reasoning, projector)
        d = out_root / case.case_id
        d.mkdir(parents=True, exist_ok=True)
        decision = panel["spokesperson"]["decision"] or "active_surveillance"
        (d / "prostate-treatment-decision.json").write_text(json.dumps(decision), encoding="utf-8")
        (d / "prostate-treatment-decision-reasoning.json").write_text(
            json.dumps({**trace, "free_text": free_text(case, panel)}, indent=2, ensure_ascii=False), encoding="utf-8")
        (d / "expert-panel.json").write_text(json.dumps(panel, indent=2, ensure_ascii=False, default=float),
                                             encoding="utf-8")
    print(f"{len(targets)} casos -> {out_root}")


def free_text(case, panel: dict) -> str:
    """Texto libre con cifras **del caso**, nunca inventadas.

    El reto penaliza los hallazgos no respaldados, así que aquí sólo entran
    valores que están en ``structured-prompt.json`` y la salida del panel.
    """
    p = case.prompt or {}
    sp = panel["spokesperson"]
    bits = [
        f"ISUP grade group {p.get('bx_isup')}, Gleason {p.get('bx_gl_prim')}+{p.get('bx_gl_sec')}",
        f"PI-RADS {p.get('pirads')}", f"PSA {p.get('psa')} ng/mL", f"PSA density {p.get('psad')}",
        f"clinical stage {p.get('ct')}", f"age {p.get('age')}",
    ]
    tail = ""
    if sp.get("open"):
        tail = " Panel margin does not separate the two leading options; decision left open for deliberation."
    return "; ".join(bits) + f". Panel recommends {sp.get('decision')}." + tail


if __name__ == "__main__":
    main()
