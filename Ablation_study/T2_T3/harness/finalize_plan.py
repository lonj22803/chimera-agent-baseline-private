"""Marca el plan como cerrado solo despues de una clausura valida."""

from __future__ import annotations

import json

from .paths import STUDY


def main() -> None:
    closure = json.loads((STUDY / "results/cierre.json").read_text())
    if not closure.get("complete"):
        raise RuntimeError("No se puede cerrar un estudio incompleto")
    path = STUDY / "PLAN_ABLACION_T2_T3.md"
    text = path.read_text()
    for line in (
        "> **Estado: F0 en curso.**",
        "> **Estado: F0-F2 completadas; F3 preparada.**",
    ):
        text = text.replace(line, "> **Estado: F0-F6 completadas.**")
    for phase in range(7):
        for status in ("en curso", "pendiente", "preparada"):
            text = text.replace(f"| F{phase} | {status} |", f"| F{phase} | completada |")
    path.write_text(text)


if __name__ == "__main__":
    main()
