"""Entrena un adaptador LoRA sobre Gemma 4 E2B-it con las trayectorias de ``build_sft.py``.

Un solo adaptador para las tres tareas (el prompt ya dice cuál es). Pensado para
una GPU de 24 GB: batch 1 + acumulación, gradient checkpointing y logits solo en
las posiciones con pérdida.

    # un pliegue de la validación cruzada (entrena en los otros, valida en un 15 % interno)
    python pipeline/train_lora.py --model ../model/gemma-4-E2B-it --sft runs/sft.jsonl \
        --fold 0 --out runs/r16/fold0 --tool-content string

    # modelo final: todos los casos, épocas fijas elegidas en la validación cruzada
    python pipeline/train_lora.py --model ../model/gemma-4-E2B-it --sft runs/sft.jsonl \
        --fold -1 --epochs 3 --out runs/r16/final --tool-content string

``--tool-content`` tiene que ser el valor que ``check_template.py`` dio por bueno.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import encode_example  # noqa: E402

DEFAULT_TARGET = r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)$"


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------


def label_of(r: dict) -> str:
    m = r.get("meta") or {}
    if r["task"] == 3:
        return f"3:event={m.get('event')}"
    if r["kind"] == "form_fill":
        obj = json.loads(r["messages"][-1]["content"])
        return f"{r['task']}:{obj.get('biopsy_decision', obj.get('action'))}"
    return f"{r['task']}:?"


def split_records(records: list[dict], fold: int, val_frac: float, seed: int):
    """Entrenamiento / validación interna / test del pliegue, siempre por caso."""
    if fold < 0:
        return records, [], []
    test = [r for r in records if r.get("fold") == fold]
    rest = [r for r in records if r.get("fold") != fold]
    # validación interna: un val_frac de los casos (no de las filas), estratificado por tarea
    by_task: dict[int, list[str]] = defaultdict(list)
    for r in rest:
        if r["kind"] == "form_fill":
            by_task[r["task"]].append(r["case_id"])
    rng = random.Random(seed)
    val_ids = set()
    for t, ids in by_task.items():
        ids = sorted(set(ids))
        rng.shuffle(ids)
        val_ids.update(ids[: max(1, round(len(ids) * val_frac))] if len(ids) > 3 else [])
    train = [r for r in rest if r["case_id"] not in val_ids]
    val = [r for r in rest if r["case_id"] in val_ids]
    return train, val, test


def oversample(records: list[dict], factor_minority: float, rng: random.Random) -> list[dict]:
    """Duplica los casos de clases minoritarias (por tarea) hasta ~factor × su tamaño."""
    if factor_minority <= 1:
        return records
    by_case: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_case[(r["task"], r["case_id"])].append(r)
    labels = {}
    for key, rs in by_case.items():
        ff = [r for r in rs if r["kind"] == "form_fill"]
        labels[key] = label_of(ff[0]) if ff else f"{key[0]}:?"
    counts = Counter(labels.values())
    out = list(records)
    for task in {k[0] for k in by_case}:
        task_counts = {l: n for l, n in counts.items() if l.startswith(f"{task}:")}
        if not task_counts:
            continue
        top = max(task_counts.values())
        for key, lab in labels.items():
            if key[0] != task or task_counts[lab] >= top:
                continue
            extra = min(factor_minority, top / task_counts[lab]) - 1
            reps = int(extra) + (1 if rng.random() < extra - int(extra) else 0)
            for _ in range(reps):
                out.extend(by_case[key])
    rng.shuffle(out)
    return out


def encode_all(tok, records, tool_content, max_len, log):
    enc, skipped = [], Counter()
    for r in records:
        try:
            e = encode_example(tok, r, tool_content)
        except ValueError as exc:
            skipped[f"plantilla:{exc}"] += 1
            continue
        if len(e["input_ids"]) > max_len:
            skipped["demasiado_largo"] += 1
            continue
        e["record"] = r
        enc.append(e)
    if skipped:
        log(f"  descartados: {dict(skipped)}")
    return enc


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------


def load_model(path: str, model_class: str, qlora: bool):
    import transformers

    kwargs = {"dtype": torch.bfloat16}
    if qlora:
        from transformers import BitsAndBytesConfig

        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
        )
    classes = [model_class] if model_class != "auto" else ["AutoModelForImageTextToText", "AutoModelForCausalLM"]
    last = None
    for name in classes:
        try:
            model = getattr(transformers, name).from_pretrained(path, **kwargs)
            return model, name
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise RuntimeError(f"no se pudo cargar {path} con {classes}: {last}")


def attach_lora(model, args, log):
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    names = [n for n, _ in model.named_modules() if re.fullmatch(args.target_regex, n)]
    if not names:
        sample = [n for n, _ in model.named_modules()][:60]
        raise SystemExit(f"--target-regex no casa con ningún módulo. Algunos nombres:\n" + "\n".join(sample))
    log(f"  LoRA sobre {len(names)} módulos (p. ej. {names[0]})")
    if args.qlora:
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    cfg = LoraConfig(r=args.rank, lora_alpha=args.alpha, lora_dropout=args.dropout, bias="none",
                     target_modules=args.target_regex, task_type="CAUSAL_LM")
    model = get_peft_model(model, cfg)
    model.print_trainable_parameters()
    return model


def loss_on(model, e, device, use_logits_to_keep: bool):
    ids = torch.tensor([e["input_ids"]], device=device)
    labels = torch.tensor(e["labels"], device=device)
    # La posición p predice el token p+1: se guardan los logits de las posiciones
    # cuya etiqueta siguiente tiene pérdida.
    tgt_next = (labels[1:] != -100).nonzero(as_tuple=True)[0]
    if use_logits_to_keep:
        out = model(input_ids=ids, logits_to_keep=tgt_next, use_cache=False)
        logits = out.logits[0]
    else:
        out = model(input_ids=ids, use_cache=False)
        logits = out.logits[0, tgt_next]
    targets = labels[1:][tgt_next]
    return torch.nn.functional.cross_entropy(logits.float(), targets), int(targets.numel())


@torch.no_grad()
def evaluate_loss(model, enc, device, use_ltk):
    model.eval()
    tot, n = 0.0, 0
    for e in enc:
        loss, k = loss_on(model, e, device, use_ltk)
        tot += loss.item() * k
        n += k
    model.train()
    return tot / max(n, 1)


@torch.no_grad()
def evaluate_decisions(model, tok, enc, device, tool_content, max_new_tokens=400):
    """Acierto de la decisión generando el JSON del form-fill (greedy).

    Aproximación barata al criterio real: usa el razonamiento de referencia como
    transcripción. El número bueno es el de ``eval_fold.sh`` con vLLM.
    """
    from render import normalise_messages, render_ids

    model.eval()
    ok = n = 0
    for e in enc:
        r = e["record"]
        if r["kind"] != "form_fill" or r["task"] == 3:
            continue
        msgs = normalise_messages(r["messages"][:-1], tool_content)
        ids = torch.tensor([render_ids(tok, msgs, None, add_generation_prompt=True)], device=device)
        out = model.generate(input_ids=ids, max_new_tokens=max_new_tokens, do_sample=False)
        text = tok.decode(out[0, ids.shape[1]:], skip_special_tokens=True)
        want = json.loads(r["messages"][-1]["content"])
        key = "biopsy_decision" if r["task"] == 1 else "action"
        m = re.search(r"\{.*\}", text, re.DOTALL)
        try:
            got = json.loads(m.group(0)).get(key) if m else None
        except json.JSONDecodeError:
            got = None
        ok += int(got == want[key])
        n += 1
    model.train()
    return ok / n if n else float("nan"), n


# ---------------------------------------------------------------------------
# Bucle
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="carpeta de gemma-4-E2B-it")
    ap.add_argument("--sft", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--fold", type=int, default=0, help="pliegue de test; -1 = entrenar con todo")
    ap.add_argument("--tasks", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--tool-content", choices=["string", "blocks"], default="string")
    ap.add_argument("--model-class", default="auto")
    ap.add_argument("--target-regex", default=DEFAULT_TARGET)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--alpha", type=int, default=32)
    ap.add_argument("--dropout", type=float, default=0.1)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--warmup", type=float, default=0.05)
    ap.add_argument("--max-len", type=int, default=10240)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--oversample", type=float, default=2.0, help="factor máximo para clases minoritarias")
    ap.add_argument("--patience", type=int, default=1, help="épocas sin mejora antes de parar")
    ap.add_argument("--qlora", action="store_true")
    ap.add_argument("--no-logits-to-keep", action="store_true",
                    help="si el forward del modelo no acepta logits_to_keep (usa más memoria)")
    ap.add_argument("--eval-generate", action="store_true",
                    help="en validación, generar el JSON y medir el acierto de la decisión")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    rng = random.Random(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    logf = (args.out / "train.log").open("a")

    def log(msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    (args.out / "args.json").write_text(json.dumps({k: str(v) for k, v in vars(args).items()}, indent=2))
    records = [json.loads(l) for l in args.sft.open()]
    records = [r for r in records if r["task"] in args.tasks]
    train, val, test = split_records(records, args.fold, args.val_frac, args.seed)
    (args.out / "split.json").write_text(json.dumps({
        "train": sorted({r["case_id"] for r in train}),
        "val": sorted({r["case_id"] for r in val}),
        "test": sorted({r["case_id"] for r in test}),
    }, indent=2))
    train = oversample(train, args.oversample, rng)
    log(f"filas: train={len(train)} val={len(val)} test(no se usa)={len(test)}")

    from transformers import AutoTokenizer, get_cosine_schedule_with_warmup

    tok = AutoTokenizer.from_pretrained(args.model)
    enc_train = encode_all(tok, train, args.tool_content, args.max_len, log)
    enc_val = encode_all(tok, val, args.tool_content, args.max_len, log)
    lens = sorted(len(e["input_ids"]) for e in enc_train)
    if lens:
        log(f"longitudes: p50={lens[len(lens) // 2]} p95={lens[int(len(lens) * 0.95)]} max={lens[-1]}")

    model, cls = load_model(args.model, args.model_class, args.qlora)
    log(f"modelo cargado con {cls}")
    model.config.use_cache = False
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model = attach_lora(model, args, log)
    device = next(model.parameters()).device
    if device.type == "cpu" and torch.cuda.is_available():
        model.to("cuda")
        device = torch.device("cuda")
    use_ltk = not args.no_logits_to_keep

    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=0.0)
    steps = math.ceil(len(enc_train) / args.grad_accum) * args.epochs
    sched = get_cosine_schedule_with_warmup(opt, max(1, int(steps * args.warmup)), max(1, steps))

    best, best_epoch, bad = None, None, 0
    history = []
    model.train()
    for epoch in range(1, args.epochs + 1):
        rng.shuffle(enc_train)
        tot, ntok, t0 = 0.0, 0, time.time()
        opt.zero_grad(set_to_none=True)
        for i, e in enumerate(enc_train, 1):
            loss, k = loss_on(model, e, device, use_ltk)
            (loss / args.grad_accum).backward()
            tot += loss.item() * k
            ntok += k
            if i % args.grad_accum == 0 or i == len(enc_train):
                torch.nn.utils.clip_grad_norm_(params, 1.0)
                opt.step()
                sched.step()
                opt.zero_grad(set_to_none=True)
        row = {"epoch": epoch, "train_loss": tot / max(ntok, 1), "secs": round(time.time() - t0)}
        if enc_val:
            row["val_loss"] = evaluate_loss(model, enc_val, device, use_ltk)
            if args.eval_generate:
                row["val_decision_acc"], row["val_n"] = evaluate_decisions(model, tok, enc_val, device, args.tool_content)
        if torch.cuda.is_available():
            row["max_mem_gb"] = round(torch.cuda.max_memory_allocated() / 2**30, 2)
        history.append(row)
        log(json.dumps(row))
        model.save_pretrained(args.out / f"adapter_epoch{epoch}")

        if enc_val:
            # criterio: acierto de la decisión si se mide; si no, pérdida de validación
            score = (row.get("val_decision_acc", float("nan")), -row["val_loss"])
            score = (score[0] if score[0] == score[0] else 0.0, score[1])
            if best is None or score > best:
                best, best_epoch, bad = score, epoch, 0
            else:
                bad += 1
                if bad > args.patience:
                    log(f"parada temprana en la época {epoch}")
                    break
    chosen = best_epoch or history[-1]["epoch"]
    (args.out / "history.json").write_text(json.dumps({"history": history, "best_epoch": chosen}, indent=2))
    (args.out / "BEST_EPOCH").write_text(f"{chosen}\n")
    log(f"mejor época: {chosen} -> {args.out / f'adapter_epoch{chosen}'}")


if __name__ == "__main__":
    main()
