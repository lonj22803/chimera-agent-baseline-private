"""Renderizado con la plantilla de chat del modelo y máscara de pérdida.

La plantilla es la del propio modelo (``tokenizer.apply_chat_template``), la misma
que usa vLLM en ``LLM.chat``. ``check_template.py`` comprueba en el entorno de
inferencia que los ids que produce este módulo coinciden token a token con los
``prompt_token_ids`` que genera vLLM. Si no coinciden, no se entrena.

Qué tokens llevan pérdida: los que el modelo GENERA en inferencia, es decir, cada
turno de asistente (llamadas a herramientas, texto final y JSON del form-fill),
incluido el token con el que termina el turno. Nada del prompt, de los resultados
de herramientas ni del sistema.
"""

from __future__ import annotations

import copy
from typing import Any


def normalise_messages(messages: list[dict[str, Any]], tool_content: str) -> list[dict[str, Any]]:
    """Prepara los mensajes como los ve la plantilla.

    ``tool_content``:
      * ``"string"``  concatena los bloques de texto de los turnos ``tool`` (lo que hace
        vLLM cuando la plantilla espera ``content`` como cadena);
      * ``"blocks"``  deja la lista de bloques, sin el ``id`` de LangChain.
    ``check_template.py`` dice cuál de los dos reproduce a vLLM.
    """
    out = copy.deepcopy(messages)
    for m in out:
        if m["role"] == "tool" and isinstance(m.get("content"), list):
            if tool_content == "string":
                m["content"] = "\n".join(b.get("text", "") for b in m["content"] if b.get("type") == "text")
            else:
                m["content"] = [{"type": "text", "text": b.get("text", "")} for b in m["content"]]
        if m["role"] == "assistant" and m.get("tool_calls"):
            # La plantilla de HF espera los argumentos como dict; vLLM los convierte igual.
            for tc in m["tool_calls"]:
                args = tc["function"].get("arguments")
                if isinstance(args, str):
                    import json

                    tc["function"]["arguments"] = json.loads(args)
    return out


def render_ids(tokenizer, messages, tools, add_generation_prompt: bool) -> list[int]:
    kwargs = {"tokenize": True, "add_generation_prompt": add_generation_prompt}
    if tools:
        kwargs["tools"] = tools
    ids = tokenizer.apply_chat_template(messages, **kwargs)
    if isinstance(ids, dict) or hasattr(ids, "input_ids"):
        ids = ids["input_ids"]
    if ids and isinstance(ids[0], list):
        ids = ids[0]
    return list(ids)


def _lcp(a: list[int], b: list[int]) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def encode_example(tokenizer, record: dict[str, Any], tool_content: str = "string") -> dict[str, Any]:
    """Devuelve ``input_ids``, ``labels`` (−100 fuera de los turnos del asistente) y los tramos.

    Para cada turno de asistente ``i``:
      inicio = len(render(messages[:i], add_generation_prompt=True))   # lo que ve vLLM
      fin    = prefijo común entre render(completo) y render(messages[:i+1])
    Se exige que el prefijo de generación sea prefijo exacto de la conversación completa;
    si no lo es, la plantilla no es estable y el ejemplo se rechaza.
    """
    msgs = normalise_messages(record["messages"], tool_content)
    tools = record.get("tools")
    full = render_ids(tokenizer, msgs, tools, add_generation_prompt=False)
    labels = [-100] * len(full)
    spans = []
    for i, m in enumerate(msgs):
        if m["role"] != "assistant":
            continue
        prefix = render_ids(tokenizer, msgs[:i], tools, add_generation_prompt=True)
        if full[: len(prefix)] != prefix:
            raise ValueError(f"plantilla inestable en el turno {i}: el prompt de generación no es prefijo")
        upto = render_ids(tokenizer, msgs[: i + 1], tools, add_generation_prompt=False)
        end = _lcp(full, upto)
        if end <= len(prefix):
            raise ValueError(f"turno {i} vacío tras renderizar")
        # vLLM deja de generar en el token de fin de turno: lo que la plantilla ponga
        # después (un salto de línea, p. ej.) no lo genera el modelo y no lleva pérdida.
        # Si el fin de turno cae justo fuera del tramo, se incluye.
        eos = set(_eos_ids(tokenizer))
        stops = [p for p in range(len(prefix), end) if full[p] in eos]
        if stops:
            end = stops[-1] + 1
        elif end < len(full) and full[end] in eos:
            end += 1
        for p in range(len(prefix), end):
            labels[p] = full[p]
        spans.append((len(prefix), end))
    return {"input_ids": full, "labels": labels, "spans": spans}


def _eos_ids(tokenizer) -> list[int]:
    ids = []
    for attr in ("eos_token_id",):
        v = getattr(tokenizer, attr, None)
        if isinstance(v, int):
            ids.append(v)
        elif isinstance(v, (list, tuple)):
            ids.extend(v)
    for tok in ("<end_of_turn>", "<turn|>", "<eos>"):
        try:
            tid = tokenizer.convert_tokens_to_ids(tok)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(tid, int) and tid >= 0 and tid != getattr(tokenizer, "unk_token_id", None):
            ids.append(tid)
    return sorted(set(ids))


def describe(tokenizer, enc: dict[str, Any], max_chars: int = 400) -> str:
    """Texto legible de los tramos con pérdida (para revisarlos a ojo)."""
    parts = []
    for a, b in enc["spans"]:
        text = tokenizer.decode(enc["input_ids"][a:b], skip_special_tokens=False)
        parts.append(f"[{a}:{b}] {text[:max_chars]!r}{' …' if len(text) > max_chars else ''}")
    return "\n".join(parts)
