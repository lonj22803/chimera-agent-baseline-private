"""Informe de una corrida sobre los casos SIN etiqueta: la prueba honesta gratis.

Sobre los 104 casos sin ground truth no hay nota que calcular, pero sí hay
todo lo que se puede comprobar sin etiqueta: que ningún caso se perdió, que el
peldaño «precedente idéntico» no disparó nunca, qué reglas decidieron, qué
documentos se abrieron frente a lo que el plan decía, cuántas veces el
presidente disintió, cuántas veces se usó el respaldo, y si las distribuciones
(decisión, confianza, revelaciones) se parecen a las de la serie etiquetada.
Cualquier desviación grande es un cambio que hay que hacer antes de entregar.

    python -m ...analysis.report_unlabelled --run runs/all
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "data" / "task1"
SECTIONS = ["radiology_report", "psa_trend", "previous_notes", "laboratory_results", "family_history"]


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "0/0"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--md-out", default=None)
    args = ap.parse_args()
    root = Path(args.run)
    labelled = {p.name for p in (DATA / "ground_truth").iterdir() if p.is_dir()}
    rows = [json.loads(l) for l in (root / "summary.jsonl").read_text().splitlines() if l.strip()]
    unl = [r for r in rows if r["case_id"] not in labelled]
    lab = [r for r in rows if r["case_id"] in labelled]
    payload = {}
    for r in rows:
        f = DATA / "agent_input" / r["case_id"] / "structured-prompt.json"
        payload[r["case_id"]] = json.loads(f.read_text()) if f.exists() else {}
    gt = {}
    for cid in labelled:
        d = DATA / "ground_truth" / cid
        gt[cid] = {"decision": json.loads((d / "prostate-biopsy-decision.json").read_text()),
                   **json.loads((d / "prostate-biopsy-decision-reasoning.json").read_text())}

    out: list[str] = []
    P = out.append
    P(f"# Informe de la corrida `{root.name}` sobre los casos sin etiqueta\n")
    P(f"{len(rows)} casos en la corrida: {len(lab)} etiquetados, **{len(unl)} sin etiqueta**.\n")

    ok = [r for r in unl if r.get("ok")]
    P("## 1. Integridad\n")
    P(f"- casos entregados: {pct(len(ok), len(unl))}; fallos: {len(unl) - len(ok)}")
    fb = [r for r in unl if any("fallback" in w for w in r.get("warnings") or [])]
    P(f"- respaldo determinista del presidente: {pct(len(fb), len(unl))}" + (f" — {[r['case_id'][-6:] for r in fb]}" if fb else ""))
    sm = [r for r in unl if r.get("library_self_match")]
    P(f"- precedente idéntico (debe ser 0): {len(sm)}")
    secs = [r["seconds"] for r in ok if r.get("seconds")]
    if secs:
        P(f"- tiempo por caso: media {sum(secs) / len(secs):.1f} s, máximo {max(secs):.1f} s")
    P(f"- reaperturas del verificador: {sum(1 for r in ok if (r.get('passes') or 1) > 1)}")
    P("")

    P("## 2. Qué decidió y por qué regla\n")
    dec = collections.Counter(r.get("decision") for r in ok)
    gdec = collections.Counter(g["decision"] for g in gt.values())
    P(f"- decisión: yes {pct(dec['yes'], len(ok))}, no {pct(dec['no'], len(ok))} — en la serie etiquetada el urólogo: yes {pct(gdec['yes'], len(gt))}")
    by_bx = collections.defaultdict(collections.Counter)
    for r in ok:
        by_bx[str(payload[r["case_id"]].get("bx"))][r.get("decision")] += 1
    gby = collections.defaultdict(collections.Counter)
    for cid, g in gt.items():
        gby[str(payload.get(cid, {}).get("bx"))][g["decision"]] += 1
    P("- por cubo (sin etiqueta → serie etiquetada):")
    for b in ("None", "Negative", "Positive"):
        c, g = by_bx[b], gby[b]
        n, gn = sum(c.values()), sum(g.values())
        P(f"  - `{b}`: n={n}, yes {pct(c['yes'], n)} → urólogo yes {pct(g['yes'], gn)} sobre {gn}")
    rules = collections.Counter()
    for r in ok:
        rule = str(r.get("protocol_rule") or "")
        key = rule.split(",")[0].split("(")[0].strip() if not rule.startswith("documented") else "documented prior grade"
        rules[key] += 1
    P("- peldaño del protocolo que decidió:")
    for k, v in rules.most_common():
        P(f"  - {k}: {v}")
    grades = collections.Counter(str(r.get("grade")) for r in ok if str(payload[r["case_id"]].get("bx")) == "Positive")
    npos = sum(grades.values())
    P(f"- grado documentado leído en el cubo positivo: {pct(npos - grades['None'], npos)} — reparto {dict(grades)}")
    P("")

    P("## 3. La traza que se entrega\n")
    conf = collections.Counter(r.get("confidence") for r in ok)
    gconf = collections.Counter(g["confidence"] for g in gt.values())
    P(f"- confianza: " + ", ".join(f"{k} {pct(v, len(ok))}" for k, v in conf.most_common())
      + " — urólogo: " + ", ".join(f"{k} {pct(v, len(gt))}" for k, v in gconf.most_common()))
    rev = collections.Counter()
    for r in ok:
        for s in r.get("reveal_sequence") or []:
            rev[s] += 1
    grev = collections.Counter()
    for g in gt.values():
        for s in g["reveal_sequence"]:
            grev[s] += 1
    P("- secciones abiertas (frecuencia sin etiqueta → urólogo en la serie):")
    for s in SECTIONS:
        P(f"  - {s}: {pct(rev[s], len(ok))} → {pct(grev[s], len(gt))}")
    mism = [r for r in ok if set(r.get("reveal_sequence") or []) != set(r.get("planned") or [])]
    P(f"- casos en que lo abierto difiere del plan: {len(mism)}" + (f" — {[(r['case_id'][-6:], r.get('planned'), r.get('reveal_sequence')) for r in mism][:6]}" if mism else ""))
    empty = [r for r in ok if not (r.get("planned") or [])]
    P(f"- casos con plan vacío (el urólogo no abriría nada): {len(empty)}")
    wts = collections.defaultdict(collections.Counter)
    for r in ok:
        for k, v in (r.get("variable_weights") or {}).items():
            wts[k][v] += 1
    P("- pesos entregados (moda y frecuencia): " + ", ".join(f"{k}={c.most_common(1)[0][0]} {100 * c.most_common(1)[0][1] / len(ok):.0f}%" for k, c in wts.items()))
    P("")

    P("## 4. La sala\n")
    warn = collections.Counter()
    for r in ok:
        for w in r.get("warnings") or []:
            head = w.split("(")[0].split(":")[0:2]
            warn[":".join(h.strip() for h in head)[:48]] += 1
    for k, v in warn.most_common():
        P(f"- {k}: {v}")
    dis = [r for r in ok if (r.get("chair_form") or {}).get("decision") and (r["chair_form"]["decision"] != r.get("decision"))]
    P(f"- el presidente disintió del protocolo en {pct(len(dis), len(ok))}; se entregó el protocolo en todos")
    P(f"- preguntas abiertas por caso: media {sum(len(r.get('questions') or []) for r in ok) / max(len(ok), 1):.1f}")
    P(f"- EXPERT-IMAGE convocado: {sum(1 for r in ok if r.get('need_image'))}")
    P(f"- longitud del free_text: media {sum(r.get('free_text_chars', 0) for r in ok) / max(len(ok), 1):.0f} caracteres, "
      f"mínimo {min((r.get('free_text_chars', 0) for r in ok), default=0)}")
    text = "\n".join(out)
    print(text)
    if args.md_out:
        Path(args.md_out).write_text(text)


if __name__ == "__main__":
    main()
