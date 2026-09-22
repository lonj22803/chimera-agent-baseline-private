"""Fusiona el adaptador en los pesos y exporta un checkpoint que vLLM carga sin cambios.

    python pipeline/merge_export.py --base ../model/gemma-4-E2B-it \
        --adapter runs/r16/fold0/adapter_epoch2 --out runs/r16/fold0/merged --check-sft runs/sft.jsonl

Hace además tres comprobaciones:
  1. paridad de logits PEFT sin fusionar vs fusionado sobre unos ejemplos;
  2. ``config.json`` del fusionado vs el original (solo pueden cambiar campos inocuos);
  3. copia de tokenizador, plantilla de chat y ficheros del procesador desde el base.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_lora import load_model  # noqa: E402

COPY_FROM_BASE = (
    "tokenizer.json", "tokenizer_config.json", "tokenizer.model", "special_tokens_map.json",
    "chat_template.jinja", "chat_template.json", "processor_config.json",
    "preprocessor_config.json", "generation_config.json", "added_tokens.json",
)
IGNORED_CONFIG_KEYS = {"_name_or_path", "transformers_version", "torch_dtype", "dtype", "use_cache"}


def diff_config(a: dict, b: dict, path: str = "") -> list[str]:
    out = []
    for k in sorted(set(a) | set(b)):
        if k in IGNORED_CONFIG_KEYS:
            continue
        p = f"{path}.{k}" if path else k
        if k not in a or k not in b:
            out.append(f"{p}: {'falta en fusionado' if k not in b else 'nuevo en fusionado'}")
        elif isinstance(a[k], dict) and isinstance(b[k], dict):
            out.extend(diff_config(a[k], b[k], p))
        elif a[k] != b[k]:
            out.append(f"{p}: {a[k]!r} -> {b[k]!r}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model-class", default="auto")
    ap.add_argument("--check-sft", type=Path, default=None, help="JSONL para la prueba de paridad")
    ap.add_argument("--n-check", type=int, default=3)
    ap.add_argument("--tool-content", default="string")
    args = ap.parse_args()

    from peft import PeftModel
    from transformers import AutoTokenizer

    base, cls = load_model(args.base, args.model_class, qlora=False)
    peft_model = PeftModel.from_pretrained(base, args.adapter)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    peft_model.to(device).eval()

    samples = []
    if args.check_sft:
        from render import encode_example

        tok = AutoTokenizer.from_pretrained(args.base)
        for line in args.check_sft.open():
            r = json.loads(line)
            samples.append(torch.tensor([encode_example(tok, r, args.tool_content)["input_ids"][:2048]]))
            if len(samples) >= args.n_check:
                break
    with torch.no_grad():
        ref = [peft_model(input_ids=s.to(device), use_cache=False).logits[0, -64:].float().cpu() for s in samples]

    merged = peft_model.merge_and_unload()
    with torch.no_grad():
        got = [merged(input_ids=s.to(device), use_cache=False).logits[0, -64:].float().cpu() for s in samples]
    for i, (a, b) in enumerate(zip(ref, got)):
        d = (a - b).abs().max().item()
        same = (a.argmax(-1) == b.argmax(-1)).float().mean().item()
        print(f"paridad ejemplo {i}: max|Δlogit|={d:.4f}  argmax igual={same:.3f}")
        if same < 0.98:
            raise SystemExit("la fusión cambia las predicciones: no exportar")

    args.out.mkdir(parents=True, exist_ok=True)
    merged.to(torch.bfloat16).save_pretrained(args.out, safe_serialization=True, max_shard_size="5GB")
    base_dir = Path(args.base)
    for name in COPY_FROM_BASE:
        if (base_dir / name).exists():
            shutil.copy2(base_dir / name, args.out / name)

    a = json.loads((base_dir / "config.json").read_text())
    b = json.loads((args.out / "config.json").read_text())
    diffs = diff_config(a, b)
    (args.out / "MERGE_REPORT.json").write_text(json.dumps(
        {"base": str(base_dir), "adapter": args.adapter, "class": cls, "config_diffs": diffs}, indent=2))
    if diffs:
        print("AVISO: config.json cambia respecto al base:\n  " + "\n  ".join(diffs))
    print(f"exportado en {args.out} (clase {cls})")


if __name__ == "__main__":
    main()
