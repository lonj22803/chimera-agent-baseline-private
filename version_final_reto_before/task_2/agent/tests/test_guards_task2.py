"""La guardia de lenguaje de proceso, verificada contra la prosa real del urólogo.

El plan (paso 4.2) exige que la lista curada en la tarea 1 no se copie a ciegas:
hay que medirla contra los 72 ``free_text`` de la tarea 2 y exigir **0 falsos
positivos** antes de activarla. Este test fija esa medida: si alguien añade un
patrón que empieza a marcar la prosa legítima del urólogo, falla aquí y no en
las notas entregadas.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from version_final_reto.common import guards
from version_final_reto.task_2.agent import decide

GT = Path(__file__).resolve().parents[4] / "data" / "task2" / "ground_truth"
REASONING = "prostate-treatment-decision-reasoning.json"


def _free_texts() -> list[tuple[str, str]]:
    out = []
    for d in sorted(p for p in GT.iterdir() if p.is_dir()):
        f = d / REASONING
        if not f.exists():
            continue
        data = json.loads(f.read_text())
        text = data if isinstance(data, str) else (
            data.get("free_text") or data.get("reasoning") or json.dumps(data))
        out.append((d.name, str(text)))
    return out


@pytest.mark.skipif(not GT.exists(), reason="los datos de task2 no están disponibles")
def test_process_language_no_dispara_en_la_prosa_del_urologo():
    """0 falsos positivos sobre los 72 textos reales: el requisito del plan."""
    texts = _free_texts()
    assert len(texts) == 72, f"se esperaban 72 free_text, hay {len(texts)}"
    offenders = {cid: hits for cid, text in texts if (hits := guards.process_language(text))}
    assert not offenders, (
        "la guardia marca prosa legítima del urólogo como lenguaje de proceso: "
        f"{dict(list(offenders.items())[:5])}")


@pytest.mark.skipif(not GT.exists(), reason="los datos de task2 no están disponibles")
def test_ningun_free_text_esta_vacio():
    """Si un texto llega vacío, el test anterior pasaría por vacuidad."""
    assert all(text.strip() for _, text in _free_texts())


def test_la_guardia_si_marca_lenguaje_de_proceso_real():
    """La contraparte: que no pase por no detectar nada nunca."""
    assert guards.process_language("The panel reached consensus on this case.")
    assert guards.process_language("The evidence converged and carried the decision.")


def test_decide_reexporta_la_misma_guardia():
    """task_2/decide.py la reexporta; que no se bifurque en una copia distinta."""
    assert decide.process_language is guards.process_language
