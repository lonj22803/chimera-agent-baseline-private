"""Grupos de registros relacionados (PLAN §10.1). Sin esto no se entrena nada.

El PLAN lo pone antes que cualquier ajuste: «Antes de entrenar, crear un
``group_id`` para registros relacionados a partir de procedencia disponible y
duplicaciones verificadas». La razón es que T1, T2 y T3 no comparten los mismos
identificadores textuales, pero **sí comparten pacientes**: la auditoría de V2
encontró 170 grupos de vectores MRI idénticos presentes en más de una tarea.
Partir por ID de directorio asumiría independencia donde no la hay.

**Criterio de agrupación, único y declarado:** dos casos van al mismo grupo si
comparten un vector de modalidad **exactamente igual** (byte a byte tras
serializar de forma canónica). No se agrupa por parecido clínico: el PLAN lo
prohíbe —«La coincidencia de un perfil clínico sencillo no basta para declarar
el mismo paciente»—. La igualdad exacta de un vector de 1024 flotantes no es
casualidad, pero tampoco es prueba de identidad de paciente: es una pista
fuerte, y lo que se hace con ella es **mantener esos registros juntos** al
partir, que es conservador en la dirección correcta.

No se publican identificadores de paciente ni se usan los grupos para predecir.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MODALIDADES = ("MRI image", "Biopsy slide", "Prostatectomy slide")


class UnionFind:
    def __init__(self):
        self.padre: dict[str, str] = {}

    def añadir(self, x: str) -> None:
        self.padre.setdefault(x, x)

    def raiz(self, x: str) -> str:
        while self.padre[x] != x:
            self.padre[x] = self.padre[self.padre[x]]
            x = self.padre[x]
        return x

    def unir(self, a: str, b: str) -> None:
        self.añadir(a); self.añadir(b)
        ra, rb = self.raiz(a), self.raiz(b)
        if ra != rb:
            self.padre[rb] = ra


def _huella(vector) -> str:
    return hashlib.sha256(json.dumps(vector, separators=(",", ":")).encode()).hexdigest()


def casos(raiz: Path = RAIZ) -> list[tuple[int, str, Path]]:
    """(tarea, nombre de caso, directorio) de las tres tareas."""
    salida = []
    for tarea in (1, 2, 3):
        base = raiz / f"data/task{tarea}/agent_input"
        for d in sorted(p for p in base.iterdir() if p.is_dir()):
            salida.append((tarea, d.name, d))
    return salida


def construir(raiz: Path = RAIZ) -> dict:
    uf = UnionFind()
    por_huella: dict[str, list[str]] = defaultdict(list)
    modalidades_por_caso: dict[str, list[str]] = {}

    todos = casos(raiz)
    for tarea, nombre, d in todos:
        clave = f"t{tarea}:{nombre}"
        uf.añadir(clave)
        presentes = []
        emb = d / "prostate-modality-level-neural-representations.json"
        if not emb.exists():
            modalidades_por_caso[clave] = presentes
            continue
        datos = json.loads(emb.read_text())
        for modalidad in MODALIDADES:
            vectores = datos.get(modalidad)
            if not vectores:
                continue
            presentes.append(modalidad)
            for v in vectores:
                por_huella[f"{modalidad}|{_huella(v)}"].append(clave)
        modalidades_por_caso[clave] = presentes

    colisiones = 0
    for huella, claves in por_huella.items():
        if len(claves) > 1:
            colisiones += 1
            for otro in claves[1:]:
                uf.unir(claves[0], otro)

    grupos: dict[str, list[str]] = defaultdict(list)
    for tarea, nombre, _ in todos:
        clave = f"t{tarea}:{nombre}"
        grupos[uf.raiz(clave)].append(clave)

    # Identificador estable y anónimo: el hash del conjunto ordenado de claves.
    asignacion, tamaños, cruzados = {}, defaultdict(int), 0
    for miembros in grupos.values():
        gid = "g" + hashlib.sha256("|".join(sorted(miembros)).encode()).hexdigest()[:12]
        tareas = {m.split(":")[0] for m in miembros}
        if len(tareas) > 1:
            cruzados += 1
        tamaños[len(miembros)] += 1
        for m in miembros:
            asignacion[m] = gid

    return {
        "criterio": "igualdad exacta de un vector de modalidad, union-find sobre las tres tareas",
        "modalidades_consideradas": list(MODALIDADES),
        "casos_totales": len(todos),
        "casos_por_tarea": {f"t{t}": sum(1 for x, _, _ in todos if x == t) for t in (1, 2, 3)},
        "grupos": len(grupos),
        "grupos_multitarea": cruzados,
        "huellas_compartidas": colisiones,
        "distribucion_tamaños": {str(k): v for k, v in sorted(tamaños.items())},
        "asignacion": asignacion,
        "modalidades_por_caso": modalidades_por_caso,
    }


def cargar(raiz: Path = RAIZ) -> dict[str, str]:
    """Asignación caso -> grupo, desde el manifiesto congelado."""
    m = Path(__file__).resolve().parent / "manifests" / "grupos.json"
    if m.exists():
        return json.loads(m.read_text())["asignacion"]
    return construir(raiz)["asignacion"]


if __name__ == "__main__":
    r = construir()
    destino = Path(__file__).resolve().parent / "manifests" / "grupos.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(r, indent=2, ensure_ascii=False))
    resumen = {k: v for k, v in r.items() if k not in ("asignacion", "modalidades_por_caso")}
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    print(f"\nescrito {destino.relative_to(RAIZ)}")
