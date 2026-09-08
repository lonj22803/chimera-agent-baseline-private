"""¿Cuánto ganaría blindar al clasificador en sus tramos con historial?

La pregunta que contesta este script, sin volver a correr el modelo: **si en el
cubo indeterminado —donde el criterio de cohorte se abstiene— el presidente no
pudiera apartarse del clasificador cuando éste está en `firm` o `supports`,
¿cuánto cambiaría la nota?**

Por qué se pregunta. Medido out-of-fold sobre los 91 casos etiquetados, dentro
de ``bx = Positive``:

======================  ====  ==================
tramo                   n     acierto del clas.
======================  ====  ==================
``firm`` + ``supports`` 13    **0.923**
``discuss``             36    0.472
======================  ====  ==================

Es decir: en 13 de los 49 casos de ese cubo el clasificador casi no falla, y en
los otros 36 no distingue. La generación anterior ya midió el mismo mecanismo
(su iteración 3: el clasificador acertaba 0.900 en `supports` y el presidente lo
anulaba hasta 0.400) y lo atacó con un reto en el prompt. Este script mide si
ese reto basta o si hace falta una regla dura.

Cómo se mide. Se copia el árbol de salida, se parchea **sólo** la decisión de
los casos afectados y se puntúa con el evaluador oficial.

Una advertencia honesta sobre el método: al parchear la decisión, el
``free_text`` deja de corresponderse con ella. Con el juez de razonamiento
apagado —que es como se puntúa aquí— eso no entra en la nota, pero significa que
el número de este script es una **cota de lo que daría la regla**, no la nota de
una corrida real con la regla puesta. Si el contrafactual sale grande, hay que
confirmarlo corriendo de verdad.

    python .../analysis/counterfactual.py --run .../runs/full
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from delete_solution_one.solution_task_one_correction_claude.analysis import scoring  # noqa: E402

TIERS_WITH_STANDING = ("firm", "supports")


def load_board(run: Path, case_id: str) -> dict:
    return json.loads((run / "boards" / f"{case_id}.json").read_text())


def data_of(board: dict, speaker: str) -> dict:
    for item in reversed(board["interventions"]):
        if item["speaker"] == speaker:
            return item.get("data") or {}
    return {}


def truth(case_id: str) -> str | None:
    f = REPO / "data" / "task1" / "ground_truth" / case_id / "prostate-biopsy-decision.json"
    return json.loads(f.read_text()) if f.exists() else None


def main() -> None:
    ap = argparse.ArgumentParser(description="Contrafactual: blindar al clasificador")
    ap.add_argument("--run", required=True)
    ap.add_argument("--tiers", nargs="+", default=list(TIERS_WITH_STANDING))
    args = ap.parse_args()

    run = Path(args.run)
    shadow = run / f"counterfactual_{'_'.join(args.tiers)}"
    if shadow.exists():
        shutil.rmtree(shadow)
    shutil.copytree(run / "output", shadow / "output")

    rows = [json.loads(ln) for ln in (run / "summary.jsonl").read_text().splitlines() if ln.strip()]
    ok = [r for r in rows if r.get("ok")]

    flipped, kept, gained, lost = [], 0, 0, 0
    for r in ok:
        cid = r["case_id"]
        board = load_board(run, cid)
        prior = data_of(board, "EXPERT-CLASSIFIER")
        cohort = data_of(board, "EXPERT-COHORT")

        if cohort.get("verdict") is not None:
            continue                                    # la cohorte se pronuncia: no aplica
        if prior.get("veredicto_operativo") not in args.tiers:
            continue                                    # el clasificador no tiene standing
        want = prior.get("prediccion")
        if want not in ("yes", "no") or want == r["decision"]:
            kept += 1
            continue

        y = truth(cid)
        if y is not None:
            gained += int(want == y and r["decision"] != y)
            lost += int(r["decision"] == y and want != y)
        flipped.append((cid, r["decision"], want, y, prior["veredicto_operativo"]))
        (shadow / "output" / "task1" / cid / "prostate-biopsy-decision.json").write_text(
            json.dumps(want, indent=2))

    print(f"=== contrafactual sobre {run.name}: tramos {', '.join(args.tiers)} ===")
    print(f"casos donde la cohorte se abstiene y el clasificador tiene standing "
          f"y el presidente lo respetó: {kept}")
    print(f"casos volteados: {len(flipped)}  (recupera {gained}, pierde {lost})\n")
    for cid, was, now, y, tier in flipped:
        mark = "GANA " if now == y else ("PIERDE" if was == y else "igual")
        print(f"  {cid[-8:]}  {tier:<9} {was} -> {now}   verdad={y}   {mark}")

    ids = {r["case_id"] for r in ok}
    print()
    for label, root in (("tal cual", run / "output"), ("con la regla", shadow / "output")):
        agg = scoring.score(root, case_ids=ids)
        s = scoring.summarise(agg)
        print(f"  {label:<14} ranking={s['ranking_score']}  case={s['mean_case_score']}  "
              f"puerta={s['decision_gate']}  F1(yes)={s['f1_yes']}")
    print(f"\n(salida parcheada en {shadow})")


if __name__ == "__main__":
    main()
