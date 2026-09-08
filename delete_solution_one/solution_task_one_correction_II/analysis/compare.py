"""Comparación pareada de esta junta contra el baseline y contra la pizarra v2.

Los tres brazos se puntúan **sobre exactamente los mismos casos** de cada
muestra, con el evaluador oficial y el juez de razonamiento apagado, de modo que
la variabilidad de qué pacientes tocaron se cancela y lo que queda es la
diferencia entre agentes. Se reutiliza la envoltura del evaluador que ya existe
en el paquete anterior: aquí no se reimplementa ninguna métrica.

    python .../analysis/compare.py --auto .../runs --pattern 'mc_s*'
    python .../analysis/compare.py --runs .../runs/full
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from delete_solution_one.solution_task_one_correction_claude.analysis import scoring  # noqa: E402

#: Los dos brazos de referencia: el ReAct del baseline a la misma temperatura, y
#: la pizarra con moderador (v2), que es lo que hay que batir.
ARMS = {
    "baseline": REPO / "delete_test" / "output_off",
    "pizarra_v2": REPO / "delete_solution_one" / "solution_task_one_correction_claude"
                  / "runs" / "full" / "output",
}

KEYS = ("ranking_score", "mean_case_score", "decision_gate", "f1_yes",
        "variable_weight_score", "confidence_score", "important_decisive_factor_score",
        "section_grounding_score", "tool_score")


def case_ids_of(run_dir: Path) -> set[str]:
    out = run_dir / "output" / "task1"
    return {p.name for p in out.iterdir() if p.is_dir()} if out.is_dir() else set()


def compare(run_dir: Path) -> dict | None:
    ids = case_ids_of(run_dir)
    if not ids:
        return None
    row: dict = {"run": run_dir.name, "n": len(ids)}
    cfg = run_dir / "run_config.json"
    if cfg.exists():
        c = json.loads(cfg.read_text())
        row |= {"seed": c.get("seed"), "sample": c.get("sample"),
                "temperature": c.get("temperature")}
    for label, root in (("junta", run_dir / "output"), *ARMS.items()):
        if not Path(root).is_dir():
            continue
        agg = scoring.score(root, case_ids=ids)
        if not agg:
            continue
        s = scoring.summarise(agg)
        for k in KEYS:
            row[f"{label}_{k}"] = s.get(k)
    return row


def _delta(df, a: str, b: str) -> None:
    ka, kb = f"{a}_ranking_score", f"{b}_ranking_score"
    if ka not in df or kb not in df or df[kb].isna().all():
        return
    d = (df[ka] - df[kb]).dropna()
    if d.empty:
        return
    print(f"\n{a} − {b} sobre {len(d)} muestra(s) de ~{int(df['n'].mean())} casos:")
    print(f"  delta medio {d.mean():+.4f} (sd {d.std():.4f})   gana en {int((d > 0).sum())}/{len(d)}")
    if len(d) >= 5:
        from scipy import stats
        print(f"  Wilcoxon pareado p = {stats.wilcoxon(df[ka], df[kb]).pvalue:.4f}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Comparación pareada de la junta")
    ap.add_argument("--runs", nargs="*", default=None)
    ap.add_argument("--auto", default=None, help="directorio de corridas")
    ap.add_argument("--pattern", default="mc_s*")
    args = ap.parse_args()

    dirs = sorted(Path(args.auto).glob(args.pattern)) if args.auto \
        else [Path(r) for r in (args.runs or [])]
    rows = [r for r in (compare(d) for d in dirs) if r]
    if not rows:
        sys.exit("No hay corridas con salida en task1/.")

    import pandas as pd

    df = pd.DataFrame(rows)
    show = ["run", "n"] + [c for c in df.columns
                           if c.endswith(("ranking_score", "decision_gate", "f1_yes", "tool_score"))]
    print(df[show].round(4).to_string(index=False))
    _delta(df, "junta", "baseline")
    _delta(df, "junta", "pizarra_v2")

    destino = Path(args.auto) if args.auto else dirs[0].parent
    df.to_csv(destino / "compare.csv", index=False)
    print(f"\nescrito {destino / 'compare.csv'}")


if __name__ == "__main__":
    main()
