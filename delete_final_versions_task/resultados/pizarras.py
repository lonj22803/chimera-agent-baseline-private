"""Construye el índice navegable de las actas de las tres juntas.

Los runners ya persisten una pizarra por caso. Lo que falta para poder *leerlas*
es saber a cuál ir: este script las ordena por lo que las hace interesantes —el
caso donde el protocolo se equivocó, el que el verificador tuvo que reabrir, el
que acabó en respaldo— y escribe `PIZARRAS.md` con un enlace a cada una.

    PYTHONPATH=src:. .venv/bin/python -m delete_final_versions_task.resultados.pizarras
"""
from __future__ import annotations

import json
from pathlib import Path

from .analizar import jsonl, peldano, truth

RES = Path(__file__).resolve().parent
GT_KEY = {1: "prostate-biopsy-decision.json", 2: "prostate-treatment-decision.json",
          3: "prostate-time-to-recurrence-or-last-follow-up.json"}
TITULO = {1: "Tarea 1 · decisión de biopsia", 2: "Tarea 2 · decisión de tratamiento",
          3: "Tarea 3 · pronóstico posoperatorio"}


def acta_path(task: int, case_id: str) -> tuple[Path, Path] | None:
    """(markdown, json) del acta, en el sitio donde la deja el runner de la tarea."""
    run = RES / f"task_{task}"
    md, js = run / "boards" / f"{case_id}.md", run / "boards" / f"{case_id}.json"
    if md.exists():
        return md, js
    md, js = (run / "output" / f"task{task}" / case_id / n for n in ("acta.md", "acta.json"))
    return (md, js) if md.exists() else None


def esperado(task: int, gt: dict, case_id: str):
    ref = (gt.get(case_id) or {}).get(GT_KEY[task])
    if isinstance(ref, dict):
        return ref.get("primary") or ref.get("biopsy_decision") or ref.get("event")
    return ref


def filas(task: int) -> list[dict]:
    gt = truth(task)
    out = []
    for r in jsonl(RES / f"task_{task}" / "summary.jsonl"):
        cid = r.get("case_id")
        paths = acta_path(task, cid)
        ref = esperado(task, gt, cid)
        dec = r.get("decision") if task in (1, 2) else r.get("months_to_recurrence")
        acierto = None if task == 3 or ref is None else (str(dec) == str(ref))
        out.append({
            "case_id": cid,
            "acta": paths[0].relative_to(RES).as_posix() if paths else None,
            "decision": dec,
            "esperado": ref,
            "acierto": acierto,
            "peldano": peldano(task, r) if task in (1, 2) else "CAPRA-S",
            "confianza": r.get("confidence"),
            "reabierta": (r.get("passes") or 1) > 1,
            "respaldo": bool(r.get("fallback_note") or r.get("fallback_form") or r.get("fallback")),
            "intervenciones": r.get("n_interventions"),
            "segundos": r.get("seconds"),
            "ok": r.get("ok", True),
        })
    return out


def tabla(rows: list[dict], task: int) -> list[str]:
    cab = ("| caso | acta | peldaño | decisión | referencia | ✓ | int. |"
           if task in (1, 2) else "| caso | acta | meses | event | respaldo | int. |")
    sep = "|---|---|---|---|---|---|---|" if task in (1, 2) else "|---|---|---|---|---|---|"
    out = [cab, sep]
    for r in rows:
        link = f"[acta]({r['acta']})" if r["acta"] else "—"
        if task in (1, 2):
            marca = "" if r["acierto"] is None else ("✓" if r["acierto"] else "**✗**")
            out.append(f"| `{r['case_id']}` | {link} | {r['peldano']} | {r['decision']} | "
                       f"{r['esperado']} | {marca} | {r['intervenciones'] or ''} |")
        else:
            meses = f"{r['decision']:.1f}" if isinstance(r["decision"], (int, float)) else r["decision"]
            out.append(f"| `{r['case_id']}` | {link} | {meses} | {r['esperado']} | "
                       f"{'sí' if r['respaldo'] else ''} | {r['intervenciones'] or 11} |")
    return out


def main() -> None:
    doc = [
        "# Las pizarras, caso por caso",
        "",
        "Cada junta deja un acta: una intervención por turno, numeradas de forma global",
        "y monótona, con lo que dijo cada participante literalmente y lo que el código",
        "calculó de ese turno. Es la traza de cómo se enfrentó el problema, no un resumen",
        "escrito después. Están en `task_N/boards/<caso>.{md,json}` (tareas 1 y 2) y en",
        "`task_3/output/task3/<caso>/acta.{md,json}` (tarea 3).",
        "",
        "Este índice existe para saber a cuál ir. Los casos se listan **primero los que",
        "el protocolo falló**, luego los que el verificador reabrió o acabaron en respaldo,",
        "y después el resto por orden de caso.",
        "",
    ]
    resumen = {}
    for task in (1, 2, 3):
        rows = filas(task)
        if not rows:
            continue
        fallos = [r for r in rows if r["acierto"] is False]
        raros = [r for r in rows if r["acierto"] is not False and (r["reabierta"] or r["respaldo"])]
        resto = [r for r in rows if r not in fallos and r not in raros]
        resumen[task] = {"n": len(rows), "fallos": len(fallos), "raros": len(raros)}
        doc += [f"## {TITULO[task]}", "",
                f"{len(rows)} actas. {len(fallos)} decisiones contra la referencia, "
                f"{len(raros)} con reapertura o respaldo.", ""]
        if fallos:
            doc += [f"### Donde el protocolo se equivocó ({len(fallos)})", "",
                    "Son las actas que más enseñan: el mecanismo está escrito y se ve "
                    "qué peldaño disparó y con qué evidencia.", ""]
            doc += tabla(fallos, task) + [""]
        if raros:
            doc += [f"### Reaperturas y respaldos ({len(raros)})", ""]
            doc += tabla(raros, task) + [""]
        doc += [f"<details><summary>Los {len(resto)} restantes</summary>", ""]
        doc += tabla(resto, task) + ["", "</details>", ""]

    (RES / "PIZARRAS.md").write_text("\n".join(doc) + "\n")
    print(json.dumps(resumen, indent=2))
    print(f"Escrito {RES / 'PIZARRAS.md'}")


if __name__ == "__main__":
    main()
