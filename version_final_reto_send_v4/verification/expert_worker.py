"""Puntúa un caso con los expertos entrenados e imprime el resultado en JSON.

Un caso por proceso, que es como corre Grand Challenge y la única forma de
comparar: los imputadores de la tarea 1 llevan ``sample_posterior=True`` y su
``RandomState`` viaja dentro del pickle, así que puntuar dos casos en el mismo
proceso hace que el segundo sortee distinto. Cualquier comparación que reutilice
el intérprete mide ese arrastre, no el cambio que se quiere medir.

Uso::

    python3 expert_worker.py <task> <directorio_del_caso> <base|njobs1>
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

#: El brazo de control se elige **antes** de importar los paneles: así los
#: estimadores se quedan exactamente como los dejó el entrenamiento.
if len(sys.argv) > 3 and sys.argv[3] == "base":
    import os
    os.environ["CHIMERA_SERIAL_PREDICT"] = "0"

CLINICAL = {1: "prostate-biopsy-decision-clinical-data.json",
            2: "prostate-treatment-decision-clinical-data.json",
            3: "prostate-time-to-recurrence-or-last-follow-up-clinical-data.json"}


def main() -> None:
    task, case_dir, arm = int(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    files = {"prompt": json.loads((case_dir / "structured-prompt.json").read_text()),
             "clinical": json.loads((case_dir / CLINICAL[task]).read_text()),
             "features": json.loads((case_dir / "prostate-modality-level-neural-representations.json").read_text())}
    case_id = files["prompt"].get("case_id") or case_dir.name

    if task == 1:
        from version_final_reto.task_1.experts_1.panel import Panel
        panel = Panel()
        panel._load_live()
        start = time.perf_counter()
        # Un ``case_id`` que la caché no tiene: la rama viva es la del reto.
        panel.cases.pop(case_id, None)
        panel.ensure(case_id, files)
        payload = dict(panel.cases[case_id])
        # ``fusion_nolab`` va aplazada en la V1.1; para comparar contra la V1 hay
        # que materializarla, que es justo lo que hace el caso real cuando el
        # registrador no abre la analítica.
        payload["deployed"] = payload["deployed"].materialise() if hasattr(
            payload["deployed"], "materialise") else payload["deployed"]
    else:
        from version_final_reto.task_2.experts_2 import panel as trained
        live = trained._live_models()
        start = time.perf_counter()
        panel = trained.Panel()
        panel.cases.pop(case_id, None)
        panel._live = live
        panel.ensure(case_id, files)
        payload = panel.cases[case_id]
    print(json.dumps({"case_id": case_id, "task": task, "arm": arm,
                      "seconds": round(time.perf_counter() - start, 2),
                      "payload": payload}, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
