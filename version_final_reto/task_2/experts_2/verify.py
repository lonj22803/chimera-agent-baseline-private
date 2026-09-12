"""Recalcula métricas de probabilidades LOO archivadas, sin ajustar expertos.

Una cifra agregada publicada no sustituye probabilidades ausentes. Los
resultados incompletos se guardan y hacen que el proceso termine con código 1.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np

from .panel import DATA, HERE, EXPERTS, d2, io, load_bundle
from chimera_experts.uncertainty_multiclass import multiclass_brier, expected_calibration_error

PUBLISHED = {
    "accuracy": [0.8611, 0.8611, 0.6389, 0.8611, 0.8611],
    "brier": [0.2619, 0.2733, 0.4865, 0.2652, 0.2842],
    "ece": [0.0425, 0.0627, 0.1069, 0.0760, 0.0857],
}


def compare(measured, published):
    return {"measured": measured, "published": published,
            "delta": None if measured is None else measured - published,
            "passed": measured is not None and round(measured, 4) == published}


def isup_loo(cases, y):
    """Mapa modal de grado reajustado en cada pliegue; empate por clase."""
    def grade(case):
        try:
            return float(case.prompt.get("bx_isup"))
        except (TypeError, ValueError):
            return float("nan")
    grades = np.array([grade(c) for c in cases])
    predictions = []
    for i, g in enumerate(grades):
        train = np.arange(len(cases)) != i
        selected = train & (grades == g)
        labels = y[selected] if selected.any() else y[train]
        predictions.append(int(np.bincount(labels, minlength=4).argmax()))
    return np.array(predictions)


def verify(data_root=DATA, out=HERE / "reports" / "verify.json"):
    cases = io.load_cases(Path(data_root), task=2, labelled_only=True)
    if len(cases) != 72:
        raise ValueError(f"Se requieren 72 etiquetados; encontrados {len(cases)}")
    y = d2.build_labels(cases)
    results, predictions = {}, {}
    for i, (name, path) in enumerate(EXPERTS.items()):
        bundle = load_bundle(path)
        P = bundle.get("loo_probabilities")
        row = {"ladder_protocol": bundle.get("ladder_protocol", "leave_one_out")}
        if P is None:
            row["error"] = "Faltan loo_probabilities; las métricas agregadas no permiten reproducir el LOO sin reentrenar."
            measured = dict.fromkeys(PUBLISHED)
        else:
            P = np.asarray(P, dtype=float)
            if (P.shape != (72, 4) or not np.isfinite(P).all() or
                    (P < 0).any() or not np.allclose(P.sum(axis=1), 1) or
                    tuple(bundle["classes"]) != d2.CLASSES):
                raise ValueError(f"{name}: probabilidades LOO inválidas")
            pred = P.argmax(axis=1)
            predictions[name] = pred
            measured = {"accuracy": float((pred == y).mean()),
                        "brier": multiclass_brier(y, P),
                        "ece": expected_calibration_error(y, P)}
        row.update({m: compare(measured[m], values[i]) for m, values in PUBLISHED.items()})
        row["published_report"] = bundle["metrics"]["loo"]
        results[name] = row
    agreement = {a: {b: int((pa == pb).sum()) for b, pb in predictions.items()}
                 for a, pa in predictions.items()}
    pairs = [("expert_one", "expert_two", 72), ("expert_one", "expert_four", 72),
             ("expert_two", "expert_four", 72), ("expert_three", "expert_one", 44),
             ("expert_three", "expert_two", 44), ("expert_three", "expert_four", 44)]
    agreement_checks = {f"{a}/{b}": compare(agreement.get(a, {}).get(b), expected)
                        for a, b, expected in pairs}
    rule = isup_loo(cases, y)
    hits = int((rule == y).sum())
    rule_result = {"hits": compare(hits, 62), "accuracy": compare(hits / 72, 0.8611),
                   "predictions": rule.tolist()}
    checks = {m: all(r[m]["passed"] for r in results.values()) for m in PUBLISHED}
    checks["agreement"] = all(r["passed"] for r in agreement_checks.values())
    checks["isup_rule"] = all(rule_result[k]["passed"] for k in ("hits", "accuracy"))
    report = {"method": "Recompute from archived LOO probabilities; no expert refitting",
              "row_order": "sorted case_id, same as historical io.load_cases; bundles have no row IDs",
              "precision": "Equality after rounding to the published four decimal places",
              "n": len(cases), "case_ids": [c.case_id for c in cases],
              "experts": results, "agreement": agreement,
              "agreement_checks": agreement_checks, "isup_rule": rule_result,
              "checks": checks, "passed": all(checks.values())}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    for name, row in results.items():
        for m in PUBLISHED:
            r = row[m]
            print(f"{name} {m}: measured={r['measured']} published={r['published']} delta={r['delta']} {'PASS' if r['passed'] else 'FAIL'}")
        if "error" in row:
            print(f"{name}: {row['error']}")
    for pair, r in agreement_checks.items():
        print(f"agreement {pair}: {r['measured']}/72 expected={r['published']} delta={r['delta']} {'PASS' if r['passed'] else 'FAIL'}")
    print(f"ISUP LOO: {hits}/72 = {hits / 72:.10f} {'PASS' if checks['isup_rule'] else 'FAIL'}")
    print(f"Checks: {sum(checks.values())}/5 PASS; report={out}")
    return report


def main():
    report = verify()
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
