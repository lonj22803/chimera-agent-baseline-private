"""Diagnóstico de una corrida: qué se rompió, dónde y en qué cubo clínico.

No sustituye a [`compare.py`](compare.py), que da la nota oficial. Esto responde
a la otra pregunta, la que se hace después de una corrida: **por qué** salió ese
número. Cinco vistas, todas sobre `summary.jsonl` y las actas persistidas:

1. fallos y avisos, agrupados por tipo;
2. comportamiento del verificador: cuántos pases, cuántas veces escribió su
   línea mecánica, cuántas reabrió;
3. economía de revelaciones: qué documentos se abrieron y qué precisión da eso
   contra lo que abrió el urólogo;
4. exactitud por cubo de biopsia previa, que es donde se decide esta tarea;
5. las intervenciones que quedaron vacías o degeneradas.

    python .../analysis/diagnose.py --run .../runs/pilot
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

DATA = REPO / "data" / "task1"


def rows_of(run: Path) -> list[dict]:
    f = run / "summary.jsonl"
    if not f.exists():
        sys.exit(f"No hay {f}")
    return [json.loads(ln) for ln in f.read_text().splitlines() if ln.strip()]


def truth(case_id: str) -> tuple[str | None, list[str]]:
    """(decisión del urólogo, secciones que reveló)."""
    d = DATA / "ground_truth" / case_id
    dec = d / "prostate-biopsy-decision.json"
    rea = d / "prostate-biopsy-decision-reasoning.json"
    y = json.loads(dec.read_text()) if dec.exists() else None
    seq: list[str] = []
    if rea.exists():
        r = json.loads(rea.read_text())
        for item in r.get("reveal_sequence") or []:
            key = item.get("key") if isinstance(item, dict) else item
            if key:
                seq.append(key)
    return y, seq


def panel(case_id: str) -> dict:
    f = DATA / "agent_input" / case_id / "structured-prompt.json"
    return json.loads(f.read_text()) if f.exists() else {}


def main() -> None:
    ap = argparse.ArgumentParser(description="Diagnóstico de una corrida de la junta")
    ap.add_argument("--run", required=True)
    ap.add_argument("--show", type=int, default=0, help="imprime N actas completas")
    args = ap.parse_args()

    run = Path(args.run)
    rows = rows_of(run)
    ok = [r for r in rows if r.get("ok")]
    bad = [r for r in rows if not r.get("ok")]

    print(f"=== {run.name}: {len(rows)} casos, {len(ok)} ok, {len(bad)} fallidos ===\n")
    for r in bad:
        print(f"  FALLO {r['case_id']}: {r.get('error')}")
    if bad:
        print()

    # -- 1. avisos --------------------------------------------------------
    warn = Counter()
    for r in ok:
        for w in r.get("warnings") or []:
            warn[w.split("(")[0].split(":")[0].strip() + ": " + w.split(":", 1)[-1].split("(")[0].strip()[:60]] += 1
    if warn:
        print("--- avisos ---")
        for w, n in warn.most_common():
            print(f"  {n:3d}  {w}")
        print()

    # -- 2. el verificador ------------------------------------------------
    print("--- verificador ---")
    print(f"  pases: {dict(Counter(r.get('passes') for r in ok))}")
    print(f"  escribió su línea VERDICT: {sum(1 for r in ok if r.get('verifier_parsed'))}/{len(ok)}")
    print(f"  cerró en 'ready': {sum(1 for r in ok if r.get('verifier_ready'))}/{len(ok)}")
    agree = [r for r in ok if r.get("verifier_suggest") in ("biopsy", "defer")]
    same = sum(1 for r in agree
               if (r["verifier_suggest"] == "biopsy") == (r["decision"] == "yes"))
    print(f"  el presidente siguió su sugerencia: {same}/{len(agree)}")
    print(f"  convocó a EXPERT-IMAGE: {sum(1 for r in ok if r.get('need_image'))}/{len(ok)}")
    print()

    # -- 3. revelaciones --------------------------------------------------
    print("--- revelaciones ---")
    opened = Counter()
    precisions = []
    for r in ok:
        seq = r.get("reveal_sequence") or []
        opened.update(seq)
        _, gt_seq = truth(r["case_id"])
        if seq:
            precisions.append(len(set(seq) & set(gt_seq)) / len(set(seq)))
    for s, n in opened.most_common():
        print(f"  {n:3d}/{len(ok)}  {s}")
    print(f"  nº medio de documentos: {sum(len(r.get('reveal_sequence') or []) for r in ok) / max(len(ok), 1):.2f}")
    if precisions:
        print(f"  tool_score (precisión) medio: {sum(precisions) / len(precisions):.4f}")
    print()

    # -- 4. exactitud por cubo -------------------------------------------
    print("--- decisión por cubo de biopsia previa ---")
    buckets: dict[str, list[tuple[str, str]]] = {}
    for r in ok:
        y, _ = truth(r["case_id"])
        if y is None:
            continue
        bx = str(panel(r["case_id"]).get("bx") or "None")
        buckets.setdefault(bx, []).append((r["decision"], y))
    total_hit = total_n = 0
    for bx, pairs in sorted(buckets.items()):
        hit = sum(1 for p, y in pairs if p == y)
        total_hit += hit
        total_n += len(pairs)
        says_yes = sum(1 for p, _ in pairs if p == "yes")
        print(f"  bx={bx:<10} {hit}/{len(pairs)} = {hit / len(pairs):.3f}   "
              f"(el agente dijo 'yes' en {says_yes}/{len(pairs)})")
    if total_n:
        print(f"  TOTAL       {total_hit}/{total_n} = {total_hit / total_n:.3f}")
    print()

    # -- 5. confianza y pesos --------------------------------------------
    print("--- formulario ---")
    print(f"  confianza: {dict(Counter(r.get('confidence') for r in ok))}")
    print(f"  decisión:  {dict(Counter(r.get('decision') for r in ok))}")
    dec = Counter()
    for r in ok:
        for k, v in (r.get("variable_weights") or {}).items():
            if v in ("important", "decisive"):
                dec[f"{k}={v}"] += 1
    print("  variables por encima de 'noted':")
    for k, n in dec.most_common(12):
        print(f"    {n:3d}  {k}")
    print(f"  prosa: {sum(r.get('free_text_chars', 0) for r in ok) / max(len(ok), 1):.0f} caracteres de media")
    print(f"  segundos/caso: {sum(r.get('seconds', 0) for r in ok) / max(len(ok), 1):.1f}")
    print(f"  intervenciones/caso: {sum(r.get('n_interventions', 0) for r in ok) / max(len(ok), 1):.1f}")

    # -- 6. actas degeneradas --------------------------------------------
    boards = run / "boards"
    if boards.is_dir():
        print("\n--- intervenciones vacías o degeneradas ---")
        short = Counter()
        for f in sorted(boards.glob("*.json")):
            b = json.loads(f.read_text())
            for it in b["interventions"]:
                body = it["body"]
                if len(body) < 120 or "…" in body[:20]:
                    short[it["speaker"]] += 1
        for s, n in short.most_common():
            print(f"  {n:3d}  {s}")
        if not short:
            print("  ninguna")

    for f in sorted(boards.glob("*.md"))[:args.show]:
        print("\n" + "=" * 78 + f"\n{f.name}\n" + "=" * 78)
        print(f.read_text())


if __name__ == "__main__":
    main()
