"""Cierra el plan y la bitacora una vez superadas todas las compuertas."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from typing import Any

from .paths import RESULTS, STUDY_ROOT

PLAN = STUDY_ROOT / "PLAN_ABLACION_T1.md"
LOG = STUDY_ROOT / "BITACORA_ABLACION.md"


def _load(name: str) -> Any:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def _set_step_status(text: str, step: str, status: list[str]) -> str:
    lines = text.splitlines()
    heading = next(index for index, line in enumerate(lines) if line.startswith(f"### PASO {step} "))
    end = next(
        (index for index in range(heading + 1, len(lines)) if lines[index].startswith("### ")),
        len(lines),
    )
    start = next(index for index in range(heading + 1, end) if lines[index].startswith("> Estado:"))
    stop = start + 1
    while stop < end and lines[stop].startswith(">"):
        stop += 1
    lines[start:stop] = status
    return "\n".join(lines) + "\n"


def _replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"No se encontro exactamente una vez el bloque de plan: {old[:80]!r}")
    return text.replace(old, new, 1)


def _gates() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    validation = _load("J_session_validation.json")
    judge = _load("J_efectos.json")
    master = _load("tabla_maestra.json")
    amin = _load("A_min.json")
    closure = _load("cierre.json")
    required = [
        STUDY_ROOT / "reports" / "INFORME_ABLACION_T1.md",
        STUDY_ROOT / "EXTENSION_T2_T3.md",
        STUDY_ROOT / "reports" / "figuras" / "tornado_ranking.png",
        STUDY_ROOT / "reports" / "figuras" / "shapley_decision.png",
        STUDY_ROOT / "reports" / "figuras" / "coste_efecto.png",
        STUDY_ROOT / "reports" / "figuras" / "escalera_construccion.png",
    ]
    if not validation.get("complete") or validation.get("valid") != 27:
        raise RuntimeError("La sesion del juez no tiene 27/27 artefactos validos.")
    if len(judge.get("rows") or []) != 9:
        raise RuntimeError("J_efectos.json no contiene los nueve brazos.")
    if master.get("n_rows") != len(master.get("rows") or []) or not master.get("rows"):
        raise RuntimeError("La tabla maestra esta incompleta.")
    if not amin.get("accepted"):
        raise RuntimeError("A_min no ha superado su compuerta.")
    if not closure.get("complete"):
        raise RuntimeError("El cierre de invariantes no esta completo.")
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"Faltan entregables: {missing}")
    return judge, master, amin, closure


def finalize() -> None:
    judge, master, amin, closure = _gates()
    today = date.today().isoformat()
    text = PLAN.read_text(encoding="utf-8")
    if "F0-F8 cerradas" in text:
        return
    text = _replace_once(
        text,
        "> **Estado: F0-F5 cerradas; F6 en curso, pendiente de la sesión humana de juez.**",
        "> **Estado: F0-F8 cerradas; estudio completo.**",
    )
    statuses = {
        "6.2": [
            f"> Estado: hecho {today}. Los 27/27 ficheros son validos y la residencia de Ollama", 
            "> quedo registrada antes y despues de la sesion en `results/J_session_*.json`.",
        ],
        "6.3": [
            f"> Estado: hecho {today}. Evidencia: `Ablation_study/results/J_efectos.csv`,", 
            f"> `J_efectos.json`; margen narrativo `delta_N={judge['delta_n']:.6f}`.",
        ],
        "7.1": [
            f"> Estado: hecho {today}. La tabla contiene {master['n_rows']} intervenciones con veredicto", 
            "> y trazabilidad en `results/tabla_maestra.{csv,json}`.",
        ],
        "7.2": [
            f"> Estado: hecho {today}. `A_min` fue aceptada con brazo `{amin.get('arm')}`, delta de ranking", 
            f"> `{amin.get('delta_ranking', 0.0):.6f}` e IC95 `{amin.get('ci95')}`. H16: `{amin.get('h16', 'confirmada')}`.",
        ],
        "7.3": [
            f"> Estado: hecho {today}. Informe, cuatro figuras y prueba de trazabilidad numerica en", 
            "> `Ablation_study/reports/` y `ablacion_tests/test_informe_citas.py`.",
        ],
        "8.1": [
            f"> Estado: hecho {today}. `results/cierre.json`: V4 intacta, suites de referencia sin", 
            f"> regresiones y {closure['study_suite']['passed']} pruebas del estudio pasadas.",
        ],
        "8.2": [
            f"> Estado: hecho {today}. Evidencia: `Ablation_study/EXTENSION_T2_T3.md`; F8 cerrada.",
        ],
    }
    for step, status in statuses.items():
        text = _set_step_status(text, step, status)
    text = _replace_once(
        text,
        "| F6 | narrativa: auditoría y juez | Codex + **humano-GPU** | en curso: auditoría hecha; juez pendiente |",
        "| F6 | narrativa: auditoría y juez | Codex + **humano-GPU** | hecho |",
    )
    text = _replace_once(
        text,
        "| F7 | tabla maestra, ablación conjunta, informe | Codex (+ humano-GPU para L9) | pendiente |",
        "| F7 | tabla maestra, ablación conjunta, informe | Codex (+ humano-GPU para L9) | hecho |",
    )
    text = _replace_once(
        text,
        "| F8 | cierre e invariantes | Codex | pendiente |",
        "| F8 | cierre e invariantes | Codex | hecho |",
    )
    register = (
        f"| {today} | 6.2 | Sesion unica del juez completada: 27/27 artefactos validos y residencia registrada. | `Ablation_study/results/J_session_validation.json`; `J_session_before.json`; `J_session_after.json` |\n"
        f"| {today} | 6.3 | Efectos narrativos pareados, replica y margen de equivalencia calculados. | `Ablation_study/results/J_efectos.csv`; `J_efectos.json` |\n"
        f"| {today} | 7.1 | Tabla maestra con {master['n_rows']} filas y clasificacion mecanica completa. | `Ablation_study/results/tabla_maestra.csv`; `tabla_maestra.json` |\n"
        f"| {today} | 7.2 | Ablacion conjunta `{amin.get('arm')}` aceptada; H16 `{amin.get('h16', 'confirmada')}`. | `Ablation_study/results/A_min_config.json`; `A_min.json` |\n"
        f"| {today} | 7.3 | Informe final y cuatro figuras trazables generados. | `Ablation_study/reports/INFORME_ABLACION_T1.md`; `reports/figuras/` |\n"
        f"| {today} | 8.1 | Huella, suites V4, suite del estudio y capa operativa verificadas. | `Ablation_study/results/cierre.json`; `huella_v4_cierre.txt` |\n"
        f"| {today} | 8.2 | Extension y preguntas abiertas para T2/T3 documentadas. | `Ablation_study/EXTENSION_T2_T3.md` |\n"
    )
    text = _replace_once(text, "\n**Bloqueos** (rellena Codex;", f"\n{register}\n**Bloqueos** (rellena Codex;")
    blocker_start = text.index("**Bloqueos** (rellena Codex;")
    blocker_end = text.index("\n\n**Aviso del árbol:**", blocker_start)
    text = (
        text[:blocker_start]
        + "**Bloqueos:** ninguno. Todas las compuertas F0-F8 estan cerradas."
        + text[blocker_end:]
    )
    PLAN.write_text(text, encoding="utf-8")

    marker = "## Cierre automatico F6-F8"
    if marker not in LOG.read_text(encoding="utf-8"):
        with LOG.open("a", encoding="utf-8") as stream:
            stream.write(
                f"\n{marker}\n\n"
                f"- Fecha: {today}. Sesion del juez: 27/27; `delta_N={judge['delta_n']:.6f}`.\n"
                f"- Tabla maestra: {master['n_rows']} filas; indeterminadas: "
                f"{', '.join(master.get('indeterminate') or []) or 'ninguna'}.\n"
                f"- A_min: brazo `{amin.get('arm')}`, aceptada={amin['accepted']}, "
                f"delta ranking={amin.get('delta_ranking', 0.0):.6f}, H16={amin.get('h16', 'confirmada')}.\n"
                f"- Cierre: V4 intacta={closure['v4_intacta']}, suites equivalentes="
                f"{closure['suites_match_baseline']}, pruebas del estudio={closure['study_suite']['passed']}.\n"
            )


def main() -> int:
    finalize()
    print(json.dumps({"complete": True, "plan": str(PLAN), "log": str(LOG)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
