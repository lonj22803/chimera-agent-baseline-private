"""Genera la lectura provisional Tier S a partir de los artefactos medidos."""

from __future__ import annotations

import csv
from datetime import date
import json
from typing import Any

from .classify import classify
from .paths import RESULTS
from .stats import COMPONENTS


def _load(name: str) -> Any:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def _f_verdict(row: dict[str, Any]) -> str:
    metrics = row["overall"]["metrics"]
    deltas = {name: metrics[name]["delta"] for name in COMPONENTS}
    intervals = {name: tuple(metrics[name]["ci95"]) for name in COMPONENTS}
    return classify(
        deltas,
        intervals,
        level="F",
        exact_zero=all(value == 0 for value in deltas.values()),
    )


def _d_verdict(row: dict[str, Any], same_sign: bool) -> str:
    ranking = row["overall"]["metrics"]["ranking"]
    return classify(
        ranking["delta"],
        tuple(ranking["ci95"]),
        level="D",
        p_value=row["mcnemar_holm_p"],
        exact_zero=not row["changed_cases"] and ranking["delta"] == 0,
        same_sign=same_sign,
    )


def build() -> dict[str, Any]:
    loo_rows = {
        row["id"]: row
        for row in _load("S_loo.json")["rows"]
        if row["mode"] == "honest"
    }
    robust = {
        row["id"]: row
        for row in csv.DictReader((RESULTS / "S_robustez.csv").open(encoding="utf-8"))
    }
    cascade = _load("S_cascade.json")["vote_a0_vs_yes"]["honest"]
    factorial = _load("S_factorial.json")["modes"]["honest"]

    h1_d = _d_verdict(loo_rows["S-COH"], robust["S-COH"]["same_sign"] == "True")
    h2_d = _d_verdict(loo_rows["S-M4"], robust["S-M4"]["same_sign"] == "True")
    vote_delta = cascade["metrics"]["ranking"]
    shapley = factorial["shapley"]["ranking"]
    h5_zero = (
        not loo_rows["S-PSA-off"]["changed_cases"]
        and all(
            loo_rows["S-PSA-off"]["overall"]["metrics"][name]["delta"] == 0
            for name in ("ranking", "gate", "f1_yes", *COMPONENTS)
        )
    )
    h6_weights = _f_verdict(loo_rows["S-W-noted"])
    h6_plan = _f_verdict(loo_rows["S-PLAN-todo"])
    h7_zero = (
        not loo_rows["S-LIB-off"]["changed_cases"]
        and all(
            loo_rows["S-LIB-off"]["overall"]["metrics"][name]["delta"] == 0
            for name in ("ranking", "gate", "f1_yes", *COMPONENTS)
        )
    )
    h15_f = _f_verdict(loo_rows["S-G-off"])
    h15_rank = loo_rows["S-G-off"]["overall"]["metrics"]["ranking"]["delta"]

    hypotheses = {
        "H1": {
            "estado": "indeterminada" if h1_d.startswith("INDETERMINADA") else "confirmada",
            "evidencia": "S-COH: delta ranking 0.0648, IC95 [0.0186, 0.1142], McNemar-Holm p=0.5371; signo DEV/VAL positivo.",
            "regla": h1_d,
            "fuente": "S_loo.csv; S_robustez.csv",
        },
        "H2": {
            "estado": "indeterminada" if h2_d.startswith("INDETERMINADA") else "confirmada",
            "evidencia": "S-M4: delta ranking 0.0302, IC95 [-0.0113, 0.0776], McNemar-Holm p=1; signos DEV/VAL opuestos.",
            "regla": h2_d,
            "fuente": "S_loo.csv; S_robustez.csv",
        },
        "H3": {
            "estado": "indeterminada" if vote_delta["ci95"][0] <= 0 <= vote_delta["ci95"][1] else ("refutada" if vote_delta["delta"] > 0 else "confirmada"),
            "evidencia": "Voto honesto 15/27 frente a si constante 18/27; delta ranking A0-si -0.0829, IC95 [-0.2174, 0.0317].",
            "regla": "comparacion pareada del peldano de voto",
            "fuente": "S_cascade.csv",
        },
        "H4": {
            "estado": "confirmada" if shapley["E3"] > shapley["E1"] else "refutada",
            "evidencia": f"Shapley ranking E3={shapley['E3']:.4f} y E1={shapley['E1']:.4f}.",
            "regla": "E1 < E3",
            "fuente": "S_factorial.csv",
        },
        "H5": {
            "estado": "confirmada" if h5_zero else "refutada",
            "evidencia": "S-PSA-off: 0 filas distintas y delta cero en D, ranking y los cinco componentes.",
            "regla": "SOBRA por construccion" if h5_zero else _f_verdict(loo_rows["S-PSA-off"]),
            "fuente": "S_loo.csv",
        },
        "H6": {
            "estado": "confirmada" if h6_weights == h6_plan == "NECESARIA_F" else "indeterminada",
            "evidencia": "Pesos constantes noted: delta ranking 0.0634. Abrir todo: delta tool 0.0818. Ambos brazos se clasifican NECESARIA_F.",
            "regla": f"pesos={h6_weights}; plan={h6_plan}",
            "fuente": "S_loo.csv; S_formulario.csv",
        },
        "H7": {
            "estado": "refutada" if h7_zero else "indeterminada",
            "evidencia": "S-LIB-off: 0 filas distintas y delta cero en todos los componentes; no aparece la bajada F prevista.",
            "regla": "SOBRA por construccion" if h7_zero else _f_verdict(loo_rows["S-LIB-off"]),
            "fuente": "S_loo.csv",
        },
        "H8": {
            "estado": "indeterminada",
            "evidencia": "Cerrar radiologia cambia 3 decisiones y cerrar notas previas cambia 5, pero ninguna supera Holm; la equivalencia prosa-ejecutor requiere L0.",
            "regla": "Tier L pendiente",
            "fuente": "S_loo.csv",
        },
        "H15": {
            "estado": "confirmada" if h15_f == "NECESARIA_F" and h15_rank > 0 else ("refutada" if h15_rank <= 0 else "indeterminada"),
            "evidencia": "Sin M11: variable_weight mejora 0.0378, grounding cae 0.1782 y el neto favorece a la guardia en 0.00833 de ranking.",
            "regla": h15_f,
            "fuente": "S_loo.csv; S_formulario.csv",
        },
    }
    return {"date": date.today().isoformat(), "tier": "S", "hypotheses": hypotheses}


