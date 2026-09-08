"""La pizarra, escrita como el acta de una junta clínica.

Diferencia de fondo con la generación anterior: allí la pizarra era una lista de
bloques con cabeceras técnicas, pies de página automáticos y avisos entre
corchetes. Se leía como un log. Aquí se lee como un acta: **intervenciones
numeradas, cada una con quién habla y en calidad de qué**, en el orden en que se
produjeron, y nada más.

Tres reglas que hacen que el acta sirva de traza:

1. **La numeración es global y monótona.** Si el verificador devuelve la sesión
   al moderador, las intervenciones de la segunda vuelta son 9, 10, 11 — no
   "ronda 2 · intervención 5". Citar "intervención 7" identifica un turno único.
2. **Nadie edita lo de otro.** Sólo se añade.
3. **El cuerpo de la intervención es lo que dijo el participante**, sin
   anotaciones del sistema mezcladas. Lo que el código calcula (qué se abrió,
   qué falta) va en ``data``, que se persiste pero no se le mete al siguiente
   modelo dentro del texto de otro.

Dos vistas del mismo origen:

* :meth:`Board.render` — el acta tal y como la lee el siguiente participante.
* :meth:`Board.thread` — el índice de una línea por intervención, que es lo que
  el presidente usa para construir el hilo de trazabilidad del dictamen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Los participantes de la junta y el papel con el que se presentan. El texto de
#: la derecha es lo que ve el resto: dice en calidad de qué habla cada uno y, por
#: tanto, cuánto crédito darle.
WHO = {
    "INTAKE": "the record clerk; reads the file out loud and interprets nothing",
    "EXPERT-CLASSIFIER": "statistical classifier; suggests a starting point, decides nothing",
    "EXPERT-COHORT": "cohort criterion; what the labelled series did in this exact situation",
    "EXPERT-EAU": "EAU guideline specialist; speaks only from the guideline text he retrieved",
    "MODERATOR": "chairs the discussion; sets the verification plan and the open questions",
    "EXPERT-IMAGE": "imaging-embedding expert; reports what the frozen MRI vectors give",
    "REGISTRAR": "the registrar who pulls up documents; reports what they say, nothing else",
    "VERIFIER": "second EAU reader; checks against the guideline whether this can be decided yet",
    "CHAIR": "the senior urologist who signs the decision",
}


@dataclass
class Intervention:
    """Un turno de palabra.

    ``n``        número de intervención, global y creciente.
    ``speaker``  quién habla (clave de :data:`WHO`).
    ``body``     lo que dijo, literal.
    ``data``     lo que el código calculó de ese turno; se persiste, no se
                 le inyecta a nadie dentro del texto de otro participante.
    ``pass_``    vuelta de la sesión (1 = la primera).
    """

    n: int
    speaker: str
    body: str
    data: dict[str, Any] = field(default_factory=dict)
    pass_: int = 1

    @property
    def who(self) -> str:
        return WHO.get(self.speaker, self.speaker)

    def to_dict(self) -> dict[str, Any]:
        return {"n": self.n, "speaker": self.speaker, "who": self.who,
                "body": self.body, "data": self.data, "pass_": self.pass_}


class Board:
    """El acta de un caso."""

    def __init__(self, case_id: str, task: int = 1) -> None:
        self.case_id = case_id
        self.task = task
        self.items: list[Intervention] = []

    # -- escritura -----------------------------------------------------------

    def say(self, speaker: str, body: str, data: dict[str, Any] | None = None,
            pass_: int = 1) -> Intervention:
        item = Intervention(n=len(self.items) + 1, speaker=speaker, body=body.strip(),
                            data=data or {}, pass_=pass_)
        self.items.append(item)
        return item

    # -- lectura -------------------------------------------------------------

    HEAD = (
        "===== CASE CONFERENCE — case {case_id} (task {task}: biopsy decision) =====\n"
        "This is the minute of a live case conference. Colleagues speak in turn; each one\n"
        "sees everything said before. Interventions are numbered so that anyone can point\n"
        "at a specific turn. Nothing here is the decision until the chair signs it.\n"
    )

    def render(self) -> str:
        blocks = [self.HEAD.format(case_id=self.case_id, task=self.task)]
        for it in self.items:
            blocks.append(
                f"\n--- INTERVENTION {it.n} · {it.speaker} ({it.who}) ---\n\n{it.body}\n"
            )
        return "".join(blocks) + "\n===== END OF MINUTE =====\n"

    def thread(self) -> str:
        """Índice de una línea por intervención: el hilo que cita el presidente."""
        lines = []
        for it in self.items:
            gist = " ".join((it.data.get("gist") or it.body).split())
            lines.append(f"  [{it.n}] {it.speaker}: {gist[:150]}")
        return "\n".join(lines)

    def last_of(self, speaker: str) -> Intervention | None:
        for it in reversed(self.items):
            if it.speaker == speaker:
                return it
        return None

    # -- persistencia --------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {"case_id": self.case_id, "task": self.task, "n_interventions": len(self.items),
                "interventions": [it.to_dict() for it in self.items]}

    def to_markdown(self) -> str:
        lines = [f"# Junta clínica — {self.case_id} (tarea {self.task})", ""]
        for it in self.items:
            lines += [f"## Intervención {it.n} — {it.speaker}", "",
                      f"*{it.who}* · vuelta {it.pass_}", "", it.body, ""]
        return "\n".join(lines)

    @classmethod
    def from_dicts(cls, case_id: str, task: int, items: list[dict]) -> Board:
        board = cls(case_id, task)
        board.items = [
            Intervention(n=d["n"], speaker=d["speaker"], body=d["body"],
                         data=d.get("data") or {}, pass_=d.get("pass_", 1))
            for d in items
        ]
        return board
