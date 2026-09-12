"""Particiones anidadas por grupo (PLAN §10.1). Se congelan antes de medir nada.

Configuración del PLAN: **5 pliegues exteriores y 3 interiores, semillas
predeclaradas 111, 223 y 337**, «adaptando número de pliegues si la agrupación
impide una evaluación válida».

Lo que hace distinto a esto de un `KFold` cualquiera:

- **Parte por grupo, no por caso.** Con 423 casos en 199 grupos (y 170 grupos
  presentes en más de una tarea), partir por identificador de directorio pondría
  al mismo paciente a los dos lados. Ver `groups.py`.
- **Estratifica** por la etiqueta de la tarea cuando el tamaño lo permite: T3 por
  evento, T1 por decisión, T2 por clase.
- **Registra los pliegues sin `watchful_waiting`** en vez de esconderlos. Esa
  clase tiene **dos** etiquetas en todo el corpus: es aritméticamente imposible
  que aparezca en los cinco pliegues. El PLAN lo pide explícito: «registrar los
  pliegues sin esa clase […] No eliminar la clase de la métrica ni presentar
  cinco folds como cinco observaciones independientes de ella».
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold, GroupKFold

RAIZ = Path(__file__).resolve().parents[3]
AQUI = Path(__file__).resolve().parent
SEMILLAS = (111, 223, 337)
PLIEGUES_EXTERIORES = 5
PLIEGUES_INTERIORES = 3

NOMBRE_DECISION = {
    1: "prostate-biopsy-decision.json",
    2: "prostate-treatment-decision.json",
    3: "prostate-time-to-recurrence-or-last-follow-up.json",
}


def etiquetas(tarea: int, raiz: Path = RAIZ) -> dict[str, object]:
    """Caso -> etiqueta cruda. Sólo los casos que tienen ground truth."""
    base = raiz / f"data/task{tarea}/ground_truth"
    salida = {}
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        f = d / NOMBRE_DECISION[tarea]
        if f.exists():
            salida[d.name] = json.loads(f.read_text())
    return salida


def _estrato(tarea: int, valor) -> str:
    if tarea == 3:
        return str(valor.get("event"))
    return str(valor)


def construir(tarea: int, raiz: Path = RAIZ) -> dict:
    from . import groups as g

    asignacion = g.cargar(raiz)
    etq = etiquetas(tarea, raiz)
    casos = sorted(etq)
    grupo = [asignacion[f"t{tarea}:{c}"] for c in casos]
    estrato = [_estrato(tarea, etq[c]) for c in casos]
    conteo = Counter(estrato)

    # Con una clase de soporte 2 no se puede estratificar en 5 pliegues sin que
    # sklearn avise; se estratifica igual y se registra dónde falta la clase.
    minimo = min(conteo.values())
    exteriores = PLIEGUES_EXTERIORES
    estratificado = minimo >= 2

    resultado = {
        "tarea": tarea,
        "casos": len(casos),
        "grupos_distintos": len(set(grupo)),
        "distribucion": dict(sorted(conteo.items())),
        "clase_minoritaria": min(conteo, key=conteo.get),
        "soporte_minimo": minimo,
        "estratificado": estratificado,
        "pliegues_exteriores": exteriores,
        "pliegues_interiores": PLIEGUES_INTERIORES,
        "semillas": list(SEMILLAS),
        "reparticiones": {},
    }

    for semilla in SEMILLAS:
        if estratificado:
            cv = StratifiedGroupKFold(n_splits=exteriores, shuffle=True, random_state=semilla)
            reparto = list(cv.split(casos, estrato, grupo))
        else:
            cv = GroupKFold(n_splits=exteriores)
            reparto = list(cv.split(casos, estrato, grupo))

        pliegues = []
        for k, (tr, te) in enumerate(reparto):
            clases_test = Counter(estrato[i] for i in te)
            faltan = sorted(set(conteo) - set(clases_test))
            # Interiores sobre el train del exterior, otra vez por grupo.
            gr_tr = [grupo[i] for i in tr]
            es_tr = [estrato[i] for i in tr]
            n_int = min(PLIEGUES_INTERIORES, len(set(gr_tr)))
            if min(Counter(es_tr).values()) >= 2 and n_int >= 2:
                cvi = StratifiedGroupKFold(n_splits=n_int, shuffle=True, random_state=semilla)
                interiores = [[ [casos[tr[i]] for i in a], [casos[tr[i]] for i in b] ]
                              for a, b in cvi.split(list(tr), es_tr, gr_tr)]
            else:
                cvi = GroupKFold(n_splits=n_int)
                interiores = [[ [casos[tr[i]] for i in a], [casos[tr[i]] for i in b] ]
                              for a, b in cvi.split(list(tr), es_tr, gr_tr)]

            pliegues.append({
                "pliegue": k,
                "train": [casos[i] for i in tr],
                "test": [casos[i] for i in te],
                "grupos_train": sorted({grupo[i] for i in tr}),
                "grupos_test": sorted({grupo[i] for i in te}),
                "distribucion_test": dict(sorted(clases_test.items())),
                "clases_ausentes_en_test": faltan,
                "interiores": interiores,
            })
        resultado["reparticiones"][str(semilla)] = pliegues

    # Comprobación dura: ningún grupo puede estar a los dos lados.
    for semilla, pliegues in resultado["reparticiones"].items():
        for p in pliegues:
            solape = set(p["grupos_train"]) & set(p["grupos_test"])
            assert not solape, f"fuga de grupo en tarea {tarea} semilla {semilla}: {solape}"
    return resultado


def cargar(tarea: int) -> dict:
    f = AQUI / "manifests" / f"particiones_task{tarea}.json"
    return json.loads(f.read_text())


if __name__ == "__main__":
    destino = AQUI / "manifests"
    destino.mkdir(parents=True, exist_ok=True)
    for tarea in (1, 2, 3):
        r = construir(tarea)
        (destino / f"particiones_task{tarea}.json").write_text(
            json.dumps(r, indent=2, ensure_ascii=False))
        print(f"tarea {tarea}: {r['casos']} casos en {r['grupos_distintos']} grupos "
              f"| {r['distribucion']} | estratificado={r['estratificado']}")
        for semilla, pliegues in r["reparticiones"].items():
            vacios = [p["pliegue"] for p in pliegues if p["clases_ausentes_en_test"]]
            if vacios:
                detalle = {p["pliegue"]: p["clases_ausentes_en_test"] for p in pliegues
                           if p["clases_ausentes_en_test"]}
                print(f"    semilla {semilla}: pliegues sin alguna clase en test -> {detalle}")
