"""Experimentos de Monte Carlo: subconjuntos aleatorios de 30 casos.

Por qué 30 y por qué al azar
----------------------------
Una corrida completa de los 91 casos cuesta cerca de una hora de GPU, y iterar
sobre ella invita a dos errores: mirar siempre los mismos casos (que acaban
memorizados en las decisiones de diseño) y confundir una diferencia de dos
casos con una mejora. Muestrear **30 casos al azar** con una semilla distinta
cada vez ataca las dos cosas: cada iteración ve una cohorte diferente, y
repetir el muestreo da una **distribución** del `ranking_score` en vez de un
número suelto.

El baseline se puntúa **sobre exactamente los mismos casos** de cada muestra,
así que la comparación es pareada: la variabilidad de qué pacientes tocaron se
cancela, y lo que queda es la diferencia entre los dos agentes.

    python .../analysis/montecarlo.py --runs runs/mc_s0 runs/mc_s1 ...
    python .../analysis/montecarlo.py --auto runs --pattern 'mc_s*'
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from delete_solution_one.solution_task_one_correction_claude.analysis import scoring  # noqa: E402

BASELINE = REPO / "delete_test" / "output_off"
PREV = REPO / "delete_solution_one" / "solution_task_one" / "runs" / "run2" / "output"


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
        row["seed"] = c.get("seed")
        row["sample"] = c.get("sample")
    for label, root in (("nuevo", run_dir / "output"), ("baseline", BASELINE), ("pizarra_v1", PREV)):
        if not Path(root).is_dir():
            continue
        agg = scoring.score(root, case_ids=ids)
        if not agg:
            continue
        s = scoring.summarise(agg)
        for k in ("ranking_score", "mean_case_score", "decision_gate", "f1_yes"):
            row[f"{label}_{k}"] = s[k]
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="*", default=None)
    ap.add_argument("--auto", default=None, help="directorio de corridas")
    ap.add_argument("--pattern", default="mc_s*")
    args = ap.parse_args()

    if args.auto:
        dirs = sorted(Path(args.auto).glob(args.pattern))
    else:
        dirs = [Path(r) for r in (args.runs or [])]
    rows = [r for r in (compare(d) for d in dirs) if r]
    if not rows:
        sys.exit("No hay corridas con salida.")

    import pandas as pd

    df = pd.DataFrame(rows)
    cols = [c for c in df.columns if c.endswith("ranking_score")]
    print(df[["run", "n", *[c for c in df.columns if c.endswith(("ranking_score", "decision_gate", "f1_yes"))]]]
          .round(4).to_string(index=False))

    if "nuevo_ranking_score" in df and "baseline_ranking_score" in df:
        d = df["nuevo_ranking_score"] - df["baseline_ranking_score"]
        print(f"\nnuevo − baseline sobre {len(d)} muestras de {int(df['n'].mean())} casos:")
        print(f"  delta medio {d.mean():+.4f}  (sd {d.std():.4f})   gana en {int((d > 0).sum())}/{len(d)}")
        if len(d) >= 5:
            from scipy import stats
            print(f"  Wilcoxon pareado p = {stats.wilcoxon(df['nuevo_ranking_score'], df['baseline_ranking_score']).pvalue:.4f}")
    if "pizarra_v1_ranking_score" in df:
        d2 = df["nuevo_ranking_score"] - df["pizarra_v1_ranking_score"]
        print(f"\nnuevo − pizarra v1: delta medio {d2.mean():+.4f}  gana en {int((d2 > 0).sum())}/{len(d2)}")
    _ = cols, np
    destino = Path(args.auto) if args.auto else dirs[0].parent
    df.to_csv(destino / "montecarlo.csv", index=False)
    print(f"\nescrito {destino / 'montecarlo.csv'}")


if __name__ == "__main__":
    main()
