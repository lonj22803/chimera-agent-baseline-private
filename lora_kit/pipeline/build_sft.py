"""Construye las trayectorias de entrenamiento (SFT) para las TRES tareas.

Cada caso con ground truth genera dos ejemplos, porque en inferencia el mismo
modelo se llama en dos contextos:

* ``react``     system + caso -> llamadas a herramientas (una por turno) con sus
                respuestas reales -> texto final de razonamiento.
* ``form_fill`` prompt del nodo form-fill -> JSON del formulario.

Los mensajes se escriben en el formato OpenAI exacto que ``ChatVLLM`` entrega a
``llm.chat`` (``_to_openai_messages``): turnos de asistente con ``content: null`` y
``tool_calls``; turnos ``tool`` con el contenido en bloques de texto.

    python pipeline/build_sft.py --data-root ../data --out runs/sft.jsonl \
        --folds runs/folds.json --tasks 1 2 3

Estructura de datos esperada (la del reto):

    <data-root>/task<N>/agent_input/<case>/{structured-prompt,*-clinical-data}.json
    <data-root>/task<N>/ground_truth/<case>/<los dos ficheros de salida de la tarea>
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contract as C  # noqa: E402

# Etiqueta legible y clave del structured-prompt.json de cada variable ponderable.
VARIABLE_LABELS: dict[str, tuple[str, str | None]] = {
    "bx": ("prior biopsy", "bx"),
    "fh": ("family history", None),
    "age": ("age", "age"),
    "dre": ("DRE", "dre"),
    "psa": ("PSA", "psa"),
    "vol": ("prostate volume", "vol"),
    "psad": ("PSA density", "psad"),
    "cspca": ("csPCa probability", "cspca"),
    "pirads": ("PI-RADS", "pirads"),
    "comorbidity": ("comorbidity", "medhx"),
    "ct": ("clinical stage", "ct"),
    "bx_isup": ("biopsy ISUP grade group", "bx_isup"),
    "bx_gl_prim": ("primary Gleason pattern", "bx_gl_prim"),
    "bx_gl_sec": ("secondary Gleason pattern", "bx_gl_sec"),
}

SECTION_LABELS = {
    "get_mri_report": "MRI report",
    "get_pathology_report": "Biopsy pathology report",
    "get_surgical_pathology_report": "Surgical pathology report",
    "get_psa_trend": "PSA trend",
    "get_previous_notes": "Previous notes",
    "get_lab_results": "Laboratory results",
    "get_family_history": "Family history",
}

T3_DEFAULT_TOOLS = [
    "get_mri_report",
    "get_pathology_report",
    "get_surgical_pathology_report",
    "get_previous_notes",
    "get_family_history",
]


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_labelled_cases(data_root: Path, task: int) -> list[dict[str, Any]]:
    """Casos con entrada y ground truth. Los que no tienen GT se ignoran."""
    inp = data_root / f"task{task}" / "agent_input"
    gt = data_root / f"task{task}" / "ground_truth"
    if not inp.is_dir():
        return []
    dec_file, rea_file = C.GT_FILES[task]
    out = []
    for case_dir in sorted(p for p in inp.iterdir() if p.is_dir()):
        g = gt / case_dir.name
        if not (g / dec_file).exists():
            continue
        payload = read_json(case_dir / "structured-prompt.json")
        clinical_path = case_dir / C.CLINICAL_DATA_FILE[task]
        clinical = read_json(clinical_path) if clinical_path.exists() else {}
        reasoning = read_json(g / rea_file) if (g / rea_file).exists() else None
        out.append(
            {
                "case_id": payload.get("case_id", case_dir.name),
                "group": payload.get("pid") or payload.get("case_id", case_dir.name),
                "task": task,
                "payload": payload,
                "clinical": clinical,
                "gt_decision": read_json(g / dec_file),
                "gt_reasoning": reasoning,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Política de herramientas
# ---------------------------------------------------------------------------


def tools_to_call(case: dict[str, Any], fh_policy: str, stats: Counter) -> list[str]:
    task = case["task"]
    valid = set(C.TOOL_FIELDS[task])
    if task == 3:
        tools = [t for t in T3_DEFAULT_TOOLS if t in valid]
    else:
        reveal = (case["gt_reasoning"] or {}).get("reveal_sequence") or []
        tools = []
        for section in reveal:
            tool = C.SECTION_TO_TOOL.get(section)
            if tool not in valid:
                stats[f"task{task}:seccion_invalida_descartada:{section}"] += 1
                continue
            if tool not in tools:
                tools.append(tool)
        weights = (case["gt_reasoning"] or {}).get("variable_weights") or {}
        if weights.get("fh", "not_used") != "not_used" and "get_family_history" not in tools:
            stats[f"task{task}:fh_ponderada_sin_family_history"] += 1
            if fh_policy == "add_tool":
                tools.append("get_family_history")
    return [t for t in C.CANONICAL_TOOL_ORDER if t in tools]


# ---------------------------------------------------------------------------
# Texto final de razonamiento (plantilla determinista, solo cita lo recuperado)
# ---------------------------------------------------------------------------


def _flat(value: Any, limit: int) -> str:
    if isinstance(value, str):
        text = value
    elif isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(", ".join(f"{v}" for v in item.values() if v not in (None, "")))
            else:
                parts.append(str(item))
        text = "; ".join(parts)
    elif value is None:
        text = "no data"
    else:
        text = json.dumps(value, ensure_ascii=False)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + " …"
    return text


def summarise_tool(task: int, tool: str, clinical: dict[str, Any], limit: int) -> str:
    fields = C.TOOL_FIELDS[task][tool]
    present = [f for f in fields if f in clinical and clinical[f] not in (None, "", [])]
    if not present:
        return "no data available"
    if tool == "get_psa_trend" and isinstance(clinical.get("psa_trend"), list) and clinical["psa_trend"]:
        series = clinical["psa_trend"]
        pts = [f"{p.get('val')} ({p.get('date')})" for p in series if isinstance(p, dict)]
        if len(pts) >= 2:
            return f"{len(pts)} values, from {pts[0]} to {pts[-1]}"
    return " ".join(_flat(clinical[f], limit) for f in present)


def _var_value(var: str, payload: dict[str, Any], clinical: dict[str, Any]) -> str:
    label, key = VARIABLE_LABELS.get(var, (var, var))
    if var == "fh":
        return f"{label}: {_flat(clinical.get('family_history'), 80)}"
    val = payload.get(key) if key else None
    if val in (None, "", []):
        return label
    return f"{label} {_flat(val, 60)}"


def decision_sentence(task: int, gt_decision: Any) -> str:
    if task == 1:
        return "Recommendation: biopsy recommended." if gt_decision == "yes" else (
            "Recommendation: no biopsy at this time."
        )
    if task == 2:
        return f"Recommended management: {str(gt_decision).replace('_', ' ')}."
    return f"Estimated time to biochemical recurrence or last follow-up: {float(gt_decision['months_to_recurrence']):.1f} months."


def key_factors(case: dict[str, Any], eligible: list[str]) -> list[str]:
    weights = (case["gt_reasoning"] or {}).get("variable_weights") or {} if case["task"] != 3 else {}
    rank = {"decisive": 0, "important": 1}
    chosen = sorted((v for v in eligible if weights.get(v) in rank), key=lambda v: rank[weights[v]])
    return [_var_value(v, case["payload"], case["clinical"]) for v in chosen]


def free_text(case: dict[str, Any]) -> str:
    r = case["gt_reasoning"]
    if case["task"] == 3:
        return r if isinstance(r, str) else ""
    return (r or {}).get("free_text") or ""


def build_transcript(case: dict[str, Any], tools: list[str], eligible: list[str], limit: int) -> str:
    task = case["task"]
    lines = ["Evidence retrieved:"]
    if tools:
        for t in tools:
            lines.append(f"- {SECTION_LABELS[t]}: {summarise_tool(task, t, case['clinical'], limit)}")
    else:
        lines.append("- No additional documents were needed beyond the structured record.")
    factors = key_factors(case, eligible)
    if factors:
        lines.append("Key factors: " + "; ".join(factors) + ".")
    lines.append(decision_sentence(task, case["gt_decision"]))
    if task != 3:
        conf = (case["gt_reasoning"] or {}).get("confidence")
        if conf:
            lines.append(f"Confidence: {conf}.")
    ft = free_text(case)
    if ft:
        lines.append(ft)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Objetivo del form-fill
# ---------------------------------------------------------------------------


def form_fill_target(case: dict[str, Any], called: set[str], stats: Counter) -> dict[str, Any]:
    task = case["task"]
    elig = C.eligible_variables(task, called)
    reasoning = free_text(case).strip()
    if len(reasoning) < 40:
        stats[f"task{task}:reasoning_ampliado_a_40"] += 1
        factors = key_factors(case, elig)
        extra = ("Main factors: " + "; ".join(factors) + ". ") if factors else ""
        reasoning = (extra + decision_sentence(task, case["gt_decision"]) + " " + reasoning).strip()
    if task == 3:
        obj = {
            "case_id": case["case_id"],
            "task": 3,
            "months_to_recurrence": round(float(case["gt_decision"]["months_to_recurrence"]), 1),
            "reasoning": reasoning,
        }
    else:
        gt_w = (case["gt_reasoning"] or {}).get("variable_weights") or {}
        dropped = [v for v, w in gt_w.items() if v not in elig and w != "not_used"]
        if dropped:
            stats[f"task{task}:pesos_no_elegibles_descartados"] += 1
        obj = {"case_id": case["case_id"], "task": task}
        if task == 1:
            obj["biopsy_decision"] = case["gt_decision"] == "yes"
        else:
            obj["action"] = case["gt_decision"]
        obj["confidence"] = (case["gt_reasoning"] or {}).get("confidence") or "clear"
        obj["variable_weights"] = {v: gt_w.get(v, "not_used") for v in elig}
        obj["reasoning"] = reasoning
    C.validate_form_fill(task, called, obj)  # lanza si no valida
    return obj


# ---------------------------------------------------------------------------
# Ensamblado
# ---------------------------------------------------------------------------


def react_messages(case: dict[str, Any], tools: list[str], transcript: str) -> list[dict[str, Any]]:
    task, cid = case["task"], case["case_id"]
    msgs: list[dict[str, Any]] = [
        {"role": "system", "content": C.SYSTEM_PROMPT},
        {"role": "user", "content": C.render_case_prompt(case["payload"])},
    ]
    for t in tools:
        call_id = str(uuid.uuid4())
        msgs.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"id": call_id, "type": "function",
                     "function": {"name": t, "arguments": json.dumps({"case_id": cid})}}
                ],
            }
        )
        text = C.tool_result_text(task, t, cid, case["clinical"])
        msgs.append({"role": "tool", "tool_call_id": call_id, "content": C.tool_message_content(text)})
    msgs.append({"role": "assistant", "content": transcript})
    return msgs


def build_case(case: dict[str, Any], args, stats: Counter, rng: random.Random) -> list[dict[str, Any]]:
    task = case["task"]
    tools = tools_to_call(case, args.fh_policy, stats)
    called = set(tools)
    elig = C.eligible_variables(task, called)
    transcript = build_transcript(case, tools, elig, args.evidence_chars)
    target = form_fill_target(case, called, stats)
    base = {"case_id": case["case_id"], "group": case["group"], "task": task, "fold": case.get("fold")}
    meta = {"tools_called": tools}
    if task == 3:
        meta["event"] = case["gt_decision"].get("event")

    records = [
        {**base, "kind": "react", "variant": 0, "tools": C.tool_schemas(task),
         "messages": react_messages(case, tools, transcript), "meta": meta},
    ]
    for k in range(1, args.permute_tools + 1):
        if len(tools) < 2:
            break
        order = tools[:]
        rng.shuffle(order)
        records.append({**base, "kind": "react", "variant": k, "tools": C.tool_schemas(task),
                        "messages": react_messages(case, order, transcript), "meta": meta})
    records.append(
        {**base, "kind": "form_fill", "variant": 0, "tools": None, "meta": meta,
         "messages": [
             {"role": "system", "content": C.FORM_FILL_SYSTEM_PROMPT},
             {"role": "user", "content": C.form_fill_user_prompt(case["case_id"], task, transcript, called)},
             {"role": "assistant", "content": json.dumps(target, indent=2, ensure_ascii=False)},
         ]}
    )
    return records


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--tasks", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--folds", type=Path, default=None, help="folds.json de make_folds.py")
    ap.add_argument("--fh-policy", choices=["add_tool", "drop_weight"], default="add_tool",
                    help="GT que pondera fh sin haber abierto family_history")
    ap.add_argument("--permute-tools", type=int, default=0,
                    help="variantes extra del ejemplo react con el orden de herramientas barajado")
    ap.add_argument("--evidence-chars", type=int, default=400,
                    help="caracteres máximos citados por documento en el razonamiento final")
    ap.add_argument("--seed", type=int, default=20260922)
    args = ap.parse_args()

    folds = read_json(args.folds) if args.folds else {}
    rng = random.Random(args.seed)
    stats: Counter = Counter()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with args.out.open("w") as fh:
        for task in args.tasks:
            cases = load_labelled_cases(args.data_root, task)
            stats[f"task{task}:casos_etiquetados"] = len(cases)
            for case in cases:
                case["fold"] = folds.get(str(task), {}).get(case["case_id"])
                dec = case["gt_decision"]
                stats[f"task{task}:clase:{dec.get('event') if task == 3 else dec}"] += 1
                try:
                    recs = build_case(case, args, stats, rng)
                except Exception as exc:  # noqa: BLE001 — se registra y se sigue
                    stats[f"task{task}:descartado:{type(exc).__name__}"] += 1
                    print(f"[descartado] task{task} {case['case_id']}: {exc}", file=sys.stderr)
                    continue
                for r in recs:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                    n += 1
    report = {"ejemplos": n, **dict(sorted(stats.items()))}
    args.out.with_suffix(".stats.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
