"""Carga de casos CHIMERA desde el layout ``data_filtered/<task>/``.

Layout esperado::

    data_filtered/task1/
      agent_input/<case_id>/structured-prompt.json
      agent_input/<case_id>/prostate-biopsy-decision-clinical-data.json
      agent_input/<case_id>/prostate-modality-level-neural-representations.json   (opcional)
      ground_truth/<case_id>/prostate-biopsy-decision.json                         (solo etiquetados)
      ground_truth/<case_id>/prostate-biopsy-decision-reasoning.json               (solo etiquetados)

Los casos sin ``ground_truth`` son válidos y se devuelven con ``label=None``: se
usan para los expertos no supervisados (proyección de PSA) y para ajustar
imputadores/escaladores sin filtrar la etiqueta.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

#: Nombre del fichero de datos clínicos por tarea.
CLINICAL_FILENAME = {
    1: "prostate-biopsy-decision-clinical-data.json",
    2: "prostate-treatment-decision-clinical-data.json",
    3: "prostate-time-to-recurrence-or-last-follow-up-clinical-data.json",
}

#: Nombre del fichero de decisión (ground truth) por tarea.
DECISION_FILENAME = {
    1: "prostate-biopsy-decision.json",
    2: "prostate-treatment-decision.json",
    3: "prostate-time-to-recurrence-or-last-follow-up.json",
}

REASONING_SUFFIX = "-reasoning.json"
FEATURES_FILENAME = "prostate-modality-level-neural-representations.json"


@dataclass
class Case:
    """Un caso completo: entradas, etiqueta (si existe) y traza del urólogo."""

    case_id: str
    task: int
    prompt: dict = field(default_factory=dict)
    clinical: dict = field(default_factory=dict)
    embeddings: dict = field(default_factory=dict)
    label: str | float | None = None
    reasoning: dict | None = None

    @property
    def has_label(self) -> bool:
        return self.label is not None

    @property
    def mri_embedding(self) -> list[float] | None:
        vecs = self.embeddings.get("MRI image") or []
        return list(vecs[0]) if vecs else None

    @property
    def available_sources(self) -> dict[str, bool]:
        """Qué fuentes de evidencia trae realmente este caso.

        Es el insumo del factor de completitud que ensancha la incertidumbre
        epistémica cuando faltan modalidades.
        """
        cl = self.clinical or {}
        return {
            "structured_prompt": bool(self.prompt),
            "radiology_report": bool(cl.get("radiology_report")),
            "psa_trend": len(cl.get("psa_trend") or []) > 0,
            "laboratory_results": len(cl.get("laboratory_results") or []) > 0,
            "previous_notes": len(cl.get("previous_notes") or []) > 0,
            "family_history": cl.get("family_history") not in (None, "", "Unknown"),
            "mri_embedding": self.mri_embedding is not None,
        }


def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def load_case(root: str | Path, case_id: str, task: int = 1) -> Case:
    """Carga un caso concreto. Los ficheros ausentes quedan vacíos, no lanzan error."""
    root = Path(root)
    ain = root / "agent_input" / case_id
    gt = root / "ground_truth" / case_id

    prompt = _read_json(ain / "structured-prompt.json") or {}
    clinical = _read_json(ain / CLINICAL_FILENAME[task]) or {}
    emb = _read_json(ain / FEATURES_FILENAME) or {}

    decision_name = DECISION_FILENAME[task]
    label = _read_json(gt / decision_name)
    reasoning = _read_json(gt / (decision_name.replace(".json", "") + REASONING_SUFFIX))

    return Case(
        case_id=case_id,
        task=task,
        prompt=prompt,
        clinical=clinical,
        embeddings={k: v for k, v in emb.items() if isinstance(v, list)},
        label=label,
        reasoning=reasoning,
    )


def load_cases(root: str | Path, task: int = 1, labelled_only: bool = False) -> list[Case]:
    """Carga todos los casos bajo ``root/agent_input`` ordenados por ``case_id``."""
    root = Path(root)
    ids = sorted(p.name for p in (root / "agent_input").iterdir() if p.is_dir())
    cases = [load_case(root, cid, task) for cid in ids]
    if labelled_only:
        cases = [c for c in cases if c.has_label]
    return cases


def binary_label(case: Case) -> int | None:
    """Etiqueta de la tarea 1 como entero: ``yes`` -> 1, ``no`` -> 0."""
    if case.label is None:
        return None
    return 1 if str(case.label).strip().lower() == "yes" else 0
