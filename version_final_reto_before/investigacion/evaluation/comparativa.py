"""Comparativa final: `result_v2` contra H0, B0 y todos los experimentos.

Puntúa las salidas reales de la cobertura de V2_2 con el evaluador oficial y las
pone al lado de las referencias de E00 y de los veredictos de E01–E07.

Aviso que hay que leer antes que la tabla: la cobertura es **contrato, no
calidad**. Incluye los 423 casos, pero sólo 91/72/75 tienen etiqueta, y los
expertos de T1 y T2 se ajustaron sobre esas mismas cohortes. Ninguna cifra de
aquí es una estimación fuera de muestra.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
AQUI = Path(__file__).resolve().parent
RESULT = RAIZ / "result_v2"
PESOS = {1: 0.4, 2: 0.4, 3: 0.2}


def main() -> None:
    sys.path.insert(0, str(RAIZ))
    from version_final_reto.investigacion.evaluation.referencias import (
        cargar_evaluador, puntuar, EVAL_POR_DEFECTO, SALIDAS)
    from dev.score_with_judge import load_predictions
    ev = cargar_evaluador(EVAL_POR_DEFECTO)

    e00 = json.loads((AQUI / "reports" / "e00_referencias.json").read_text())
    r = {"alcance": "Comparativa de result_v2 contra H0/B0 y los experimentos E01-E07",
         "aviso": ("Cobertura = contrato, no calidad. 423 casos ejecutados; sólo 91/72/75 "
                   "tienen etiqueta y son los que se puntúan. Los expertos de T1/T2 se "
                   "ajustaron sobre esas mismas cohortes: dentro de muestra."),
         "aviso_memoria": ("Esta corrida usa el tope de 19 GiB de la V1.1 (pico 21 502 MiB), NO el "
                           "perfil de 16 GB. Es deliberado: el perfil se valida con la compuerta sin "
                           "montar de ../version_final_reto.runtime_16gb/, y un lote caliente de 195 "
                           "casos en un proceso no reproduce el arranque frío por paciente de Grand "
                           "Challenge. No leer esta cobertura como validación del perfil."),
         "v2_2": {}, "H0": {}, "B0": {}, "deltas": {}}

    for tarea in (1, 2, 3):
        # T1 y T2 separan `labeled/` y `unlabeled/`; sólo los etiquetados se
        # pueden puntuar. T3 escribe directamente bajo `output/`.
        base = RESULT / f"task_{tarea}"
        salida = base / "labeled" / "output"
        if not salida.is_dir():
            salida = base / "output"
        preds = load_predictions(salida, RAIZ / f"data/task{tarea}", tarea)
        if not preds:
            r["v2_2"][f"task{tarea}"] = {"error": f"sin salidas en {salida}"}
            continue
        ag = puntuar(ev, preds, tarea)["agregado"]
        r["v2_2"][f"task{tarea}"] = ag
        r["H0"][f"task{tarea}"] = e00["H0"][f"task{tarea}"]
        r["B0"][f"task{tarea}"] = e00["B0"][f"task{tarea}"]

    for et in ("v2_2", "H0", "B0"):
        vals = [r[et].get(f"task{t}", {}).get("ranking_score") for t in (1, 2, 3)]
        if all(v is not None for v in vals):
            r[et]["overall_ranking_score"] = sum(PESOS[t] * v for t, v in zip((1, 2, 3), vals))

    if "overall_ranking_score" in r["v2_2"]:
        for ref in ("H0", "B0"):
            r["deltas"][f"v2_2_menos_{ref}"] = round(
                r["v2_2"]["overall_ranking_score"] - r[ref]["overall_ranking_score"], 5)

    # Veredictos de los experimentos, para tenerlo todo en un sitio.
    r["experimentos"] = {}
    for nombre in ("e01_extraccion", "e02_panel_t2", "e03_consultas", "e04_conceptos",
                   "e05_mapa_t3", "e06_e07_supervivencia"):
        f = AQUI / "reports" / f"{nombre}.json"
        if f.exists():
            r["experimentos"][nombre] = json.loads(f.read_text())

    destino = RESULT / "comparativa.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(r, indent=2, ensure_ascii=False))

    print(f"{'referencia':12} {'T1':>9} {'T2':>9} {'T3':>9} {'OVERALL':>9}")
    for et in ("H0", "B0", "v2_2"):
        vals = [r[et].get(f"task{t}", {}).get("ranking_score") for t in (1, 2, 3)]
        linea = " ".join(f"{v:9.5f}" if isinstance(v, float) else f"{'—':>9}" for v in vals)
        ov = r[et].get("overall_ranking_score")
        print(f"{et:12} {linea} {ov:9.5f}" if ov is not None else f"{et:12} {linea}")
    for k, v in r["deltas"].items():
        print(f"\n{k}: {v:+.5f}")
    print(f"\nescrito {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
