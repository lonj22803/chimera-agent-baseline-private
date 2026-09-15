"""Compara las dos salidas de Grand Challenge entre dos corridas del perfilador.

Sólo tiene sentido entre corridas con el **mismo** ``case_id``: va dentro de la
cabecera del acta (``Board.HEAD``), así que cambiarlo cambia el prompt y la
trayectoria. El perfilador lo fija con ``--case-id``.

Uso::

    python3 verification/compare_outputs.py <run_dir_A> <run_dir_B>
"""
import json
import sys
from pathlib import Path


def load(run: Path, interface: int) -> dict[str, object]:
    out = run / f"interf{interface}" / "output"
    return {p.name: json.loads(p.read_text()) for p in sorted(out.glob("*.json"))} if out.is_dir() else {}


def main() -> None:
    a, b = Path(sys.argv[1]), Path(sys.argv[2])
    report = {"a": a.name, "b": b.name, "interfaces": {}}
    for interface in (0, 1, 2):
        left, right = load(a, interface), load(b, interface)
        if not left and not right:
            continue
        same_names = sorted(left) == sorted(right)
        diffs = {}
        for name in sorted(set(left) | set(right)):
            if left.get(name) != right.get(name):
                diffs[name] = {"a": left.get(name), "b": right.get(name)}
        report["interfaces"][f"interf{interface}"] = {
            "mismos_ficheros": same_names,
            "identicos": same_names and not diffs,
            "ficheros_distintos": sorted(diffs),
            "detalle": diffs,
        }
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
