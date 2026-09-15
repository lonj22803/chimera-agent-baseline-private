"""Intervención 5 — la biblioteca de casos: razonamiento basado en precedentes.

Un urólogo que ve un caso nuevo no lo resuelve desde cero: lo compara con los
que ya ha visto. Esto es razonamiento basado en casos (Aamodt y Plaza, *AI
Communications* 1994; Kolodner 1993), y aquí se hace de forma literal: la
biblioteca son los 91 casos etiquetados del reto, y para cada paciente nuevo se
recuperan los ``k`` más parecidos **dentro de su mismo cubo de biopsia previa**
—porque la tarea son tres problemas, no uno— con la decisión que el urólogo
lector tomó en cada uno, su confianza, su traza y sus palabras.

Dos cosas hay que decir de frente:

* **Cuando el caso que se está decidiendo está en la biblioteca, el precedente
  más cercano es él mismo** (distancia 0). Eso ocurre exactamente en los 91
  casos etiquetados, y sólo en ellos: en el test del reto no puede ocurrir. En
  esa situación el experto lo declara en el acta (``self_match``) y la nota
  que sale de ahí es memorización, no rendimiento. El modo ``honest`` excluye
  el propio caso (leave-one-out) y da la cifra de generalización.
* **Fuera de muestra este experto vale lo que vale la distancia estructurada**:
  medido en leave-one-out, k=3 acierta 0.92 sin biopsia previa y 0.78 tras una
  negativa —donde el criterio de cohorte ya es mejor— y **0.47 con biopsia
  positiva**, es decir, nada. Por eso su peso en el protocolo, fuera del caso
  idéntico, es pequeño y está escrito.

La distancia es euclídea sobre siete variables del panel, estandarizadas sobre
la serie etiquetada y ponderadas (PI-RADS y PSA mandan). Sólo variables del
``structured-prompt.json``: nada que viva en un documento sin abrir.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from delete_final_versions_task_V1_1.common import vocab as V

FEATURES = ("pirads", "log_psa", "log_psad", "log_vol", "age", "dre", "cspca")
WEIGHTS = np.array([1.5, 1.0, 1.0, 0.5, 1.0, 0.7, 0.5])
VARIABLES = ["bx", "fh", "age", "dre", "psa", "vol", "psad", "cspca", "pirads", "comorbidity"]
SECTIONS = ["radiology_report", "psa_trend", "laboratory_results", "previous_notes", "family_history"]


def _num(x: Any) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def _log(x: float) -> float:
    return math.log(x) if x == x and x > 0 else float("nan")


def features(payload: dict[str, Any]) -> np.ndarray:
    dre = str(payload.get("dre") or "").strip().lower()
    dre_s = float("nan") if dre in ("", "not done", "none", "nan", "unknown") else (0.0 if dre == "normal" else 1.0)
    return np.array([_num(payload.get("pirads")), _log(_num(payload.get("psa"))),
                     _log(_num(payload.get("psad"))), _log(_num(payload.get("vol"))),
                     _num(payload.get("age")), dre_s, _num(payload.get("cspca"))], dtype=float)


class ProfessionalExperience:
    """Los casos etiquetados, indexados para recuperación por cubo."""

    def __init__(self, data_root: Path, exclude_self: bool = True, k: int = 3, eps: float = 0.05) -> None:
        self.exclude_self = exclude_self
        self.k = k
        self.eps = eps
        self.items: list[dict[str, Any]] = []
        gt_root = Path(data_root) / "ground_truth"
        in_root = Path(data_root) / "agent_input"
        for d in sorted(p for p in gt_root.iterdir() if p.is_dir()):
            dec = d / "prostate-biopsy-decision.json"
            rea = d / "prostate-biopsy-decision-reasoning.json"
            pr = in_root / d.name / "structured-prompt.json"
            if not (dec.exists() and rea.exists() and pr.exists()):
                continue
            payload = json.loads(pr.read_text())
            reasoning = json.loads(rea.read_text())
            self.items.append({
                "case_id": d.name, "decision": json.loads(dec.read_text()),
                "confidence": reasoning.get("confidence"),
                "variable_weights": reasoning.get("variable_weights") or {},
                "reveal_sequence": reasoning.get("reveal_sequence") or [],
                "free_text": reasoning.get("free_text") or "",
                "bx": str(payload.get("bx") or "None"), "pirads": payload.get("pirads"),
                "psa": payload.get("psa"), "psad": payload.get("psad"), "age": payload.get("age"),
                "dre": payload.get("dre"), "x": features(payload),
            })
        X = np.array([it["x"] for it in self.items])
        self.mu = np.nanmean(X, axis=0)
        self.sd = np.where(np.nanstd(X, axis=0) > 1e-9, np.nanstd(X, axis=0), 1.0)
        for it in self.items:
            it["z"] = self._z(it["x"])

    def _z(self, x: np.ndarray) -> np.ndarray:
        z = (x - self.mu) / self.sd
        return np.where(np.isnan(z), 0.0, z)

    def recall(self, case_id: str, payload: dict[str, Any], k: int | None = None) -> dict[str, Any]:
        k = k or self.k
        bx = str(payload.get("bx") or "None")
        z = self._z(features(payload))
        pool = [it for it in self.items if it["bx"] == bx and not (self.exclude_self and it["case_id"] == case_id)]
        if not pool:
            pool = [it for it in self.items if not (self.exclude_self and it["case_id"] == case_id)]
        dist = np.sqrt((((np.array([it["z"] for it in pool]) - z) * WEIGHTS) ** 2).sum(axis=1))
        order = np.argsort(dist)[:k]
        neigh = []
        votes: Counter = Counter()
        conf: Counter = Counter()
        wsum = 0.0
        for o in order:
            it = pool[o]
            w = 1.0 / (float(dist[o]) + self.eps)
            wsum += w
            votes[it["decision"]] += w
            conf[it["confidence"]] += w
            neigh.append({**{kk: it[kk] for kk in ("case_id", "decision", "confidence", "variable_weights",
                                                    "reveal_sequence", "free_text", "bx", "pirads", "psa",
                                                    "psad", "age", "dre")},
                          "distance": round(float(dist[o]), 3), "weight": round(w, 3)})
        self_match = bool(neigh) and neigh[0]["case_id"] == case_id and neigh[0]["distance"] < 1e-6
        p_yes = votes["yes"] / wsum if wsum else 0.5
        # pesos y revelaciones: voto ponderado por variable / sección
        weights = {}
        for v in VARIABLES:
            c: Counter = Counter()
            for n in neigh:
                if n["variable_weights"].get(v):
                    c[n["variable_weights"][v]] += n["weight"]
            weights[v] = c.most_common(1)[0][0] if c else "noted"
        reveal = []
        for s in SECTIONS:
            w_open = sum(n["weight"] for n in neigh if s in n["reveal_sequence"])
            if wsum and w_open / wsum >= 0.5:
                reveal.append(s)
        return {
            "bucket": bx, "k": len(neigh), "pool": len(pool), "self_match": self_match,
            "answer": "yes" if p_yes >= 0.5 else "no", "p_yes": round(p_yes, 4),
            "confidence": conf.most_common(1)[0][0] if conf else "clear",
            "variable_weights": weights, "reveal_sequence": reveal, "neighbours": neigh,
            "exclude_self": self.exclude_self,
        }

    def bucket_mode(self, bx: str, exclude: str | None = None) -> dict[str, Any]:
        """Moda por cubo de la traza del urólogo: el suelo del modo honesto."""
        pool = [it for it in self.items if it["bx"] == bx and it["case_id"] != exclude] or \
               [it for it in self.items if it["case_id"] != exclude]
        weights = {v: Counter(it["variable_weights"].get(v) for it in pool if it["variable_weights"].get(v)).most_common(1)[0][0]
                   for v in VARIABLES}
        conf = Counter(it["confidence"] for it in pool).most_common(1)[0][0]
        rates = {s: sum(1 for it in pool if s in it["reveal_sequence"]) / len(pool) for s in SECTIONS}
        return {"variable_weights": weights, "confidence": conf, "section_rates": rates, "n": len(pool)}


def _short(text: str, n: int = 170) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


#: Cómo pesa la distancia cada variable del panel, en el vocabulario del formulario.
DISTANCE_WEIGHTS: dict[str, str] = {"pirads": "important", "psa": "noted", "psad": "noted", "age": "noted",
                                    "dre": "noted", "vol": "noted", "cspca": "noted", "bx": "decisive",
                                    "fh": "not_used", "comorbidity": "not_used"}


def render(result: dict[str, Any], payload: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    neigh = result["neighbours"]
    # Dos cosas distintas que la sala debe ver por separado: con qué variables
    # se buscó el precedente (la distancia, fija), y qué pesó el urólogo en los
    # precedentes que salieron (su traza, por mayoría ponderada) — que es la
    # lectura clínica de hombres parecidos, y por eso es la que se declara.
    loo = {"None": 0.92, "Negative": 0.78, "Positive": 0.47}.get(result["bucket"])
    margin = abs(result["p_yes"] - 0.5) * 2
    if result["self_match"]:
        conf, why = "clear", "the nearest precedent is this very patient"
    elif loo is not None and loo >= 0.85 and margin >= 0.5:
        conf, why = "clear", f"the precedents agree ({result['p_yes']:.2f}) and the library is right {loo:.0%} of the time in this situation out of fold"
    elif loo is not None and loo >= 0.7:
        conf, why = "borderline", f"the library is right {loo:.0%} of the time in this situation out of fold"
    else:
        conf, why = "uncertain", f"in this situation the library is no better than chance ({loo:.0%} out of fold)" if loo else "unvalidated situation"
    block = V.variable_block(result["variable_weights"], V.case_values(payload or {}), conf, why,
                             heading="WHAT THE READING UROLOGIST WEIGHED IN THESE PRECEDENTS",
                             scope=f"weighted majority of the {result['k']} nearest labelled traces; the distance itself is on {', '.join(V.LABEL[v] for v, l in DISTANCE_WEIGHTS.items() if l in ('decisive', 'important'))} first")
    lines = [f"I recall {result['pool']} men I have seen in this same situation ({result['bucket']} "
             f"prior biopsy). The {result['k']} most similar patients, and what the reading urologist did:"]
    for i, n in enumerate(neigh, 1):
        tag = " — IDENTICAL PANEL: this is the same case, already in the labelled series" if (
            i == 1 and result["self_match"]) else ""
        lines.append(f"  {i}. distance {n['distance']:.2f}{tag}: PI-RADS {n['pirads']}, PSA {n['psa']}, "
                     f"PSAD {n['psad']}, age {n['age']}, DRE {n['dre']} -> "
                     f"{'BIOPSY' if n['decision'] == 'yes' else 'DEFER'} ({n['confidence']}). "
                     f"He wrote: \"{_short(n['free_text'])}\"")
    verdict = "BIOPSY" if result["answer"] == "yes" else "DEFER"
    lines.append("")
    if result["self_match"]:
        lines.append(f"PRECEDENT: {verdict}. The nearest precedent is this very patient, so the library "
                     "returns what the reading urologist actually did with him. That is a record, not a "
                     "judgement; out of sample this expert is worth only what the distance is worth.")
    else:
        strength = {"None": "strong here (0.92 leave-one-out)", "Negative": "fair here (0.78 leave-one-out)",
                    "Positive": "no better than chance here (0.47 leave-one-out): read the precedents for how "
                                "this urologist reasons, not for the answer"}.get(result["bucket"], "unvalidated here")
        lines.append(f"PRECEDENT: {verdict} (weighted vote {result['p_yes']:.2f} for biopsy). Distance-weighted "
                     f"precedent is {strength}.")
    lines.append("")
    lines.append("What my professional experience contributes: it shows what this urologist looks at and how he phrases the "
                 "call. These memories do not establish facts about this patient. Nobody may cite a precedent's grade, PSA "
                 "or MRI as if it were his.")
    lines.append("")
    lines.append(block)
    body = "\n".join(lines)
    data = {**result, "confidence": conf,
            "gist": (f"library precedent {verdict} (p={result['p_yes']:.2f}"
                     + (", identical panel in the series" if result["self_match"] else "") + f"; {conf})")}
    return body, data
