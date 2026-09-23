"""Genera el informe final trazable de la extension T2/T3."""

from __future__ import annotations

import json

from .paths import REPORTS, RESULTS, ensure_dirs


def _load(name: str):
    return json.loads((RESULTS / name).read_text())


def _f(value, digits=4):
    return "n/d" if value is None else f"{float(value):.{digits}f}"


def main() -> None:
    ensure_dirs()
    deterministic = _load("D_F_effects.json")
    narrative = _load("J_effects.json")
    t2_cpu = _load("T2_cpu.json")
    t3_cpu = _load("T3_cpu.json")
    effects = {row["arm"]: row for row in narrative["effects"]}
    lines = [
        "# Informe de ablacion T2/T3",
        "",
        "Fecha de cierre: 2026-09-23. Estudio confirmatorio sobre el codigo actual y "
        "retrospectivo respecto a los artefactos entrenados. No es validacion externa.",
        "",
        "## Resultado ejecutivo",
        "",
        "T2 admite eliminar cuatro papeles LLM del flujo (EAU, moderador, registrador y "
        "verificador como generadores) y conservar una sola llamada del presidente. Los cinco "
        "expertos numericos se conservan: la ablacion pura de cualquiera de E2/E3/E4/E5 "
        "desactiva el quorum de aptitud y cambia tres decisiones.",
        "",
        "T3 se reduce al motor ASGDE seleccionado, CAPRA para la politica de evento, el mapa de "
        "horizonte y una nota determinista. Los turnos SURGICAL, DIGITAL y FUSION de la "
        "conferencia completa son explicativos y no alimentan la salida numerica; en esta cohorte "
        "el presidente tampoco mejora la narrativa medida por el juez.",
        "",
        "## Recomendacion",
        "",
        "- **T2: adoptar como candidato `T2-Lmin`.** Conserva D/F exactamente, sube la media "
        "narrativa de 0.8256 a 0.8451 y su delta L0-var queda dentro del margen N. Reduce llamadas "
        "539 -> 72 (-86.6%), tokens de entrada 1,708,214 -> 93,991 (-94.5%) y tiempo "
        "41.43 -> 1.53 s/caso (-96.3%).",
        "- **T2-Ldet no sustituye al presidente cuando N importa.** Conserva D/F, pero pierde "
        "0.0872 de rationale (IC95 0.0595 a 0.1159), por encima del margen 0.0349.",
        "- **T3: adoptar como candidato `T3-Ldet` en la superficie evaluada.** Conserva los 75 "
        "pares `(event, months)` y mejora rationale 0.0796 frente a L0 (IC95 de L0-var -0.1311 "
        "a -0.0284), con cero llamadas. Es evidencia interna dependiente del juez, no una prueba "
        "de superioridad clinica de una plantilla.",
        "- **T3-Lmin no aporta una frontera coste/calidad mejor.** Conserva D/F, pero apenas baja "
        "86 -> 83 llamadas y su perdida narrativa puntual de 0.0436 tiene un IC amplio que cruza "
        "cero y excede el margen N. Se clasifica como indeterminada.",
        "",
        "## Brazos y efectos",
        "",
        "| Brazo | n | Ranking | Identidad D/F | Llamadas LLM | s/caso | Rationale medio | Delta N L0-var | IC95 |",
        "|---|---:|---:|---|---:|---:|---:|---:|---|",
    ]
    for row in deterministic["arms"]:
        arm = row["arm"]
        judged = effects[arm]
        lines.append(
            f"| {arm} | {row['predictions']} | {_f(row['aggregate']['ranking_score'])} | "
            f"{'si' if row['identity_with_l0']['exact'] else 'no'} | {row['cost']['llm_calls']} | "
            f"{_f(row['cost']['seconds_per_case'], 2)} | {_f(judged['variant'])} | "
            f"{_f(judged['delta'])} | [{_f(judged['ci95'][0])}, {_f(judged['ci95'][1])}] |"
        )
    t2_drop = next(row for row in t2_cpu["variants"] if row["id"] == "drop_expert_three")
    capra = next(row for row in t3_cpu["variants"] if row["id"] == "capra")
    constant = next(row for row in t3_cpu["variants"] if row["id"] == "constant60_capra_event")
    lines += [
        "",
        "## Tier CPU",
        "",
        f"- T2 completa: ranking {_f(t2_cpu['baseline']['ranking'])}, "
        f"decision {_f(t2_cpu['baseline']['gate'])}. Retirar E3 cambia "
        f"{t2_drop['n_changed']} casos y pierde {_f(t2_drop['bootstrap']['ranking_score']['delta'])} "
        "de ranking. E2/E4 no votan, pero su estado de fiabilidad participa en el quorum; "
        "borrarlos sin redisenar y revalidar el quorum no es equivalente.",
        f"- T3 selected: c-index {_f(t3_cpu['baseline']['ranking_score'])}. CAPRA queda en "
        f"{_f(capra['aggregate']['ranking_score'])} (delta {_f(capra['bootstrap']['ranking_score']['delta'])}); "
        f"un horizonte constante cae a {_f(constant['aggregate']['ranking_score'])}.",
        "- Forzar event=0 conserva el c-index por definicion, pero empeora la exactitud de evento; "
        "ranking, evento y calibracion temporal deben reportarse por separado.",
        "",
        "## Arquitecturas",
        "",
        "```text",
        "T2 V4: 5 expertos + EAU + moderador + registrador + verificador + presidente",
        "T2 min: 5 expertos + controles/registro deterministas + presidente",
        "T2 det: 5 expertos + controles/registro/nota deterministas",
        "",
        "T3 V4: CAPRA + 3 turnos asesores + protocolo + horizonte + controles + presidente",
        "T3 min: selected-ASGDE + CAPRA-event + horizonte + digest + presidente",
        "T3 det: selected-ASGDE + CAPRA-event + horizonte + nota determinista",
        "```",
        "",
        "## Decision por componente",
        "",
        "| Tarea | Componente | Decision | Evidencia |",
        "|---|---|---|---|",
        "| T2 | E1-E5 y quorum | conservar | la unica variante CPU sin cambios es la completa; una baja altera 3 casos |",
        "| T2 | EAU/moderador/registrador/verificador LLM | sustituir por codigo | T2-Lmin tiene identidad D/F y N dentro del margen |",
        "| T2 | presidente | conservar | T2-Ldet pierde N por encima del margen |",
        "| T3 | selected-ASGDE | conservar prudentemente | +0.0863 c-index vs CAPRA, pero IC95 [-0.0062, 0.2075] |",
        "| T3 | horizonte monotono | conservar | quitar orden temporal lleva c-index a 0.5000; IC de perdida excluye cero |",
        "| T3 | SURGICAL/DIGITAL/FUSION y controles discursivos | retirar | no tienen ruta causal a event/months |",
        "| T3 | presidente | retirar en esta superficie | la nota determinista mejora N y elimina 86 llamadas |",
        "",
        "## Decision por nivel",
        "",
        "- `D/F`: una variante reducida solo se recomienda si tiene identidad exacta con L0. "
        "Los margenes bootstrap se conservan como diagnostico secundario.",
        "- `N`: se usa el margen prerregistrado `max(0.03, 2*EE)` calculado por tarea sobre "
        "las tres pasadas del control. La nota determinista se interpreta como intercambio de "
        "coste por narrativa, no como sustitucion automatica.",
        "- `C`: llamadas, tokens y tiempo proceden de la telemetria de cada brazo; L0 T2 es "
        "el artefacto V4 completo ya ejecutado, con procedencia declarada en `arm.json`.",
        "",
        "## Limitaciones",
        "",
        "Los 72 casos T2 participaron en el desarrollo de los expertos. T3 usa predicciones OOF "
        "sobre 75 casos, pero la seleccion del sistema tambien fue informada por esa cohorte. Los "
        "IC describen estabilidad pareada interna y no garantizan generalizacion. El juez LLM "
        "es variable incluso con temperatura cero; por eso se promedian tres pasadas en una sola "
        "residencia. Ninguna reduccion se adopto en V4 durante este estudio.",
        "",
        "## Trazabilidad",
        "",
        "Resultados: `T2_cpu.json`, `T3_cpu.json`, `D_F_effects.json`, `J_effects.json` y "
        "`cierre.json` bajo `Ablation_study/T2_T3/results/`. Corridas y actas estan bajo "
        "`Ablation_study/T2_T3/runs/`.",
    ]
    path = REPORTS / "INFORME_ABLACION_T2_T3.md"
    path.write_text("\n".join(lines) + "\n")
    print(path)


if __name__ == "__main__":
    main()
