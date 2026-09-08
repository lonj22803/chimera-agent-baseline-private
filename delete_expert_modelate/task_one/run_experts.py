#!/usr/bin/env python3
"""Inferencia: pasa uno o todos los casos por los tres expertos de la Tarea 1.

Produce, por caso, el panel completo que el deliberador posterior recibe:

* el veredicto de cada experto con su incertidumbre descompuesta y su tramo de
  fiabilidad;
* la proyección del PSA con su intervalo conforme y su tendencia;
* los dos ficheros que el reto exige (``prostate-biopsy-decision.json`` y
  ``prostate-biopsy-decision-reasoning.json``), rellenados por el experto que el
  panel designa como portavoz.

El portavoz **no** es una votación por mayoría. Es el experto de mayor
fiabilidad medida: entre los que están en el tramo más alto, gana el de mejor
AUC out-of-fold. La razón es que un promedio de dos expertos que leen las mismas
variables no es una segunda opinión —sus errores están correlacionados— y
promediarlos disfrazaría de consenso lo que es un único punto de vista. Cuando
ningún experto pasa de ``discuss``, el panel lo dice explícitamente y deja la
decisión abierta, que es lo que la escalera está para permitir.

Uso::

    python run_experts.py --case PT-pseudo_0020cfca66c8 --out ./salida
    python run_experts.py --all --out ./salida_todos
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import pandas as pd  # noqa: E402

from chimera_experts.expert_classifier import BiopsyExpert  # noqa: E402
from chimera_experts.io import Case, load_case, load_cases  # noqa: E402
from chimera_experts.psa_projector import PSAProjectorExpert  # noqa: E402

HERE = Path(__file__).resolve().parent
DEFAULT_DATA = HERE.parents[1] / "data_filtered" / "task1"

#: Orden de preferencia entre tramos de fiabilidad.
TIER_RANK = {"firm": 2, "supports": 1, "discuss": 0}


def load_panel(with_expert_two_block: bool = True):
    """Carga los tres expertos. Los que falten se omiten sin romper nada."""
    e2_path = HERE / "expert_two" / "model" / "expert_two_psa_projector.joblib"
    projector = PSAProjectorExpert.load(e2_path) if e2_path.exists() else None

    # El Experto 3 puede haberse entrenado con el bloque G (salida del Experto 2).
    # En ese caso hay que registrar el bloque antes de cargarlo.
    if projector is not None and with_expert_two_block:
        from chimera_experts.dataset import BLOCKS

        BLOCKS["G"] = ("expert_two_projection", lambda c: projector.features_for_fusion(c, 6.0))

    trace_path = HERE / "reasoning_model" / "model" / "reasoning_trace_model.joblib"
    trace_path = trace_path if trace_path.exists() else None

    # Orden de preferencia. La variante ABD del Experto 3 va antes que la
    # ABD+G porque la ablación la deja por delante (AUC 0.794 frente a 0.792, y
    # 0.811 frente a 0.802 con el envoltorio); la ABD+G sólo se usa si la otra
    # no está entrenada.
    classifiers = []
    for sub, fname in (("expert_one", "expert_one.joblib"), ("expert_three", "expert_three.joblib"),
                       ("expert_three", "expert_three_with_e2.joblib")):
        p = HERE / sub / "model" / fname
        if p.exists():
            e = BiopsyExpert.load(p, trace_model_path=trace_path)
            if not any(c.name == e.name for c in classifiers):
                classifiers.append(e)
    return classifiers, projector


def panel_for(case: Case, classifiers, projector, reports=None) -> dict:
    """Panel completo de un caso.

    ``reports`` permite pasar los informes ya calculados en lote, que es como
    ``--all`` los obtiene: pedirlos caso a caso multiplica por 195 el numero de
    imputaciones que hay que ejecutar.
    """
    if reports is None:
        reports = [e.report([case])[0] for e in classifiers]

    spokesman = None
    if reports:
        spokesman = max(
            reports,
            key=lambda r: (
                TIER_RANK[r.verdict.ladder],
                classifiers[reports.index(r)].metrics.get("cv_auc", 0.0),
            ),
        )

    experts = []
    for e, r in zip(classifiers, reports):
        payload = r.to_expert_payload()
        payload["validated_cv_auc"] = round(float(e.metrics.get("cv_auc", float("nan"))), 4)
        experts.append(payload)

    out = {
        "case_id": case.case_id,
        "task": 1,
        "available_sources": case.available_sources,
        "experts": experts,
        "psa_projection": projector.project(case, 6.0).to_dict() if projector is not None else None,
    }

    if spokesman is not None:
        agree = {r.to_chimera_decision() for r in reports}
        out["panel"] = {
            "spokesman": spokesman.expert,
            "decision": spokesman.to_chimera_decision(),
            "confidence": spokesman.verdict.confidence,
            "reliability_tier": spokesman.verdict.ladder,
            "unanimous": len(agree) == 1,
            "note": (
                "Todos los expertos coinciden."
                if len(agree) == 1
                else "Los expertos discrepan; el portavoz es el de mayor fiabilidad medida."
            )
            + (
                ""
                if spokesman.verdict.ladder != "discuss"
                else " Ningún experto supera el tramo 'discuss': la decisión debe apoyarse en la evidencia documental."
            ),
        }
    return out


def write_case(case: Case, out_dir: Path, classifiers, projector, reports=None) -> dict:
    """Escribe los ficheros del reto y el panel ampliado para un caso."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if reports is None:
        reports = [e.report([case])[0] for e in classifiers]
    p = panel_for(case, classifiers, projector, reports)

    idx = next((i for i, e in enumerate(classifiers) if p.get("panel") and e.name == p["panel"]["spokesman"]), None)
    if idx is not None:
        rep = reports[idx]
        (out_dir / "prostate-biopsy-decision.json").write_text(
            json.dumps(rep.to_chimera_decision()), encoding="utf-8"
        )
        (out_dir / "prostate-biopsy-decision-reasoning.json").write_text(
            json.dumps(rep.to_chimera_reasoning(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
    (out_dir / "expert-panel.json").write_text(json.dumps(p, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(DEFAULT_DATA))
    ap.add_argument("--case", default=None, help="un case_id concreto")
    ap.add_argument("--all", action="store_true", help="todos los casos de --data")
    ap.add_argument("--out", default=str(HERE / "outputs"))
    args = ap.parse_args()

    classifiers, projector = load_panel()
    if not classifiers:
        raise SystemExit("No hay expertos entrenados; ejecuta antes los train_expert_*.py")
    print("Expertos cargados:", ", ".join(f"{e.name} (AUC {e.metrics.get('cv_auc', float('nan')):.3f})" for e in classifiers))
    print("Proyector de PSA:", projector.champion if projector else "no disponible")

    out_root = Path(args.out)
    if args.all:
        cases = load_cases(args.data, task=1)
        # Un unico pase en lote por experto: ver la nota en _probability_matrix.
        batched = [e.report(cases) for e in classifiers]
        rows = []
        for i, c in enumerate(cases):
            p = write_case(c, out_root / c.case_id, classifiers, projector, [b[i] for b in batched])
            row = {"case_id": c.case_id, "decision": p["panel"]["decision"],
                   "confidence": p["panel"]["confidence"], "tier": p["panel"]["reliability_tier"],
                   "unanimous": p["panel"]["unanimous"]}
            for e in p["experts"]:
                row[f"{e['expert']}_p"] = e["probability"]
                row[f"{e['expert']}_tier"] = e["reliability_tier"]
            if p["psa_projection"]:
                row["psa_direction"] = p["psa_projection"]["direction"]
            rows.append(row)
        df = pd.DataFrame(rows)
        df.to_csv(out_root / "panel_summary.csv", index=False)
        print(f"\n{len(rows)} casos escritos en {out_root}")
        print(df["tier"].value_counts().to_string())
        print(f"\nunanimidad entre expertos: {df['unanimous'].mean():.1%}")
        n_lab = sum(1 for c in cases if c.has_label)
        if n_lab:
            print(
                f"\nAVISO: {n_lab} de estos casos tienen ground truth y forman parte del\n"
                "conjunto con el que se ajustaron los expertos. Comparar estas predicciones\n"
                "con sus etiquetas mide memorizacion, no rendimiento. Las cifras validas\n"
                "son las out-of-fold de train/artifacts y de los README."
            )
    else:
        if not args.case:
            raise SystemExit("Indica --case <id> o --all")
        c = load_case(args.data, args.case, task=1)
        p = write_case(c, out_root / c.case_id, classifiers, projector)
        print(json.dumps(p, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
