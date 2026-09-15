"""El entrypoint del contenedor tiene que importar. Parece obvio; no lo era.

Al renombrar `delete_final_versions_task_V1_1` a `version_final_reto`, una regla
de sustitución destrozó un import de `inference_final.py`:

    from delete_final_versions_task_V2.verification import inference_v2
    ->  from version_final_reto.runtime_16gb.verification import inference_v2

El módulo iba separado por ` import `, así que la regla específica no casó y la
general lo convirtió en una ruta que no existe. Las 221 pruebas pasaron, porque
**ninguna importaba el entrypoint**. Lo cazó la compuerta sin montar código: los
tres casos salían con exit 1 y cero ficheros en 3–5 segundos. En Grand Challenge
habría sido un envío con todos los casos a cero.

Se importa en un subproceso: los envoltorios reasignan nombres de `inference` al
importarse, y hacerlo dentro de pytest contaminaría otras pruebas.
"""
from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
PAQUETE = RAIZ / "version_final_reto"


def test_el_entrypoint_importa_y_aplica_las_dos_sustituciones():
    codigo = (
        "import version_final_reto.inference_final;"
        "from version_final_reto.common import gc_entry;"
        "from version_final_reto.runtime_16gb import resources;"
        "from version_final_reto.task_3.agent import protocol as P;"
        "assert gc_entry.configure is resources.configure, 'perfil de 16 GB desconectado';"
        "assert getattr(P.Panel.horizon, '_v2_2', False), 'exportador de T3 sin aplicar';"
        "print('OK')")
    env = {**os.environ, "PYTHONPATH": f"{RAIZ}:{RAIZ / 'src'}"}
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True,
                       env=env, cwd=str(RAIZ))
    assert r.returncode == 0, r.stderr[-3000:]
    assert "OK" in r.stdout


def test_ningun_import_interno_apunta_a_un_modulo_inexistente():
    """Recorre todo el paquete: un import roto en cualquier sitio falla aquí."""
    sys.path[:0] = [str(RAIZ), str(RAIZ / "src")]
    rotos = []
    for p in sorted(PAQUETE.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        for n in ast.walk(ast.parse(p.read_text())):
            mods = []
            if isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                mods.append(n.module)
            elif isinstance(n, ast.Import):
                mods += [a.name for a in n.names]
            for m in mods:
                # Cualquier referencia a un árbol retirado también es un fallo.
                if m.startswith("delete_"):
                    rotos.append(f"{p.relative_to(RAIZ)}:{n.lineno} -> {m} (árbol retirado)")
                    continue
                if not m.startswith("version_final_reto"):
                    continue
                try:
                    ok = importlib.util.find_spec(m) is not None
                except (ImportError, ValueError):
                    ok = False
                if not ok:
                    rotos.append(f"{p.relative_to(RAIZ)}:{n.lineno} -> {m}")
    assert not rotos, "imports rotos:\n  " + "\n  ".join(rotos)
