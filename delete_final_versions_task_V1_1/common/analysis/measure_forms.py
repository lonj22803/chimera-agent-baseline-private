"""Medición aislada del paso 1.2; no modifica políticas ni artefactos entrenados.

Uso: .venv/bin/python -m delete_final_versions_task_V1_1.common.analysis.measure_forms

La regresión logística L2 (C=0.5) reproduce las cabezas de EXPERT-TRACE y
reasoning_task2 con numpy. Medianas, escala, moda y selección se ajustan sólo
sobre entrenamiento. El arbitraje usa LOO interior al LOO exterior. No se usa
el informe global para seleccionar casillas. La posterior de C es la suma de
las probabilidades important/decisive de esas mismas cabezas sin arbitraje.

A necesita decisiones y presupuestos fuera de muestra con calibración
anidada: los cachés históricos no contienen esa calibración. Sin evidencia
se informa explícitamente como no medido, nunca cero.
--confidence-input acepta JSON por task1/task2 con una lista de registros:
case_id, decision, rung, agreement, budget (model/missing/panel/aleatoric),
training_case_ids, protocol (loo_estricto o nested_stratified_cv_10x9),
provenance (texto no vacío),
calibration (registros de los otros casos con case_id, decision, rung, budget
y training_case_ids que excluyan tanto el caso exterior como el interior).
LOO exige todos los otros casos; 10x9 usa sólo el entrenamiento exterior.
El proveedor debe garantizar que también excluyó el caso del preprocesado y
la selección del modelo; la lista de ids permite auditar esa declaración.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import sys
import warnings

# Evita que cada pequeño solve abra un equipo BLAS distinto.
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"
import numpy as np

from ..chimera_experts.io import load_cases
from ..chimera_experts import reasoning_model as t1, reasoning_task2 as t2
from ..uncertainty_forms import (
    VarianceBudget, arbitrate_cells, confidence_from_rung, expected_f1_set,
)

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
LEVELS = ["not_used", "noted", "important", "decisive"]
METRICS = ["variable_weight_score", "important_decisive_factor_score"]


def evaluator(path):
    spec = importlib.util.spec_from_file_location("official_forms_evaluator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sign_test(scores, baseline):
    delta = np.asarray(scores) - np.asarray(baseline)
    up, down = int((delta > 1e-12).sum()), int((delta < -1e-12).sum())
    n = up + down
    p = min(1., 2 * sum(math.comb(n, k) for k in range(min(up, down) + 1)) / 2**n) if n else 1.
    return {"delta": float(delta.mean()), "n_sube": up, "n_baja": down,
            "n_empata": len(delta) - n, "p": p}


def posterior(X, y, test):
    """Newton con búsqueda de paso; intercepto sin penalizar, C=0.5.

    Binario: sigmoid y una cabeza; >=3 clases: softmax multinomial.
    Clases ausentes reciben probabilidad cero, como en los modelos originales.
    """
    classes = np.unique(y)
    result = np.zeros((len(test), 4))
    if len(classes) == 1:
        result[:, classes[0]] = 1.
        return result
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        median = np.nanmedian(X, axis=0)
    median = np.nan_to_num(median)
    X = np.where(np.isnan(X), median, X)
    test = np.where(np.isnan(test), median, test)
    mean, scale = X.mean(0), X.std(0)
    scale[scale < 1e-12] = 1.
    A = np.column_stack(((X - mean) / scale, np.ones(len(X))))
    T = np.column_stack(((test - mean) / scale, np.ones(len(test))))
    binary = len(classes) == 2
    k = 1 if binary else len(classes)
    target = (y == classes[1]).astype(float)[:, None] if binary else (y[:, None] == classes).astype(float)
    w = np.zeros((A.shape[1], k))
    reg = np.full_like(w, 2.)
    reg[-1] = 0.

    def objective(b):
        z = A @ b
        if binary:
            p = 1 / (1 + np.exp(-np.clip(z, -700, 700)))
            loss = np.sum(np.logaddexp(0, z) - target * z)
        else:
            z = z - z.max(1, keepdims=True)
            p = np.exp(z)
            p /= p.sum(1, keepdims=True)
            loss = -np.sum(target * (z - np.log(np.exp(z).sum(1, keepdims=True))))
        return float(loss + np.sum(reg * b*b) / 2), p

    for _ in range(100):
        loss, p = objective(w)
        grad = A.T @ (p - target) + reg * w
        if np.max(np.abs(grad)) < 1e-7:
            break
        covariance = p[:, :, None] * (np.eye(k)[None] - p[:, None, :])
        h = np.einsum("ni,nab,nj->iajb", A, covariance, A).reshape(w.size, w.size)
        h.flat[::w.size + 1] += reg.ravel() + 1e-10
        direction = np.linalg.solve(h, grad.ravel()).reshape(w.shape)
        if float(np.sum(grad * direction)) < 1e-10:
            break
        step = 1.
        while objective(w - step * direction)[0] > loss - 1e-4 * step * np.sum(grad * direction):
            step /= 2
            if step < 1e-12:
                raise RuntimeError("La regresión logística no converge")
        w -= step * direction
    else:
        raise RuntimeError("Se agotaron las iteraciones de la regresión logística")
    z = T @ w
    if binary:
        p = 1 / (1 + np.exp(-np.clip(z[:, 0], -700, 700)))
        result[:, classes] = np.column_stack((1-p, p))
    else:
        p = np.exp(z - z.max(1, keepdims=True))
        result[:, classes] = p / p.sum(1, keepdims=True)
    return result


def mode(y):
    # Desempate lexicográfico como np.unique sobre las etiquetas originales.
    return min(range(4), key=lambda i: (-int((y == i).sum()), LEVELS[i]))


def measure_cell(job):
    """Cache leave-two-out: un ajuste sirve a los dos folds exteriores."""
    X, y = job
    n = len(y)
    probabilities = np.zeros((n, 4))
    modes = np.zeros(n, int)
    inner_model = np.full((n, n), np.nan)
    inner_mode = np.full((n, n), np.nan)
    observed = y >= 0
    for i in range(n):
        tr = observed & (np.arange(n) != i)
        if not tr.any():
            raise ValueError("Casilla sin entrenamiento en un fold")
        probabilities[i] = posterior(X[tr], y[tr], X[[i]])[0]
        modes[i] = mode(y[tr])
    for i, j in itertools.combinations(range(n), 2):
        if not observed[i] and not observed[j]:
            continue
        tr = observed & (np.arange(n) != i) & (np.arange(n) != j)
        p = posterior(X[tr], y[tr], X[[i, j]])
        # argmax lexicográfico para empates, igual que las clases originales.
        order = sorted(range(4), key=lambda c: LEVELS[c])
        pred = np.asarray(order)[p[:, order].argmax(1)]
        constant = mode(y[tr])
        for outer, held, prediction in ((i, j, pred[1]), (j, i, pred[0])):
            if observed[held]:
                inner_model[outer, held] = 1 - abs(int(y[held]) - int(prediction)) / 3
                inner_mode[outer, held] = 1 - abs(int(y[held]) - constant) / 3
    return probabilities, modes, np.nanmean(inner_model, axis=1), np.nanmean(inner_mode, axis=1)


def policy_table(ev, truths, policies, baseline, metric):
    values = {name: [getattr(ev, metric)(gt, pred) for gt, pred in zip(truths, rows)]
              for name, rows in policies.items()}
    if any(v is None or not math.isfinite(v) for rows in values.values() for v in rows):
        raise ValueError(f"Métrica ausente o inválida: {metric}")
    table = {}
    for name, scores in values.items():
        comparison = sign_test(scores, values[baseline])
        adopted = name != baseline and comparison["delta"] > 1e-12
        table[name] = {"metrica": float(np.mean(scores)), "linea_base": baseline,
                       **comparison, "adoptar": adopted,
                       "motivo": "Mejora la media LOO frente al suelo; p se publica sin exigir significación."
                       if adopted else "Es el suelo de referencia." if name == baseline else
                       "No supera la media LOO del suelo.", "scores_por_caso": scores}
    comparisons = {}
    for a, b in itertools.combinations(policies, 2):
        comparisons[f"{b} vs {a}"] = sign_test(values[b], values[a])
    return {"politicas": table, "comparaciones_pareadas": comparisons}


def weights_measurement(cases, task, ev, workers):
    mod = t1 if task == 1 else t2
    variables = mod.TASK1_VARIABLES if task == 1 else mod.TASK2_VARIABLES
    X = np.array([[mod.case_predictors(c)[k] for k in mod.PREDICTORS] for c in cases])
    labels = np.array([[LEVELS.index(c.reasoning["variable_weights"][v])
                        if v in c.reasoning["variable_weights"] else -1 for v in variables] for c in cases])
    jobs = [(X, labels[:, j]) for j in range(len(variables))]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        cells = list(pool.map(measure_cell, jobs))
    policies = {k: [] for k in ("moda", "aprendido_entero", "arbitrate_cells")}
    sets = {k: [] for k in ("moda", "umbral_0.5", "expected_f1_set")}
    audit = []
    for i, case in enumerate(cases):
        learned, constants, cell_report, probs = {}, {}, {}, {}
        for j, v in enumerate(variables):
            p, modes, inner, floor = cells[j]
            if task == 2 and v in t2.GATED_VARIABLES and not t2.gate_target(case):
                continue
            order = sorted(range(4), key=lambda c: LEVELS[c])
            learned[v] = LEVELS[order[int(np.argmax(p[i, order]))]]
            constants[v] = LEVELS[int(modes[i])]
            cell_report[v] = {"loo": float(inner[i]), "moda": float(floor[i])}
            probs[v] = float(p[i, 2:].sum())
        arbitrated, adopted = arbitrate_cells(learned, constants, cell_report)
        for name, w in zip(policies, (constants, learned, arbitrated)):
            policies[name].append({"variable_weights": w})
        sets["moda"].append({"variable_weights": constants})
        for name, selected in (("umbral_0.5", {v for v, p in probs.items() if p > .5}),
                               ("expected_f1_set", expected_f1_set(probs))):
            sets[name].append({"variable_weights": {v: "important" for v in sorted(selected)}})
        audit.append({"case_id": case.case_id, "posterior_importante": probs,
                      "seleccion_interior": cell_report, "casillas_aprendidas": adopted,
                      "pesos": {k: rows[-1]["variable_weights"] for k, rows in policies.items()},
                      "conjuntos": {k: sorted(ev._important_set(rows[-1]["variable_weights"]))
                                    for k, rows in sets.items()}})
    truths = [c.reasoning for c in cases]
    b = {m: policy_table(ev, truths, policies, "moda", m) for m in METRICS}
    c = policy_table(ev, truths, sets, "moda", METRICS[1])
    contrast = c["comparaciones_pareadas"]["expected_f1_set vs umbral_0.5"]
    row = c["politicas"]["expected_f1_set"]
    row["contraste_clave"] = contrast
    row["adoptar"] = row["adoptar"] and contrast["delta"] > 1e-12
    row["motivo"] = ("Supera tanto la moda como el umbral 0.5 en F1 medio LOO."
                      if row["adoptar"] else "No supera simultáneamente la moda y el umbral 0.5 en F1 medio LOO.")
    return b, c, audit


PROTOCOLS = ("loo_estricto", "nested_stratified_cv_10x9")


def _check_evidence(rows, ids):
    """Valida la evidencia de confianza segun el protocolo que ella misma declara.

    Dos protocolos, una sola regla innegociable: **cero fuga**. Lo que cambia
    entre ellos es la IGUALDAD de conjuntos (un LOO estricto entrena con los
    otros 90; un pliegue 10x9 entrena con menos), nunca la comprobacion de que
    el caso evaluado no se ha visto a si mismo ni ha visto al caso exterior.

    Un registro sin ``protocol`` se rechaza: preferimos un fallo ruidoso a
    heredar en silencio la validacion equivocada.
    """
    for r in rows:
        protocol = r.get("protocol")
        if protocol not in PROTOCOLS:
            raise ValueError(f"Registro sin protocolo declarado o desconocido: {protocol!r}. "
                             f"Usa uno de {PROTOCOLS}")
        if not r.get("provenance"):
            raise ValueError("La evidencia de confianza no declara procedencia")
        train = set(r["training_case_ids"])
        calibration = r["calibration"]

        if protocol == "loo_estricto":
            if train != ids - {r["case_id"]}:
                raise ValueError("La evidencia de confianza no declara LOO estricto")
            if {c["case_id"] for c in calibration} != ids - {r["case_id"]} or \
                    len(calibration) != len(ids) - 1:
                raise ValueError("Calibración interior incompleta")
            for c in calibration:
                if set(c["training_case_ids"]) != ids - {r["case_id"], c["case_id"]}:
                    raise ValueError("Fuga de etiqueta exterior en la calibración interior")
            continue

        # nested_stratified_cv_10x9: pliegues, no conjuntos completos.
        if r["case_id"] in train:
            raise ValueError(f"{r['case_id']}: el caso se ve a si mismo en su entrenamiento")
        if not train <= ids:
            raise ValueError(f"{r['case_id']}: entrena con ids fuera de la cohorte")
        if len(train) < 0.6 * (len(ids) - 1):
            raise ValueError(f"{r['case_id']}: pliegue degenerado, entrena con {len(train)} de "
                             f"{len(ids) - 1} posibles")
        if not calibration:
            raise ValueError(f"{r['case_id']}: sin calibración interior")
        for c in calibration:
            inner = set(c["training_case_ids"])
            if c["case_id"] == r["case_id"]:
                raise ValueError(f"{r['case_id']}: el caso exterior aparece en su propia calibración")
            if r["case_id"] in inner:
                raise ValueError(f"{r['case_id']}: fuga del caso exterior en la calibración interior")
            if c["case_id"] in inner:
                raise ValueError(f"{c['case_id']}: el caso interior se ve a si mismo")
            if not inner <= ids:
                raise ValueError(f"{c['case_id']}: calibración con ids fuera de la cohorte")


def confidence_measurement(cases, task, ev, supplied):
    truths = [c.reasoning for c in cases]
    policies = {"clear": [{"confidence": "clear"} for _ in cases]}
    missing = ("El caché honest de task1 usa 5 folds y la corrida final usa expertos ajustados "
               "con los etiquetados; faltan veredictos LOO y calibración interior sin fuga."
               if task == 1 else "No hay protocolo por peldaños de task2 especificado ni "
               "veredictos LOO con varianzas y calibración interior para ese protocolo.")
    result = {"estado": "incompleto", "motivo": missing,
              "referencia_historica": .7651 if task == 1 else .9028}
    rows = supplied.get(f"task{task}")
    if rows is not None:
        by_id = {r["case_id"]: r for r in rows}
        ids = {c.case_id for c in cases}
        if set(by_id) != ids or len(rows) != len(ids):
            raise ValueError("La evidencia de confianza no cubre exactamente la cohorte")
        rows = [by_id[c.case_id] for c in cases]
        _check_evidence(rows, ids)
        protocols = {r["protocol"] for r in rows}
        if len(protocols) > 1:
            raise ValueError(f"Protocolos mezclados en la misma tarea: {sorted(protocols)}")
        protocol = protocols.pop()
        budgets = [VarianceBudget(**r["budget"]) for r in rows]
        hits = [r["decision"] == c.label for r, c in zip(rows, cases)]
        policies["agreement"] = [{"confidence": r["agreement"]} for r in rows]
        policies["confidence_from_rung"] = []
        audit = []
        for i, r in enumerate(rows):
            calibration = r["calibration"]
            labels = {c.case_id: c.label for c in cases}
            accuracy = {rung: float(np.mean([c["decision"] == labels[c["case_id"]]
                                            for c in calibration if c["rung"] == rung]))
                        for rung in {c["rung"] for c in calibration}}
            q = float(np.quantile([VarianceBudget(**c["budget"]).epistemic
                                   for c in calibration], .66))
            conf, reason = confidence_from_rung(r["rung"], budgets[i], accuracy, cohort_sigma_q66=q)
            policies["confidence_from_rung"].append({"confidence": conf})
            audit.append({"case_id": r["case_id"], "rung_accuracy": accuracy, "q66": q,
                          "budget": asdict(budgets[i]), "confidence": conf, "motivo": reason})
        motivo = ("Calibración por peldaño excluyendo el caso evaluado (LOO estricto)."
                  if protocol == "loo_estricto" else
                  "Calibración por peldaño con CV estratificada anidada 10x9. NO es LOO: "
                  "entrena con ~90 % de la cohorte en vez del 98,6 %, así que si difiere "
                  "de un LOO será por ser algo más PESIMISTA. No compares esta fila con "
                  "una medida en LOO estricto como si fueran la misma medida.")
        result.update(estado="medido", motivo=motivo, protocolo=protocol,
                      evidencia=rows, calibracion=audit)
        result["escalera_fiabilidad"] = {"_protocolo": protocol}
        for name, preds in policies.items():
            ladder = {}
            for level in ("clear", "borderline", "uncertain"):
                members = [j for j, p in enumerate(preds) if p["confidence"] == level]
                ladder[level] = {"protocolo": protocol, "n": len(members), "aciertos": sum(hits[j] for j in members),
                                 "acierto_decision": float(np.mean([hits[j] for j in members])) if members else None}
            result["escalera_fiabilidad"][name] = ladder
    result["confidence_score"] = policy_table(ev, truths, policies, "clear", "confidence_score")
    if rows is not None:
        # Sin esto, una fila 10x9 y una LOO son indistinguibles en el informe.
        for name, row in result["confidence_score"]["politicas"].items():
            row["protocolo"] = "constante" if name == "clear" else protocol
            row["motivo"] = ("Es el suelo de referencia." if name == "clear" else
                             "Mejora la media frente a clear bajo el protocolo declarado." if row["adoptar"] else
                             "No supera la media de clear bajo el protocolo declarado.")
    if rows is not None:
        row = result["confidence_score"]["politicas"]["confidence_from_rung"]
        comparison = result["confidence_score"]["comparaciones_pareadas"][
            "confidence_from_rung vs agreement"]
        row["contraste_politica_actual"] = comparison
        row["adoptar"] = row["adoptar"] and comparison["delta"] > 1e-12
        row["motivo"] = ("Supera tanto clear como agreement en confidence_score medio bajo el protocolo declarado."
                          if row["adoptar"] else "No supera simultáneamente clear y agreement.")
    if rows is None:
        for name in ("agreement", "confidence_from_rung"):
            result["confidence_score"]["politicas"][name] = {
                "metrica": None, "delta": None, "n_sube": None, "n_baja": None, "p": None,
                "linea_base": "clear", "adoptar": False, "motivo": result["motivo"]}
        result["escalera_fiabilidad"] = None
    return result


def print_tables(report):
    for task, result in report["tareas"].items():
        print(f"\n{task}: n={result['n']}")
        tables = [("A confidence_score", result["A"]["confidence_score"])]
        tables += [(f"B {m}", t) for m, t in result["B"].items()]
        tables += [("C important_decisive_factor_score", result["C"])]
        for title, table in tables:
            print(title)
            print("politica                 metrica    delta  sube baja        p adoptar")
            for name, row in table["politicas"].items():
                if row["metrica"] is None:
                    print(f"{name:24} NO MEDIDO: {row['motivo']}")
                    continue
                print(f"{name:24} {row['metrica']:.6f} {row['delta']:+.6f} "
                      f"{row['n_sube']:4} {row['n_baja']:4} {row['p']:.6f} {row['adoptar']}")
            if title.startswith("C"):
                print("Contraste expected_f1_set vs umbral_0.5:",
                      json.dumps(table["comparaciones_pareadas"]["expected_f1_set vs umbral_0.5"]))
        print("Escalera de fiabilidad:", json.dumps(result["A"]["escalera_fiabilidad"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--evaluator", type=Path, default=Path.home() / "PycharmProjects/CHIMERA-agent-eval/evaluation/evaluate.py")
    parser.add_argument("--output", type=Path, default=HERE / "forms_report.json")
    parser.add_argument("--confidence-input", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    ev = evaluator(args.evaluator)
    supplied = json.loads(args.confidence_input.read_text()) if args.confidence_input else {}
    report = {"paso": "1.2", "evaluador": str(args.evaluator),
              "evaluador_sha256": hashlib.sha256(args.evaluator.read_bytes()).hexdigest(),
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "metodologia": {"validacion": "B/C: LOO exterior; arbitraje con LOO interior (leave-two-out cacheado). A: protocolo declarado en cada tarea",
                  "cabezas": "Receta logística de EXPERT-TRACE/reasoning_task2, C=0.5; implementación Newton numpy",
                  "aprendido_entero": "Todas las cabezas sin puerta de selección; arbitrate_cells mide la puerta aparte",
                  "moda": "Moda por casilla del entrenamiento; misma puerta de grado para las tres políticas task2",
                  "ausencias": "Casillas ausentes no entrenan la cabeza; nunca se consulta su presencia en el caso de prueba",
                  "adopcion": "Mejora media sobre la constante; confidence_from_rung además debe superar agreement en ambas tareas; C además debe superar umbral 0.5; no exige p<0.05",
                  "signos": "Binomial exacta bilateral por caso, empates excluidos, sin ajuste por multiplicidad",
                  "juez": "No invocado: sólo componentes deterministas oficiales, sin case_score ni redistribución de pesos",
                  "limitacion": "LOO no corrige que las recetas y reglas históricas se eligieran con esta cohorte"},
              "tareas": {}}
    for task, expected in ((1, 91), (2, 72)):
        cases = [c for c in load_cases(args.data / f"task{task}", task, labelled_only=True) if c.reasoning]
        if len(cases) != expected:
            raise ValueError(f"task{task}: se esperaban {expected}, hay {len(cases)}")
        official_root = args.evaluator.parent / "ground_truth" / f"task{task}"
        for case in cases:
            for source in sorted((args.data / f"task{task}" / "ground_truth" / case.case_id).glob("*.json")):
                official = official_root / case.case_id / source.name
                if source.name.endswith("clinical-data.json"):
                    continue
                if official.exists() and json.loads(source.read_text()) != json.loads(official.read_text()):
                    raise ValueError(f"Ground truth distinto del oficial: {source}")
        print(f"Midiendo task{task}: {len(cases)} casos, LOO anidado...", flush=True)
        b, c, audit = weights_measurement(cases, task, ev, args.workers)
        report["tareas"][f"task{task}"] = {"n": len(cases), "case_ids": [c.case_id for c in cases],
            "A": confidence_measurement(cases, task, ev, supplied), "B": b, "C": c, "auditoria_B_C": audit}
    report["aceptacion_completa"] = all(t["A"]["estado"] == "medido" for t in report["tareas"].values())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    print_tables(report)
    print(f"\nInforme: {args.output}")
    print(f"Aceptación completa: {report['aceptacion_completa']}")
    return 0 if report["aceptacion_completa"] else 2


if __name__ == "__main__":
    sys.exit(main())
