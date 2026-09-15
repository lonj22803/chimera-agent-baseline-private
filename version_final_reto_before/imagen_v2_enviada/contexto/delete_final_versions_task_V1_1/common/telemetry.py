"""Medición de la sesión: tokens, tiempo, memoria y herramientas, por papel.

El baseline no persiste ninguna traza, y sin traza no se puede responder a
«¿cuánto cuesta esto y dónde se va el tiempo?». Este módulo lo mide **sin tocar
el upstream**: un ``BaseCallbackHandler`` que LangGraph propaga a todas las
llamadas anidadas del grafo, de modo que cada invocación del modelo y cada
llamada a herramienta pasa por aquí.

Qué se mide y cómo:

``tokens``
    Exactos, con el tokenizador del propio modelo (``ChatVLLM.tokenizer``, que
    es el que vLLM usa para generar). Se cuentan por separado los de entrada
    —el prompt completo que ve el modelo, con el acta dentro— y los de salida.
    Si el backend no expone tokenizador se estima a 4 caracteres por token y se
    marca ``approx=True``, para que nadie lea una estimación como una medida.

``papel``
    Se deduce de la cabecera del mensaje de sistema (``YOU ARE THE REGISTRAR``…).
    Es preferible a etiquetar la llamada desde el grafo porque no obliga a
    envolver el modelo, y el prompt de sistema es justamente lo que define el
    papel.

``memoria``
    Dos cifras distintas que suelen confundirse: la **RSS del proceso**
    (``resource.getrusage``), que es memoria de anfitrión, y la **VRAM ocupada
    en el dispositivo** (``torch.cuda.mem_get_info``), que incluye lo que vLLM
    reservó por su cuenta y por tanto no se ve con ``torch.cuda.memory_allocated``.

``herramientas``
    Nombre, latencia y tamaño de la respuesta de cada llamada MCP.
"""

from __future__ import annotations

import logging
import re
import resource
import time
import threading
from collections import defaultdict
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

log = logging.getLogger(__name__)


class ResourceMonitor:
    """Sample device-wide VRAM, including vLLM workers, during blocking phases.

    RSS is the process high-water mark, not aggregate container RAM. Docker's
    cgroup peak is checked separately. A missing CUDA measurement is never zero.
    """
    def __init__(self, interval=.5):
        self.interval = interval
        self.peak = None
        self.total = None
        self.stop = threading.Event()

    def sample(self):
        used, total = device_vram_mb()
        if total:
            self.total = total
            self.peak = max(self.peak or 0, used)

    def _loop(self):
        while not self.stop.wait(self.interval):
            self.sample()

    def __enter__(self):
        self.sample()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return self

    def summary(self):
        self.sample()
        return {'host_peak_rss_mb': host_rss_mb(), 'device_peak_vram_mb': self.peak,
                'device_total_mb': self.total, 'vram_sample_interval_seconds': self.interval}

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(timeout=2)

_ROLE_PATTERNS = (
    ("eau", re.compile(r"YOU ARE EXPERT-EAU", re.I)),
    ("moderator", re.compile(r"YOU ARE THE MODERATOR", re.I)),
    ("registrar", re.compile(r"YOU ARE THE REGISTRAR", re.I)),
    ("verifier", re.compile(r"YOU ARE THE VERIFIER", re.I)),
    ("chair", re.compile(r"You are the consultant urologist", re.I)),
)


def role_of(prompt_text: str) -> str:
    for name, pattern in _ROLE_PATTERNS:
        if pattern.search(prompt_text or ""):
            return name
    return "other"


