"""Vuelca en texto legible un ejemplo ``react`` y uno ``form_fill`` por tarea.

    python pipeline/dump_examples.py --sft runs/sft.jsonl --out tasks

Escribe ``<out>/task<N>/sft_react.txt`` y ``sft_form_fill.txt``: cada mensaje con su
rol, y marcados con ``>>> PÉRDIDA`` los turnos que el modelo aprende a generar.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def as_text(r: dict) -> str:
    out = [f"# task {r['task']} · {r['kind']} · caso {r['case_id']}", ""]
    if r.get("tools"):
        out.append(f"[tools={', '.join(t['function']['name'] for t in r['tools'])}]")
        out.append("")
    for m in r["messages"]:
        tag = ">>> PÉRDIDA · " if m["role"] == "assistant" else ""
        out.append(f"===== {tag}{m['role']} =====")
        if m.get("tool_calls"):
            for tc in m["tool_calls"]:
                out.append(f"<llamada> {tc['function']['name']}({tc['function']['arguments']})")
        elif isinstance(m.get("content"), list):
            out.append("\n".join(b.get("text", "") for b in m["content"]))
        else:
            out.append(str(m.get("content")))
        out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sft", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    seen = set()
    for line in args.sft.open():
        r = json.loads(line)
        key = (r["task"], r["kind"])
        if key in seen or r.get("variant"):
            continue
        seen.add(key)
        d = args.out / f"task{r['task']}"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"sft_{r['kind']}.txt").write_text(as_text(r))
        print("escrito", d / f"sft_{r['kind']}.txt")


if __name__ == "__main__":
    main()
