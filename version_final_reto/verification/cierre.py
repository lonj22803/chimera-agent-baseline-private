"""Cierre de la cobertura: permisos, pizarras, T3 rehecho y comparativa.

Se ejecuta cuando `cobertura_v2_2.py` ha terminado las tres tareas.

Por qué hace falta cada paso:

1. **Permisos.** El contenedor escribe `result_v2` como su propio usuario, así
   que desde fuera no se puede ni crear un directorio dentro. Se arregla con un
   `chmod` desde la misma imagen, que es como lo hace `do_test_run.sh`.
2. **Pizarras.** T1 y T2 las dejan en `boards/`, repartidas entre `labeled/` y
   `unlabeled/`. T3 las deja como `acta.json`/`acta.md` junto a la salida de
   cada caso. Las tres existen y son la misma cosa —el acta de la junta—, pero
   buscarlas en un único sitio daba cero para T3 y parecía que no había.
3. **T3 otra vez.** El acta de la primera pasada declaraba `a: 93.67`, heredado
   de la rama original, cuando el mapa usó `a: 90`. Los meses no cambian; lo que
   cambia es que el acta deja de mentir sobre sus propios parámetros.
4. **Comparativa** contra H0, B0 y los experimentos.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "result_v2"
IMAGEN = "chimera_agent_baseline_v2"


def permisos() -> None:
    subprocess.run(["docker", "run", "--rm", "--platform=linux/amd64", "--quiet",
                    "-v", f"{SALIDA}:/output", "--entrypoint", "/bin/sh", IMAGEN,
                    "-c", "chmod -R o+rwX /output || true"], check=False,
                   capture_output=True, text=True)


def rehacer_t3() -> dict:
    destino = SALIDA / "task_3"
    viejo = SALIDA / "task_3_primera_pasada"
    if destino.is_dir() and not viejo.exists():
        destino.rename(viejo)
    sys.path.insert(0, str(RAIZ))
    from version_final_reto.investigacion.verification import cobertura_v2_2 as cob
    cob.TAREAS = {3: cob.TAREAS[3]}
    cob.main()
    return {"primera_pasada_conservada_en": str(viejo.relative_to(RAIZ))}


def recontar() -> dict:
    """El resumen de la cobertura quedó con ceros: contaba en el sitio de T3.

    T1 y T2 reparten su salida en `labeled/` y `unlabeled/`; el contador miraba
    en `task_N/output`, que sólo existe para T3. Los ficheros siempre estuvieron;
    lo que estaba mal era el recuento, y un resumen que dice 0 salidas cuando hay
    195 es peor que no tener resumen.
    """
    cuenta = {}
    for tarea in (1, 2, 3):
        base = SALIDA / f"task_{tarea}"
        sitios = ([base / s for s in ("labeled", "unlabeled")] if tarea in (1, 2) else [base])
        salidas = pizarras = 0
        for d in sitios:
            o = d / "output" / f"task{tarea}"
            salidas += len([x for x in o.iterdir() if x.is_dir()]) if o.is_dir() else 0
            b = d / "boards"
            pizarras += len(list(b.glob("*.json"))) if b.is_dir() else 0
            if tarea == 3 and o.is_dir():
                pizarras += len(list(o.glob("*/acta.json")))
        cuenta[f"task{tarea}"] = {"salidas": salidas, "pizarras": pizarras}
    f = SALIDA / "cobertura_resumen.json"
    if f.exists():
        d = json.loads(f.read_text())
        d["recuento_corregido"] = cuenta
        d["nota_recuento"] = ("El contador original miraba en task_N/output, que sólo existe "
                              "para T3; T1 y T2 reparten en labeled/ y unlabeled/.")
        f.write_text(json.dumps(d, indent=2, ensure_ascii=False))
    return cuenta


def main() -> None:
    print("1. permisos"); permisos()
    print("2. T3 otra vez, con el acta corregida"); info = rehacer_t3()
    print("   ", info)
    permisos()
    sys.path.insert(0, str(RAIZ))
    from version_final_reto.investigacion.verification.cobertura_v2_2 import normalizar_pizarras
    print("3. pizarras:", normalizar_pizarras())
    print("4. recuento:", recontar())
    print("5. comparativa")
    from version_final_reto.investigacion.evaluation import comparativa
    comparativa.main()


if __name__ == "__main__":
    main()
