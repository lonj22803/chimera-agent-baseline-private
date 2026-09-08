"""Ejecuta el cuaderno en sitio, con el kernel del proyecto.

    python delete_solution_one/solution_task_one_using_experts_final/analysis/_run_notebook.py

Se usa ``nbclient`` en vez de ``jupyter nbconvert`` porque el venv del proyecto
tiene el primero y no el segundo, y porque así se puede fijar el directorio de
trabajo (el cuaderno resuelve la raíz del repo subiendo desde ``cwd``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
NB = HERE / "analisis_final.ipynb"


def main() -> None:
    global NB
    if len(sys.argv) > 2 and sys.argv[1] == "--notebook":
        NB = HERE / sys.argv[2]
    nb = nbformat.read(NB, as_version=4)
    client = NotebookClient(nb, timeout=1800, kernel_name="python3", resources={"metadata": {"path": str(REPO)}},
                            allow_errors=True)
    client.execute()
    nbformat.write(nb, NB)
    errs = [(i, o) for i, c in enumerate(nb.cells) if c.cell_type == "code"
            for o in c.get("outputs", []) if o.get("output_type") == "error"]
    for i, o in errs:
        print(f"\n=== ERROR en la celda {i}: {o.get('ename')}: {o.get('evalue')}")
        print("\n".join(o.get("traceback", [])[-6:]))
    print(f"\n{len(nb.cells)} celdas · {len(errs)} con error · escrito {NB}")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
