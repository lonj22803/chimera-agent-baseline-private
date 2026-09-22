"""Comprueba, EN EL ENTORNO DE INFERENCIA (vLLM 0.25.0), que entrenamiento e inferencia ven lo mismo.

    python pipeline/check_template.py --model ../model/gemma-4-E2B-it --sft runs/sft.jsonl --n 20

Para cada ejemplo y cada turno de asistente:

1. **Prompt idéntico.** Pide a vLLM el prompt de ``messages[:i]`` (con ``llm.chat`` y
   ``max_tokens=1``, que devuelve ``prompt_token_ids``) y lo compara token a token con
   lo que produce ``render.py``. Se prueba con ``--tool-content string`` y ``blocks``;
   el que coincida es el que hay que pasar a ``train_lora.py``.
2. **Llamadas legibles.** Decodifica el tramo objetivo de cada turno con llamada a
   herramienta y lo pasa por el parser ``gemma4`` de vLLM (el de ``ChatVLLM``): tiene
   que devolver exactamente el nombre y los argumentos esperados.
3. **Fin de turno.** El último token de cada tramo tiene que ser uno de los que paran
   la generación en vLLM; si no, el modelo no aprenderá a parar.

Si algo falla, NO entrenes: arregla antes ``render.py`` o los mensajes.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import encode_example, normalise_messages, render_ids  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--sft", type=Path, required=True)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--tool-parser", default="gemma4")
    ap.add_argument("--max-model-len", type=int, default=32768)
    ap.add_argument("--gpu-memory-utilization", type=float, default=0.8)
    args = ap.parse_args()

    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams

    tok = AutoTokenizer.from_pretrained(args.model)
    llm = LLM(model=args.model, dtype="auto", max_model_len=args.max_model_len,
              gpu_memory_utilization=args.gpu_memory_utilization, enforce_eager=True)
    sp = SamplingParams(max_tokens=1, temperature=0.0)
    parser = importlib.import_module(f"vllm.tool_parsers.{args.tool_parser}_utils")
    stop_ids: set[int] = set()
    gen_cfg = Path(args.model) / "generation_config.json"
    if gen_cfg.exists():
        e = json.loads(gen_cfg.read_text()).get("eos_token_id")
        stop_ids |= set(e if isinstance(e, list) else [e] if e is not None else [])
    if tok.eos_token_id is not None:
        stop_ids.add(tok.eos_token_id)

    # reparto por igual entre (tarea, tipo): las tres tareas y react/form_fill
    by_kind: dict[tuple, list] = {}
    for line in args.sft.open():
        r = json.loads(line)
        by_kind.setdefault((r["task"], r["kind"]), []).append(r)
    records, i = [], 0
    while len(records) < args.n and any(i < len(v) for v in by_kind.values()):
        records += [v[i] for _, v in sorted(by_kind.items()) if i < len(v)]
        i += 1
    records = records[: args.n]
    print("ejemplos por (tarea, tipo):", {f"{t}:{k}": sum(1 for r in records if (r["task"], r["kind"]) == (t, k))
                                            for t, k in sorted(by_kind)})
    results = {"string": 0, "blocks": 0}
    total = 0
    problems: list[str] = []
    for r in records:
        # mensajes exactamente como los entrega ChatVLLM (argumentos como cadena, bloques con id)
        for i, m in enumerate(r["messages"]):
            if m["role"] != "assistant":
                continue
            total += 1
            vllm_ids = llm.chat(messages=r["messages"][:i], sampling_params=sp, tools=r.get("tools"),
                                use_tqdm=False)[0].prompt_token_ids
            for mode in results:
                ours = render_ids(tok, normalise_messages(r["messages"][:i], mode), r.get("tools"), True)
                if list(vllm_ids) == ours:
                    results[mode] += 1
        for mode in results:
            try:
                enc = encode_example(tok, r, mode)
            except ValueError as exc:
                problems.append(f"{r['case_id']} {r['kind']} [{mode}]: {exc}")
                continue
            if mode != "string":
                continue
            asst = [m for m in r["messages"] if m["role"] == "assistant"]
            for (a, b), m in zip(enc["spans"], asst):
                if enc["input_ids"][b - 1] not in stop_ids:
                    last = tok.decode(enc["input_ids"][b - 3:b], skip_special_tokens=False)
                    problems.append(f"{r['case_id']} {r['kind']}: el tramo no acaba en token de parada ({last!r})")
                if m.get("tool_calls"):
                    text = tok.decode(enc["input_ids"][a:b], skip_special_tokens=False)
                    calls = parser.parse_tool_calls(text, strict=False)
                    want = [(tc["function"]["name"], json.loads(tc["function"]["arguments"])) for tc in m["tool_calls"]]
                    got = [(c["name"], c["arguments"]) for c in calls]
                    if got != want:
                        problems.append(f"{r['case_id']}: parser devuelve {got} en vez de {want}")

    print(json.dumps({"turnos": total, "prompt_identico": results}, indent=2))
    for p in problems[:30]:
        print("PROBLEMA:", p)
    ok = [m for m, n in results.items() if n == total]
    if ok and not problems:
        print(f"OK -> usa --tool-content {ok[0]}")
    else:
        raise SystemExit("la plantilla de entrenamiento no reproduce a vLLM: no entrenes todavía")


if __name__ == "__main__":
    main()
