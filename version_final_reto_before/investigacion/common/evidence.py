"""Registro de hechos verificables (PLAN §4.1).

La unidad de trabajo de V2 deja de ser una opinión y pasa a ser un **hecho con
fuente**. Cada hecho dice qué concepto es, qué valor tiene, en qué estado está,
de dónde sale, qué texto exacto lo respalda y a qué momento se refiere.

Lo que este contrato impide, y el parser de V1 no impedía:

- **Ausencia no es negativa.** `value=None, status="unknown"` y `value=False,
  status="observed"` son cosas distintas. V1 las colapsaba en un 0.
- **Una negación documentada es un hecho**, no la falta de uno: «No histological
  progression» es `progresion=False, status="observed"`, con su cita.
- **Un conflicto se declara**, no se resuelve en silencio quedándose con la
  última coincidencia del texto.
- **El grado humano y la predicción de patología digital no se mezclan**: van en
  hechos distintos con `source` distinto.

Los offsets apuntan al texto fuente y su final es exclusivo. Una cita literal es
**necesaria pero no suficiente**: que el texto exista no valida la
interpretación, sólo permite comprobarla.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable

ESTADOS = ("observed", "unknown", "conflicting", "not_applicable")


@dataclass(frozen=True)
class Hecho:
    concept: str
    value: Any
    status: str
    source: str
    method: str
    pointer: tuple[int, int] | None = None
    quote: str | None = None
    timepoint: str | None = None
    subject: str = "patient"
    evidence_id: str | None = None
    nota: str | None = None

    def __post_init__(self):
        if self.status not in ESTADOS:
            raise ValueError(f"estado no permitido: {self.status}")
        if self.status == "observed" and self.value is None:
            raise ValueError(f"{self.concept}: 'observed' exige un valor; usa 'unknown'")
        if self.status == "unknown" and self.value is not None:
            raise ValueError(f"{self.concept}: 'unknown' no puede traer valor")
        if self.pointer is not None:
            i, j = self.pointer
            if not (0 <= i < j):
                raise ValueError(f"{self.concept}: offsets inválidos {self.pointer}")

    def respaldado_por(self, texto: str) -> bool:
        """La cita tiene que existir **en esa posición**, no en cualquier sitio.

        Buscar la cita con `in texto` dejaría pasar un puntero equivocado hacia
        otro paciente o momento, que es justo lo que hay que poder descartar.
        """
        if self.pointer is None or self.quote is None:
            return self.status in ("unknown", "not_applicable")
        i, j = self.pointer
        return texto[i:j] == self.quote


class RegistroDeHechos:
    """Los hechos de un caso, con detección de conflicto al insertar."""

    def __init__(self, case_id: str):
        self.case_id = case_id
        self._hechos: list[Hecho] = []
        self._n = 0

    def añadir(self, hecho: Hecho) -> Hecho:
        self._n += 1
        if hecho.evidence_id is None:
            hecho = Hecho(**{**asdict(hecho), "evidence_id": f"fact-{self._n:03d}"})
        self._hechos.append(hecho)
        return hecho

    def de(self, concepto: str) -> list[Hecho]:
        return [h for h in self._hechos if h.concept == concepto]

    def valor(self, concepto: str, timepoint: str | None = None):
        """Valor único de un concepto, o None si falta o está en conflicto.

        No devuelve «el último que apareció»: si dos hechos observados se
        contradicen, la respuesta correcta es que no se sabe, y `conflictos()`
        lo dice.
        """
        cands = [h for h in self.de(concepto)
                 if h.status == "observed" and (timepoint is None or h.timepoint == timepoint)]
        if not cands:
            return None
        valores = {h.value for h in cands}
        return cands[0].value if len(valores) == 1 else None

    def conflictos(self) -> list[str]:
        salida = []
        for concepto in {h.concept for h in self._hechos}:
            obs = [h for h in self.de(concepto) if h.status == "observed"]
            por_momento: dict[str | None, set] = {}
            for h in obs:
                por_momento.setdefault(h.timepoint, set()).add(h.value)
            if any(len(v) > 1 for v in por_momento.values()):
                salida.append(concepto)
        return sorted(salida)

    def sin_respaldo(self, textos: dict[str, str]) -> list[Hecho]:
        """Hechos cuya cita no cuadra con su fuente. Se rechazan, no se corrigen."""
        malos = []
        for h in self._hechos:
            if h.pointer is None:
                continue
            fuente = textos.get(h.source)
            if fuente is None or not h.respaldado_por(fuente):
                malos.append(h)
        return malos

    def __len__(self) -> int:
        return len(self._hechos)

    def __iter__(self) -> Iterable[Hecho]:
        return iter(self._hechos)

    def a_json(self) -> str:
        return json.dumps({"case_id": self.case_id,
                           "hechos": [asdict(h) for h in self._hechos],
                           "conflictos": self.conflictos()},
                          indent=2, ensure_ascii=False)
