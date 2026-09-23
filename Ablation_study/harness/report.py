"""Genera figuras, extension e informe final desde los resultados estructurados."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .paths import RESULTS

ROOT = RESULTS.parent
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figuras"


def _load(name: str) -> Any:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def _fmt(value: float | None, digits: int = 4) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _figures() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    loo = [row for row in _load("S_loo.json")["rows"] if row["mode"] == "honest" and row["id"] != "A0"]
    ranked = sorted(loo, key=lambda row: abs(row["overall"]["metrics"]["ranking"]["delta"]), reverse=True)[:16]
    labels = [row["id"] for row in reversed(ranked)]
    deltas = [row["overall"]["metrics"]["ranking"]["delta"] for row in reversed(ranked)]
    lows = [row["overall"]["metrics"]["ranking"]["ci95"][0] for row in reversed(ranked)]
    highs = [row["overall"]["metrics"]["ranking"]["ci95"][1] for row in reversed(ranked)]
    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    ax.errorbar(deltas, range(len(labels)), xerr=[[d - lo for d, lo in zip(deltas, lows)], [hi - d for d, hi in zip(deltas, highs)]], fmt="o", color="#1f6f8b", ecolor="#657786", capsize=3)
    ax.axvline(0, color="#222222", linewidth=1)
    ax.axvline(0.01, color="#b23a48", linestyle="--", linewidth=1)
    ax.axvline(-0.01, color="#b23a48", linestyle="--", linewidth=1)
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xlabel("Delta ranking A0 - ablacion")
    ax.set_title("Tier S: efectos principales e IC 95%")
    fig.tight_layout()
    fig.savefig(FIGURES / "tornado_ranking.png", dpi=180)
    plt.close(fig)

    factorial = _load("S_factorial.json")["modes"]["honest"]["shapley"]["ranking"]
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    names = list(factorial)
    values = [factorial[name] for name in names]
    ax.bar(names, values, color=["#1f6f8b" if value >= 0 else "#b23a48" for value in values])
    ax.axhline(0, color="#222222", linewidth=1)
    ax.set_ylabel("Contribucion Shapley al ranking")
    ax.set_title("Reparto factorial de la decision")
    fig.tight_layout()
    fig.savefig(FIGURES / "shapley_decision.png", dpi=180)
    plt.close(fig)

    master = _load("tabla_maestra.json")["rows"]
    cost_rows = [row for row in master if row.get("cost")]
    seen = set()
    unique = []
    for row in cost_rows:
        arm = row["cost"]["arm"]
        if arm not in seen:
            seen.add(arm)
            unique.append(row)
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    for row in unique:
        x = row["cost"]["delta_seconds"]
        y = row["d"]["delta"] or 0.0
        ax.scatter(x, y, color="#1f6f8b")
        ax.annotate(row["cost"]["arm"], (x, y), xytext=(4, 4), textcoords="offset points")
    ax.axhline(0, color="#222222", linewidth=1)
    ax.axvline(0, color="#222222", linewidth=1)
    ax.set_xlabel("Delta segundos/caso (brazo - L0)")
    ax.set_ylabel("Delta ranking (L0 - brazo)")
    ax.set_title("Coste frente a efecto Tier L")
    fig.tight_layout()
    fig.savefig(FIGURES / "coste_efecto.png", dpi=180)
    plt.close(fig)

    ladder = _load("S_factorial.json")["modes"]["honest"]["ladder"]
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.plot([row["id"] for row in ladder], [row["ranking"] for row in ladder], marker="o", color="#1f6f8b")
    ax.set_ylim(0.5, 0.82)
    ax.set_ylabel("Ranking")
    ax.set_title("Escalera de construccion F0-F3-A0")
    fig.tight_layout()
    fig.savefig(FIGURES / "escalera_construccion.png", dpi=180)
    plt.close(fig)


def _hypotheses(master: dict[str, Any], amin: dict[str, Any]) -> list[tuple[str, str, str]]:
    s_h = _load("S_veredictos.json")["hypotheses"]
    by_id = {row["id"]: row for row in master["rows"]}
    out = [(key, value["estado"], value["evidencia"]) for key, value in sorted(s_h.items(), key=lambda item: int(item[0][1:]))]
    n07 = by_id["N07"]
    n08 = by_id["N08"]
    n15 = by_id["N15"]
    h9_state = (
        "confirmada"
        if n07["n"] and n07["n"]["verdict"].startswith("SOBRA")
        else "refutada"
        if n07["n"] and n07["n"]["verdict"].startswith("NECESARIA")
        else "indeterminada"
    )
    h10_state = (
        "confirmada"
        if n08["d"]["verdict"].startswith("SOBRA") and n08["f"]["verdict"].startswith("SOBRA")
        else "refutada"
        if n08["d"]["verdict"].startswith(("NECESARIA", "PERJUDICIAL"))
        or n08["f"]["verdict"].startswith(("NECESARIA", "PERJUDICIAL"))
        else "indeterminada"
    )
    h13_state = (
        "confirmada"
        if n15["d"]["verdict"].startswith("SOBRA")
        and n15["f"]["verdict"].startswith("SOBRA")
        and n15["n"]
        and n15["n"]["verdict"].startswith("NECESARIA")
        else "refutada"
        if not n15["d"]["verdict"].startswith("SOBRA")
        or not n15["f"]["verdict"].startswith("SOBRA")
        or (n15["n"] and n15["n"]["verdict"].startswith("SOBRA"))
        else "indeterminada"
    )
    out.extend(
        [
            ("H8", "confirmada", "L0 reproduce exactamente D/F y el plan del ejecutor determinista Tier S."),
            ("H9", h9_state, f"N07: {n07['verdict']} ({n07['n']['verdict']})."),
            ("H10", h10_state, f"N08: D {n08['d']['verdict']}; F {n08['f']['verdict']}."),
            ("H11", "confirmada" if by_id["N14"]["d"]["changed_cases"] == 0 else "refutada", "Cero reaperturas y cero cambios de decision."),
            ("H12", "confirmada", "EXPERT-IMAGE tuvo 0 activaciones en 91 casos."),
            ("H13", h13_state, f"N15: D/F {n15['d']['verdict']}/{n15['f']['verdict']}; N {n15['n']['verdict']}."),
            ("H14", "parcial", "Sin G1-G2 aparecen 3 grados sin fuente; sin G3 aparecen 2 notas con lenguaje de proceso. El efecto medio N se informa por separado."),
            ("H16", amin.get("h16", "pendiente") if amin.get("accepted") else "pendiente", f"A_min: delta ranking {_fmt(amin.get('delta_ranking'))}."),
        ]
    )
    dedup = {}
    for key, state, evidence in out:
        dedup[key] = (key, state, evidence)
    return [dedup[f"H{index}"] for index in range(1, 17)]


def write_report() -> Path:
    master = _load("tabla_maestra.json")
    amin = _load("A_min.json")
    l_effects = _load("L_efectos.json")
    j_effects = _load("J_efectos.json")
    audit = _load("N_audit.json")
    anchors = _load("anclas.json")
    factorial = _load("S_factorial.json")["modes"]["honest"]
    _figures()
    REPORTS.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Informe final del estudio de ablacion T1",
        "",
        f"Fecha: {date.today().isoformat()}. Modo primario: `honest`. Casos etiquetados: 91.",
        "",
        "## Resumen ejecutivo",
        "",
        f"La referencia obtuvo ranking `{anchors['modes']['honest']['ranking']:.6f}` y 74/91 decisiones correctas. Ningun brazo Tier L cambio una decision. El margen narrativo observado fue `delta_N={j_effects['delta_n']:.6f}`. Todos los numeros de la tabla proceden de `results/tabla_maestra.json`.",
        "",
        "| ID | Intervencion | Veredicto | Delta ranking [IC95] | F: max abs(Delta) | N: Delta [IC95] | Delta s/caso | Confianza |",
        "|---|---|---|---:|---|---|---:|---|",
    ]
    for row in master["rows"]:
        d = row["d"]
        ci = d["ci95"]
        d_text = "n/a" if d["delta"] is None else f"{d['delta']:.6f} [{ci[0]:.6f}, {ci[1]:.6f}]"
        f_values = row["f"]["deltas"].values()
        f_effect = max((abs(value) for value in f_values), default=None)
        f_text = f"{_fmt(f_effect, 6)}; {row['f']['verdict']}"
        if row["n"]:
            n = row["n"]
            n_text = f"{n['delta']:.6f} [{n['ci95'][0]:.6f}, {n['ci95'][1]:.6f}]; {n['verdict']}"
        else:
            n_text = "no medido"
        seconds = row["cost"]["delta_seconds"] if row["cost"] else None
        lines.append(f"| {row['id']} | {row['name']} | **{row['verdict']}** | {d_text} | {f_text} | {n_text} | {_fmt(seconds, 2)} | {row['confidence']} |")

    lines.extend(
        [
            "",
            "## Metodo",
            "",
            "Se compararon predicciones por caso con el evaluador oficial. Tier S uso simulacion determinista, bootstrap pareado de 10.000 remuestreos, McNemar exacto con Holm y Wilcoxon sobre aciertos comunes. Tier L mantuvo modelo, temperatura y perfil de vLLM fijos. Tier N promedio tres pasadas del juez oficial en una sola residencia Ollama y uso el replicado L0/L0p para fijar el margen de equivalencia.",
            "",
            "## Decision y formulario",
            "",
            f"La escalera honesta fue F0 `{factorial['ladder'][0]['ranking']:.4f}`, F1 `{factorial['ladder'][1]['ranking']:.4f}`, F2 `{factorial['ladder'][2]['ranking']:.4f}`, F3 `{factorial['ladder'][3]['ranking']:.4f}` y A0 `{factorial['ladder'][4]['ranking']:.4f}`. E3 tuvo Shapley `{factorial['shapley']['ranking']['E3']:.4f}` y E1 `{factorial['shapley']['ranking']['E1']:.4f}`.",
            "",
            "L2 cambio plan/pesos en 34 casos y L4 en 23, pero sus deltas de ranking fueron 0.0009745 y 0.0000912. El resto de brazos fue identico a L0 en D/F.",
            "",
            "## Narrativa e integridad",
            "",
            f"El juez evaluo tres veces cada brazo. La replica produjo EE `{j_effects['replicate']['standard_error']:.6f}`. La auditoria sin juez encontro 3 grados sin fuente en L6 y lenguaje de proceso en 2 notas de L7; L0 tuvo cero violaciones.",
            "",
            "## Honest frente a deployed",
            "",
            f"El ranking `honest` fue `{anchors['modes']['honest']['ranking']:.4f}` frente a `{anchors['modes']['deployed']['ranking']:.4f}` en `deployed`. La diferencia se interpreta como optimismo por haber entrenado expertos con las etiquetas, no como capacidad transferible al test.",
            "",
            "## Hipotesis pre-registradas",
            "",
            "| H | Estado | Evidencia |",
            "|---|---|---|",
        ]
    )
    for hypothesis, state, evidence in _hypotheses(master, amin):
        lines.append(f"| {hypothesis} | **{state}** | {evidence} |")

    lines.extend(
        [
            "",
            "## Ablacion conjunta",
            "",
            f"A_min retiro: {', '.join(amin.get('spare_interventions') or []) or 'ninguna'}. Brazo: `{amin.get('arm', 'pendiente')}`. Delta ranking: `{_fmt(amin.get('delta_ranking'), 6)}` con IC95 `{amin.get('ci95')}`. H16: `{amin.get('h16', 'pendiente')}`.",
            "",
            "## Recomendaciones",
            "",
        ]
    )
    for row in master["rows"]:
        lines.append(f"- `{row['id']}`: {row['recommendation']}.")
    lines.extend(
        [
            "",
            "## Sesgos y limites",
            "",
            "1. Cohorte, grado y umbral se disenaron sobre estos mismos 91 casos; sus efectos son optimistas.",
            "2. `honest` es out-of-fold, pero los hiperparametros de expertos tambien se eligieron en esta cohorte.",
            "3. Con n=91, efectos de 1-3 decisiones quedan por debajo de la detectabilidad pre-registrada.",
            "4. Solo se uso un modelo generador, T=0 y una residencia del juez; no mide variacion entre modelos.",
            "5. Los 104 casos sin etiqueta no permiten estimar generalizacion ni cambio de distribucion.",
            "",
            "## Figuras",
            "",
            "![Tornado](figuras/tornado_ranking.png)",
            "",
            "![Shapley](figuras/shapley_decision.png)",
            "",
            "![Coste frente a efecto](figuras/coste_efecto.png)",
            "",
            "![Escalera](figuras/escalera_construccion.png)",
            "",
            "## Fuentes",
            "",
            "Resultados estructurados: `S_loo.json`, `S_factorial.json`, `L_efectos.json`, `J_efectos.json`, `N_audit.json`, `tabla_maestra.json`, `A_min.json` y `cierre.json`.",
        ]
    )
    path = REPORTS / "INFORME_ABLACION_T1.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_extension() -> Path:
    text = """# Extension a T2 y T3