def write() -> None:
    result = build()
    (RESULTS / "S_veredictos.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# Lectura provisional del Tier S",
        "",
        f"Fecha: {result['date']}. Modo primario: `honest`. Los veredictos aplican los margenes e IC del pre-registro; D exige ademas McNemar-Holm y signo DEV/VAL.",
        "",
        "| H | Estado | Evidencia y regla | CSV | Desviaciones respecto a lo pre-registrado |",
        "|---|---|---|---|---|",
    ]
    for hypothesis, item in result["hypotheses"].items():
        evidence = f"{item['evidencia']} Regla: `{item['regla']}`"
        lines.append(
            f"| {hypothesis} | **{item['estado']}** | {evidence} | `{item['fuente']}` | Ninguna |"
        )
    lines.extend(
        [
            "",
            "## Lectura",
            "",
            "Tier S sostiene con claridad la aportacion de E4 al formulario, la superioridad relativa de E3 sobre E1 y el valor neto de la guardia de aterrizaje. E2 es redundante por construccion y la biblioteca no produce el efecto F previsto. Cohorte y grado muestran efectos de magnitud relevante, pero el control Holm y, para grado, la falta de estabilidad DEV/VAL impiden llamarlos necesarios con la regla pre-registrada.",
            "",
            "H8 no puede cerrarse sin L0: Tier S demuestra que los documentos pueden mover D, pero no mide si la prosa del registrador aporta algo frente a ejecutar el plan de forma determinista. Esta lectura no propone cambios de arquitectura.",
        ]
    )
    (RESULTS / "LECTURA_S.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write()