def host_rss_mb() -> float:
    """Pico de memoria residente del proceso, en MiB (Linux da KiB)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def device_vram_mb() -> tuple[float, float]:
    """(usada, total) de la GPU en MiB, o (0, 0) si no hay CUDA.

    ``mem_get_info`` mira el dispositivo entero, así que incluye la reserva de
    vLLM. ``memory_allocated`` sólo vería los tensores de PyTorch y daría una
    cifra ridículamente baja.
    """
    try:
        import torch  # noqa: PLC0415
        if not torch.cuda.is_available():
            return 0.0, 0.0
        free, total = torch.cuda.mem_get_info()
        return (total - free) / 2**20, total / 2**20
    except Exception:  # noqa: BLE001
        return 0.0, 0.0


class ConferenceMeter(BaseCallbackHandler):
    """Contador por caso. Se reinicia con :meth:`start_case`."""

    raise_error = False

    def __init__(self, tokenizer: Any = None) -> None:
        self.tokenizer = tokenizer
        self.approx = tokenizer is None
        self.rows: list[dict[str, Any]] = []
        self.tools: list[dict[str, Any]] = []
        self._t0: dict[str, float] = {}
        self._prompt: dict[str, str] = {}
        self._tool_t0: dict[str, float] = {}
        self._tool_name: dict[str, str] = {}
        self.case_id: str | None = None
        self.peak_vram = 0.0

    # -- ciclo por caso ------------------------------------------------------

    def start_case(self, case_id: str) -> None:
        self.case_id = case_id
        self.rows, self.tools = [], []
        self.peak_vram = device_vram_mb()[0]

    def _count(self, text: str) -> int:
        if not text:
            return 0
        if self.tokenizer is not None:
            try:
                return len(self.tokenizer.encode(text, add_special_tokens=False))
            except Exception:  # noqa: BLE001
                pass
        return max(1, len(text) // 4)

    # -- llamadas al modelo --------------------------------------------------

    def on_chat_model_start(self, serialized, messages, *, run_id=None, **kwargs) -> None:  # noqa: D102
        try:
            flat = "\n".join(getattr(m, "content", "") if isinstance(getattr(m, "content", ""), str)
                             else str(getattr(m, "content", "")) for m in (messages[0] if messages else []))
        except Exception:  # noqa: BLE001
            flat = ""
        self._prompt[str(run_id)] = flat
        self._t0[str(run_id)] = time.perf_counter()

    def on_llm_start(self, serialized, prompts, *, run_id=None, **kwargs) -> None:  # noqa: D102
        self._prompt[str(run_id)] = "\n".join(prompts or [])
        self._t0[str(run_id)] = time.perf_counter()

    def on_llm_end(self, response, *, run_id=None, **kwargs) -> None:  # noqa: D102
        key = str(run_id)
        prompt = self._prompt.pop(key, "")
        t0 = self._t0.pop(key, None)
        text, n_tool_calls = "", 0
        try:
            gen = response.generations[0][0]
            msg = getattr(gen, "message", None)
            content = getattr(msg, "content", None) if msg is not None else getattr(gen, "text", "")
            text = content if isinstance(content, str) else str(content)
            n_tool_calls = len(getattr(msg, "tool_calls", None) or []) if msg is not None else 0
        except Exception:  # noqa: BLE001
            pass
        self.rows.append({
            "case_id": self.case_id, "role": role_of(prompt),
            "prompt_tokens": self._count(prompt), "completion_tokens": self._count(text),
            "prompt_chars": len(prompt), "completion_chars": len(text),
            "seconds": round(time.perf_counter() - t0, 3) if t0 else None,
            "tool_calls": n_tool_calls, "approx": self.approx,
        })
        used, _ = device_vram_mb()
        self.peak_vram = max(self.peak_vram, used)

    def on_llm_error(self, error, *, run_id=None, **kwargs) -> None:  # noqa: D102
        key = str(run_id)
        self._prompt.pop(key, None)
        t0 = self._t0.pop(key, None)
        self.rows.append({"case_id": self.case_id, "role": "error", "prompt_tokens": 0,
                          "completion_tokens": 0, "prompt_chars": 0, "completion_chars": 0,
                          "seconds": round(time.perf_counter() - t0, 3) if t0 else None,
                          "tool_calls": 0, "error": str(error)[:200], "approx": self.approx})

    # -- llamadas a herramientas ---------------------------------------------

    def on_tool_start(self, serialized, input_str, *, run_id=None, **kwargs) -> None:  # noqa: D102
        self._tool_t0[str(run_id)] = time.perf_counter()
        self._tool_name[str(run_id)] = (serialized or {}).get("name") or kwargs.get("name") or "?"

    def on_tool_end(self, output, *, run_id=None, **kwargs) -> None:  # noqa: D102
        key = str(run_id)
        t0 = self._tool_t0.pop(key, None)
        name = self._tool_name.pop(key, "?")
        text = output if isinstance(output, str) else str(getattr(output, "content", output))
        self.tools.append({"case_id": self.case_id, "tool": name,
                           "seconds": round(time.perf_counter() - t0, 3) if t0 else None,
                           "chars": len(text or ""), "tokens": self._count(text or "")})

    def on_tool_error(self, error, *, run_id=None, **kwargs) -> None:  # noqa: D102
        key = str(run_id)
        t0 = self._tool_t0.pop(key, None)
        name = self._tool_name.pop(key, "?")
        self.tools.append({"case_id": self.case_id, "tool": name,
                           "seconds": round(time.perf_counter() - t0, 3) if t0 else None,
                           "chars": 0, "tokens": 0, "error": str(error)[:200]})

    # -- resumen -------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        by_role: dict[str, dict[str, float]] = defaultdict(lambda: {"calls": 0, "in": 0, "out": 0, "s": 0.0})
        for r in self.rows:
            b = by_role[r["role"]]
            b["calls"] += 1
            b["in"] += r["prompt_tokens"]
            b["out"] += r["completion_tokens"]
            b["s"] += r["seconds"] or 0.0
        return {
            "llm_calls": len(self.rows),
            "prompt_tokens": sum(r["prompt_tokens"] for r in self.rows),
            "completion_tokens": sum(r["completion_tokens"] for r in self.rows),
            "llm_seconds": round(sum(r["seconds"] or 0.0 for r in self.rows), 2),
            "tool_calls": len(self.tools),
            "tool_seconds": round(sum(t["seconds"] or 0.0 for t in self.tools), 2),
            "tools_used": sorted({t["tool"] for t in self.tools}),
            "by_role": {k: {"calls": v["calls"], "prompt_tokens": int(v["in"]),
                            "completion_tokens": int(v["out"]), "seconds": round(v["s"], 2)}
                        for k, v in sorted(by_role.items())},
            "peak_vram_mb": round(self.peak_vram, 1),
            "host_rss_mb": round(host_rss_mb(), 1),
            "tokens_approx": self.approx,
        }
