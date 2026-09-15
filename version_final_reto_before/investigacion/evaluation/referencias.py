"""E00 — H0 y B0, las dos referencias del PLAN §3. Sin esto no se compara nada.

**H0, referencia histórica.** V1 exacta, sus JSON y sus limitaciones. Sirve para
comprobar reproducción, no para atribuir cada variación a aprendizaje.

**B0, referencia operativa verificable.** V1 congelada con las lecturas
**realmente hechas** declaradas. El PLAN es tajante: «Los cambios necesarios
para que la traza describa la ejecución se publican como correcciones, aunque
bajen el score».

Y bajan. En los 72 casos de T2 el histórico declara ``reveal_sequence: []``
mientras el protocolo abre seis secciones. Declarar la verdad cuesta puntos de
`tool_score` y los recupera en `section_grounding`. La salida no es seguir
ocultando consultas: es medir contra una base honesta.

Se puntúa siempre con el evaluador oficial importado, con el juez apagado:
apagarlo cambia los pesos, así que H0 y B0 se comparan entre sí, nunca contra
una cifra obtenida con juez.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
AQUI = Path(__file__).resolve().parent
# Artefactos históricos congelados dentro de este directorio. Antes vivían en
# `version_final_reto/investigacion/referencias_historicas/` y `delete_final_versions_task_V1/`,
# que ya no existen en `main`: al limpiar el repositorio se copiaron aquí para
# que E00 siga siendo reproducible sin depender de árboles borrados. Son 5,4 MB.
HISTORICO = Path(__file__).resolve().parent.parent / "referencias_historicas"
EVAL_POR_DEFECTO = RAIZ.parent / "CHIMERA-agent-eval"

# Rutas resueltas por E00. NO son las que uno elegiría por el nombre, y esa es
# justo la discrepancia que el PLAN manda resolver antes de optimizar:
#
#   T1 y T2  -> el árbol histórico y el de cobertura de V1 daban EL MISMO
#               ranking (0,83903 y 0,77839). V1 no cambió esas dos salidas.
#   T3       -> la corrida de cobertura de V1 daba 0,73717, no el 0,88319 que
#               documenta. Motivo comprobado: `task_3/agent/protocol.py` cambió
#               DESPUÉS de esa corrida —uno de 6 ficheros de 126 cuyo hash
#               difería del árbol congelado—. La cobertura llevaba el portavoz
#               viejo; lo entregado es `t3_adoptado`, que es lo copiado aquí.
#               Y 0,73717 es exactamente el `baseline_c_index` de
#               `survival_total.json`.
SALIDAS = {
    1: HISTORICO / "H0_task1",
    2: HISTORICO / "H0_task2",
    3: HISTORICO / "H0_task3",
}

# T3 tiene tres cifras que no se deben mezclar (PLAN §3 y EVIDENCIA §1).
T3_CIFRAS = {
    "desplegado_dentro_de_muestra": 0.88319,
    "anidado_fuera_de_muestra": 0.8234513274336284,
    "portavoz_anterior": 0.7371681415929203,
    "time_score_anidado": 0.7120625469090819,
}

PESOS_OVERALL = {1: 0.4, 2: 0.4, 3: 0.2}


def cargar_evaluador(repo: Path):
    os.environ["USE_RATIONALE_JUDGE"] = "0"
    d = repo / "evaluation"
    if not (d / "evaluate.py").exists():
        sys.exit(f"No encuentro el evaluador en {d}")
    sys.path.insert(0, str(d))
    import evaluate as ev
    mapping = d / "ground_truth" / "section_variable_mapping.json"
    ev.SECTION_MAPPING_FILE = mapping
    ev._SECTION_VAR_MAPPING = None
    return ev


def lecturas_reales(tarea: int) -> dict[str, list[str]]:
    """`revealed` del `summary.jsonl` histórico: lo que el protocolo abrió de verdad."""
    f = HISTORICO / f"summary_task{tarea}.jsonl"
    salida = {}
    if not f.exists():
        return salida
    for linea in f.read_text().splitlines():
        if not linea.strip():
            continue
        fila = json.loads(linea)
        reveladas = fila.get("revealed")
        if reveladas is not None:
            # Deduplicado conservando orden: el contrato pide secciones
            # consultadas, no un recuento de accesos.
            vistas, orden = set(), []
            for s in reveladas:
                if s not in vistas:
                    vistas.add(s); orden.append(s)
            salida[fila["case_id"]] = orden
    return salida


def puntuar(ev, predicciones: dict, tarea: int) -> dict:
    gts = ev.load_ground_truth_records(RAIZ / f"data/task{tarea}" / "ground_truth", f"task{tarea}")
    filas = []
    for gt in gts:
        cid = ev.get_case_id(gt)
        pred = predicciones.get(cid)
        if tarea == 3:
            filas.append(ev.evaluate_recurrence_case(gt, pred, None))
        else:
            filas.append(ev.evaluate_case(gt, pred, None, None))
    ag = ev.compute_aggregate_metrics(filas)
    return {"agregado": {k: v for k, v in ag.items() if k != "decision_classification_report"},
            "filas": [{k: v for k, v in f.items() if not k.startswith("_")} for f in filas]}


def construir(repo_eval: Path = EVAL_POR_DEFECTO) -> dict:
    ev = cargar_evaluador(repo_eval)
    sys.path.insert(0, str(RAIZ))
    from dev.score_with_judge import load_predictions

    resultado = {
        "alcance": "E00: reproducción de H0 y construcción de B0, juez apagado",
        "evaluador_sha256": hashlib.sha256(
            (repo_eval / "evaluation/evaluate.py").read_bytes()).hexdigest(),
        "H0": {}, "B0": {}, "correcciones": {},
    }

    for tarea in (1, 2, 3):
        salida = SALIDAS[tarea]
        datos = RAIZ / f"data/task{tarea}"
        h0_preds = load_predictions(salida, datos, tarea)
        if not h0_preds:
            raise SystemExit(f"No hay salidas históricas para la tarea {tarea} en {salida}")

        h0 = puntuar(ev, h0_preds, tarea)
        resultado["H0"][f"task{tarea}"] = h0["agregado"]

        # B0: misma decisión, mismos documentos, traza corregida.
        reales = lecturas_reales(tarea)
        b0_preds = copy.deepcopy(h0_preds)
        cambiados = 0
        for cid, rec in b0_preds.items():
            if tarea == 3 or cid not in reales:
                continue
            if list(rec.get("reveal_sequence") or []) != reales[cid]:
                rec["reveal_sequence"] = reales[cid]
                cambiados += 1
        b0 = puntuar(ev, b0_preds, tarea)
        resultado["B0"][f"task{tarea}"] = b0["agregado"]
        resultado["correcciones"][f"task{tarea}"] = {
            "casos_con_traza_corregida": cambiados,
            "casos_totales": len(h0_preds),
            "delta_ranking": (b0["agregado"].get("ranking_score") or 0)
                             - (h0["agregado"].get("ranking_score") or 0),
        }

    for etiqueta in ("H0", "B0"):
        resultado[etiqueta]["overall_ranking_score"] = sum(
            PESOS_OVERALL[t] * (resultado[etiqueta][f"task{t}"].get("ranking_score") or 0.0)
            for t in (1, 2, 3))
    resultado["delta_overall_B0_menos_H0"] = (
        resultado["B0"]["overall_ranking_score"] - resultado["H0"]["overall_ranking_score"])

    resultado["aviso_task3"] = {
        "cifras": T3_CIFRAS,
        "nota": ("El ranking T3 que aparece arriba es DENTRO DE MUESTRA: el portavoz "
                 "se ajustó con los 75 casos que se puntúan. Para comparar candidatos "
                 "V2 hay que usar la estimación anidada (0,82345), no ésta. Se publica "
                 "la desplegada sólo porque es la que reproduce el artefacto entregado."),
        "rutas_resueltas": {f"task{t}": str(SALIDAS[t].relative_to(RAIZ)) for t in (1, 2, 3)},
    }
    return resultado


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--eval-repo", type=Path, default=EVAL_POR_DEFECTO)
    a = ap.parse_args()
    r = construir(a.eval_repo)
    destino = AQUI / "reports" / "e00_referencias.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(r, indent=2, ensure_ascii=False))

    print(f"{'':12} {'T1':>9} {'T2':>9} {'T3':>9} {'OVERALL':>9}")
    for etiqueta in ("H0", "B0"):
        fila = [r[etiqueta][f"task{t}"].get("ranking_score") for t in (1, 2, 3)]
        print(f"{etiqueta:12} " + " ".join(f"{x:9.5f}" if x is not None else f"{'—':>9}" for x in fila)
              + f" {r[etiqueta]['overall_ranking_score']:9.5f}")
    print(f"\ndelta OVERALL (B0 − H0): {r['delta_overall_B0_menos_H0']:+.5f}")
    for t in (1, 2, 3):
        c = r["correcciones"][f"task{t}"]
        print(f"  task{t}: {c['casos_con_traza_corregida']}/{c['casos_totales']} trazas corregidas, "
              f"delta ranking {c['delta_ranking']:+.5f}")
    print(f"\nescrito {destino.relative_to(RAIZ)}")
