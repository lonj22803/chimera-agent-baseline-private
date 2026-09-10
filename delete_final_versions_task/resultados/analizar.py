"""Lee la corrida de ``resultados/`` y destila lo que va al informe.

No vuelve a puntuar nada: las notas vienen de ``scores/*.json``, que los produce
el evaluador **oficial**. Lo que se calcula aquí es la otra mitad de la pregunta
—cómo llegó cada junta a su decisión— leyendo las actas y los ``summary.jsonl``:
qué peldaño del protocolo disparó, quién acabó de portavoz, cuántas veces habló
la sala, dónde entraron los respaldos y qué costó cada caso.

    PYTHONPATH=src:. .venv/bin/python -m delete_final_versions_task.resultados.analizar
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import mean, median

RES = Path(__file__).resolve().parent
REPO = RES.parents[1]


def jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_json(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def truth(task: int) -> dict[str, dict]:
    """El ground truth tal y como lo lee el evaluador, por case_id."""
    root = REPO / "data" / f"task{task}" / "ground_truth"
    out = {}
    for case in sorted(p for p in root.iterdir() if p.is_dir()):
        for f in case.iterdir():
            if f.suffix == ".json":
                out.setdefault(case.name, {})[f.name] = load_json(f)
    return out


def boards_stats(task: int) -> dict:
    """Estadística de las actas: cuántas intervenciones y quién habló."""
    run = RES / f"task_{task}"
    files = sorted((run / "boards").glob("*.json"))
    if not files:  # T3 guarda el acta junto a la salida del caso
        files = sorted((run / "output" / f"task{task}").glob("*/acta.json"))
    speakers: Counter = Counter()
    lengths, passes = [], []
    for f in files:
        board = load_json(f) or {}
        items = board.get("interventions") or []
        lengths.append(len(items))
        passes.append(max((i.get("pass_", 1) or 1) for i in items) if items else 1)
        for i in items:
            speakers[i.get("speaker")] += 1
    return {
        "n_actas": len(files),
        "intervenciones_media": round(mean(lengths), 2) if lengths else None,
        "intervenciones_min": min(lengths) if lengths else None,
        "intervenciones_max": max(lengths) if lengths else None,
        "casos_con_reapertura": sum(1 for p in passes if p > 1),
        "turnos_por_participante": dict(speakers.most_common()),
    }


def coste(rows: list[dict], task: int) -> dict:
    secs = [r["seconds"] for r in rows if r.get("seconds") is not None]
    tel = jsonl(RES / f"task_{task}" / "telemetry.jsonl")
    if task == 3:  # su telemetría es por caso, no por papel
        secs = secs or [t["seconds"] for t in tel if t.get("seconds")]
    prompt_tok = [r.get("tel_prompt_tokens") for r in rows if r.get("tel_prompt_tokens")]
    calls = [r.get("tel_llm_calls") for r in rows if r.get("tel_llm_calls")]
    return {
        "segundos_por_caso_media": round(mean(secs), 1) if secs else None,
        "segundos_por_caso_mediana": round(median(secs), 1) if secs else None,
        "minutos_totales": round(sum(secs) / 60, 1) if secs else None,
        "tokens_entrada_por_caso": round(mean(prompt_tok)) if prompt_tok else None,
        "llamadas_llm_por_caso": round(mean(calls), 1) if calls else None,
        "vram_pico_mb": max((r.get("tel_peak_vram_mb") or 0) for r in rows) or None,
    }


def mecanismo(task: int, rows: list[dict]) -> dict:
    """Cómo se decidió: el peldaño, el portavoz y las guardias que saltaron."""
    ok = [r for r in rows if r.get("ok", True)]
    out: dict = {
        "casos": len(rows),
        "casos_ok": len(ok),
        "casos_con_error": [r["case_id"] for r in rows if not r.get("ok", True)],
    }
    if task in (1, 2):
        out |= {
            "decision": dict(Counter(str(r.get("decision")) for r in ok).most_common()),
            "confianza": dict(Counter(str(r.get("confidence")) for r in ok).most_common()),
            "peldano_del_protocolo": dict(Counter(peldano(task, r) for r in ok).most_common()),
            "portavoz": dict(Counter(str(r.get("protocol_who")) for r in ok).most_common()),
            "esquema_valido": sum(1 for r in ok if r.get("schema_ok")),
            "nota_de_respaldo": sum(1 for r in ok if r.get("fallback_note")),
            "formulario_de_respaldo": sum(1 for r in ok if r.get("fallback_form")),
            "presidente_reintentos": dict(Counter(r.get("chair_attempts") for r in ok).most_common()),
            "prosa_retada": sum(1 for r in ok if r.get("prose_challenged")),
            "verificador_reabre": sum(1 for r in ok if (r.get("passes") or 1) > 1),
            "avisos": dict(Counter(w for r in ok for w in (r.get("warnings") or [])).most_common(10)),
            "palabras_de_la_nota_media": round(mean([r["note_words"] for r in ok if r.get("note_words")]), 1)
            if any(r.get("note_words") for r in ok) else None,
        }
    if task == 1:
        con_grado = [r for r in ok if r.get("grade") is not None]
        out |= {
            "grado_documentado_hallado": len(con_grado),
            "casos_en_vigilancia": sum(1 for r in ok if r.get("on_surveillance")),
            "biblioteca_self_match": sum(1 for r in ok if r.get("library_self_match")),
            "imagen_convocada": sum(1 for r in ok if r.get("need_image")),
        }
    if task == 3:
        meses = [r["months_to_recurrence"] for r in ok if r.get("months_to_recurrence") is not None]
        out |= {
            "event": dict(Counter(r.get("event") for r in ok).most_common()),
            "meses_mediana": round(median(meses), 1) if meses else None,
            "meses_min": round(min(meses), 1) if meses else None,
            "meses_max": round(max(meses), 1) if meses else None,
            "respaldo": sum(1 for r in ok if r.get("fallback")),
            "portavoz": dict(Counter(str((r.get("uncertainty") or {}).get("basis", "CAPRA-S")) for r in ok).most_common()),
        }
    return out


def peldano(task: int, row: dict) -> str:
    """El peldaño del protocolo, sin el valor concreto que lo disparó.

    ``protocol_rule`` lleva dentro la p del voto o el grado hallado, así que
    agrupar por la cadena cruda daría un grupo por caso. En T2 la regla es única
    y lo que discrimina es qué experto acabó de portavoz.
    """
    if task == 2:
        return str(row.get("protocol_who"))
    rule = str(row.get("protocol_rule"))
    for prefijo, nombre in (("cohort criterion", "1 · criterio de cohorte"),
                            ("documented prior grade", "2 · grado documentado"),
                            ("weighted vote", "3 · voto ponderado")):
        if rule.startswith(prefijo):
            return nombre
    return rule


def aciertos(task: int, rows: list[dict]) -> dict:
    """Reparte el acierto por el mecanismo que decidió cada caso.

    No sustituye al evaluador: sólo dice qué peldaño se equivoca, que es lo que
    el agregado oficial no puede decir porque no conoce el protocolo.
    """
    if task == 3:
        return {}
    gt = truth(task)
    key = {1: "prostate-biopsy-decision.json", 2: "prostate-treatment-decision.json"}[task]
    por_regla: dict[str, list[bool]] = {}
    for r in rows:
        if not r.get("ok", True):
            continue
        ref = (gt.get(r["case_id"]) or {}).get(key)
        if ref is None:
            continue
        if isinstance(ref, dict):
            ref = ref.get("primary") or ref.get("biopsy_decision")
        por_regla.setdefault(peldano(task, r), []).append(str(r.get("decision")) == str(ref))
    return {
        regla: {"n": len(v), "aciertos": sum(v), "acierto": round(sum(v) / len(v), 4)}
        for regla, v in sorted(por_regla.items(), key=lambda kv: -len(kv[1]))
    }


def componentes(rows: list[dict]) -> dict:
    """Media de cada componente sobre los casos que pasan la puerta.

    El agregado oficial publica sólo tres de los seis; los otros hay que
    promediarlos de las filas, y sólo sobre los casos que pasan la puerta, que
    son los únicos donde el evaluador llega a calcularlos.
    """
    passed = [r for r in rows if r.get("decision_score") == 1.0] or rows
    out = {}
    for key in ("rationale_score", "variable_weight_score", "confidence_score",
                "important_decisive_factor_score", "tool_score", "section_grounding_score"):
        vals = [r[key] for r in passed if r.get(key) is not None]
        out[key] = round(mean(vals), 6) if vals else None
    return out


def main() -> None:
    no_judge = load_json(RES / "scores" / "no_judge.json") or {}
    resultado = {"sin_juez": no_judge, "con_juez": {}, "componentes": {}, "tareas": {}}
    for task in (1, 2, 3):
        j = load_json(RES / "scores" / f"judge_task{task}.json")
        if j:
            resultado["con_juez"][f"task{task}"] = j.get("aggregate", {})
            resultado["componentes"][f"task{task}"] = componentes(j.get("rows") or [])
        rows = jsonl(RES / f"task_{task}" / "summary.jsonl")
        resultado["tareas"][f"task{task}"] = {
            "mecanismo": mecanismo(task, rows),
            "acierto_por_peldano": aciertos(task, rows),
            "actas": boards_stats(task),
            "coste": coste(rows, task),
        }

    ranking = {}
    for task in (1, 2, 3):
        sj = (no_judge.get(f"task{task}") or {}).get("ranking_score")
        cj = (resultado["con_juez"].get(f"task{task}") or {}).get("ranking_score")
        ranking[f"task{task}"] = {"sin_juez": sj, "con_juez": cj}
    pesos = {"task1": 2.0, "task2": 2.0, "task3": 1.0}
    overall = {}
    for modo in ("sin_juez", "con_juez"):
        vals = {t: ranking[t][modo] for t in pesos if ranking[t][modo] is not None}
        if len(vals) == 3:
            overall[f"overall_{modo}"] = round(
                sum(v * pesos[t] for t, v in vals.items()) / sum(pesos.values()), 10)
    ranking |= overall
    resultado["ranking"] = ranking

    out = RES / "scores" / "analisis.json"
    out.write_text(json.dumps(resultado, indent=2, ensure_ascii=False, default=str))
    print(json.dumps(ranking, indent=2))
    print(f"\nEscrito {out}")


if __name__ == "__main__":
    main()
