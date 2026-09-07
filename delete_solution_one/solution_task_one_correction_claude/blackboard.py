"""La pizarra: el medio compartido donde todos los participantes escriben.

Segunda generación: las entradas llevan **ronda**. El moderador puede reabrir la
sesión, y entonces los mismos expertos vuelven a intervenir viendo lo que se
escribió en la ronda anterior y lo que el moderador ha declarado que falta.

Una pizarra es una lista **append-only** de entradas tipadas. Cada
participante lee todo lo escrito hasta ese momento (renderizado como texto) y
añade una entrada propia. Nadie edita ni borra lo de otro: el registro es la
traza auditable del caso, y es lo que se persiste a disco para poder ver por
qué el agente decidió lo que decidió.

Dos representaciones, un solo origen de verdad:

* :meth:`Blackboard.render` — texto plano que entra en el prompt del siguiente
  participante. Compacto, numerado, sin ruido de formato.
* :meth:`Blackboard.to_dict` / :meth:`Blackboard.to_markdown` — la traza
  completa (incluye los payloads legibles por máquina) que se guarda en disco.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Orden de intervención canónico. Sólo se usa para documentar/ordenar la
#: traza; el grafo es quien realmente decide el turno.
SPEAKERS = (
    "INTAKE",
    "EXPERT-PRIOR",
    "EXPERT-PROTOCOL",
    "EXPERT-IMAGE",
    "MODERATOR",
    "LLM-1-GAP-ANALYST",
    "LLM-2-EVIDENCE",
    "LLM-3-CHAIR",
)


@dataclass
class Entry:
    """Una intervención en la pizarra.

    * ``speaker``  — quién escribe (uno de :data:`SPEAKERS`).
    * ``role``     — su papel en una frase, para que el siguiente participante
      sepa cuánto crédito darle.
    * ``title``    — cabecera legible de la entrada.
    * ``body``     — el texto que ve el siguiente LLM.
    * ``data``     — payload estructurado (no entra en el prompt; se persiste).
    """

    speaker: str
    role: str
    title: str
    body: str
    data: dict[str, Any] = field(default_factory=dict)
    round: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "speaker": self.speaker,
            "role": self.role,
            "title": self.title,
            "body": self.body,
            "data": self.data,
            "round": self.round,
        }


class Blackboard:
    """Pizarra compartida de un caso."""

    def __init__(self, case_id: str, task: int = 1) -> None:
        self.case_id = case_id
        self.task = task
        self.entries: list[Entry] = []

    # -- escritura -----------------------------------------------------------

    def post(self, speaker: str, role: str, title: str, body: str,
             data: dict[str, Any] | None = None, round: int = 1) -> Entry:
        entry = Entry(speaker=speaker, role=role, title=title, body=body.strip(),
                      data=data or {}, round=round)
        self.entries.append(entry)
        return entry

    # -- lectura -------------------------------------------------------------

    def render(self, up_to: int | None = None) -> str:
        """La pizarra tal y como la lee el siguiente participante."""
        shown = self.entries if up_to is None else self.entries[:up_to]
        head = (
            f"===== SHARED BLACKBOARD — case {self.case_id} (task {self.task}: biopsy decision) =====\n"
            f"{len(shown)} contribution(s) so far. Each block below was written by a different\n"
            "participant with a different view of the case. Nothing here is a final answer\n"
            "unless it is explicitly labelled as such.\n"
        )
        blocks = []
        last_round = 0
        for i, e in enumerate(shown, 1):
            if e.round != last_round:
                last_round = e.round
                blocks.append(
                    f"\n########## ROUND {e.round} "
                    + ("(opening round)" if e.round == 1 else "(reopened by the moderator)")
                    + " ##########\n"
                )
            blocks.append(
                f"\n----- [{i}] {e.title}\n"
                f"Posted by: {e.speaker} — {e.role}\n\n"
                f"{e.body}\n"
            )
        return head + "".join(blocks) + "\n===== END OF BLACKBOARD =====\n"

    def last_of(self, speaker: str) -> Entry | None:
        for e in reversed(self.entries):
            if e.speaker == speaker:
                return e
        return None

    # -- persistencia --------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "task": self.task,
            "n_entries": len(self.entries),
            "entries": [e.to_dict() for e in self.entries],
        }

    def to_markdown(self) -> str:
        lines = [f"# Pizarra — {self.case_id} (task {self.task})", ""]
        last = 0
        for i, e in enumerate(self.entries, 1):
            if e.round != last:
                last = e.round
                lines += [f"---", "", f"# Ronda {e.round}", ""]
            lines += [f"## [{i}] {e.title}", "", f"**{e.speaker}** — *{e.role}*", "", e.body, ""]
        return "\n".join(lines)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Blackboard:
        board = cls(payload["case_id"], payload.get("task", 1))
        board.entries = [Entry(**e) for e in payload.get("entries", [])]
        return board