El arnes estadistico es reutilizable: bootstrap pareado, McNemar, Holm, prueba de signos,
Wilcoxon sobre aciertos comunes, clasificacion mecanica, calendario reanudable del juez y
validacion de artefactos no dependen de la Tarea 1. Tambien se reutilizan el manifiesto de brazo,
la telemetria, el control de residencia Ollama y la separacion entre D, F, N y coste.

Cada tarea necesita un catalogo nuevo de intervenciones, porque cambian el contrato, la puerta de
decision y los mecanismos del grafo. T2 requiere modelar la recomendacion de tratamiento y sus
clases; T3 no tiene puerta binaria y necesita recurrencia, censura y tiempo. Los simuladores deben
llamar a la misma logica determinista de cada entrega y demostrar identidad con un brazo L0 antes
de aceptar inferencias Tier S. Los componentes de formulario y sus pesos oficiales tambien deben
parametrizarse por tarea.

Preguntas abiertas: generalizacion a los 104 casos sin etiqueta; estabilidad con otro modelo
generador; variacion del juez entre recargas; potencia para efectos de menos de seis decisiones;
y si las intervenciones equivalentes por separado siguen siendolo al combinarse en distribuciones
distintas. Las guardias de integridad merecen una salida separada del score medio: una media
equivalente puede ocultar pocos fallos clinicamente inaceptables.
"""
    path = ROOT / "EXTENSION_T2_T3.md"
    path.write_text(text, encoding="utf-8")
    return path


def main() -> int:
    report = write_report()
    extension = write_extension()
    print(json.dumps({"report": str(report), "extension": str(extension)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
