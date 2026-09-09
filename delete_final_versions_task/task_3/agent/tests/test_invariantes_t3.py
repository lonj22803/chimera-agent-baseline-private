"""Las invariantes de diseño de la tarea 3, fijadas para que no se pierdan.

Tres cosas que el plan exige y que son fáciles de romper sin darse cuenta:

1. El mapa monótono riesgo→meses no puede dañar el c-index. Es la separación en
   dos etapas sobre la que se apoya toda la tarea: primero se ajusta el ORDEN
   (ranking_score), después la MAGNITUD (time_score), y la segunda no toca a la
   primera porque el c-index sólo compara pares.
2. La nota tiene que explicar la semántica de censura. Sin ella el número y la
   prosa se contradicen, y ésa es la causa raíz de los abortos del baseline: el
   modelo se negaba a decir cuándo ocurriría algo que la pregunta mal planteada
   le hacía esperar.
3. La guardia ganglionar sólo debe disparar cuando hay contradicción real.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from delete_final_versions_task.task_3.agent import decide

ART = Path(__file__).resolve().parents[2] / "experts_3" / "train" / "artifacts"


def _report(name: str) -> dict:
    return json.loads((ART / f"expert_{name}_report.json").read_text())


@pytest.mark.skipif(not ART.exists(), reason="faltan los artefactos de experts_3")
def test_el_mapa_monotono_no_danha_el_c_index():
    """El c-index del orden de riesgo y el de los meses son EL MISMO número."""
    orden = _report("one")["metrics"]["c_index"]
    meses = _report("five")["metrics"]["c_index"]
    assert orden == meses, (
        "el mapa riesgo->meses dejó de ser monótono: el c-index cambió de "
        f"{orden} a {meses}. La separación en dos etapas ya no se sostiene.")


@pytest.mark.skipif(not ART.exists(), reason="faltan los artefactos de experts_3")
def test_la_cohorte_medida_son_75_casos():
    assert len(_report("five")["case_ids"]) == 75


def test_la_nota_declara_la_semantica_de_censura():
    """Sin evento: 'seguimiento esperado', nunca 'fecha de recurrencia conocida'."""
    nota = "A" * 60
    unc = {"interval_months": [10.0, 30.0]}

    censurado = decide.finish("T3-x", {"months_to_recurrence": 20.0, "event": 0}, nota, unc)
    assert "expected follow-up without an event" in censurado["reasoning"]
    assert "not a known recurrence date" in censurado["reasoning"]

    con_evento = decide.finish("T3-y", {"months_to_recurrence": 20.0, "event": 1}, nota, unc)
    assert "predicted recurrence horizon" in con_evento["reasoning"]
    assert "not evidence of observed recurrence" in con_evento["reasoning"]


def test_la_banda_se_declara_no_validada():
    """La sensibilidad no puede presentarse como intervalo con cobertura."""
    nota = "A" * 60
    out = decide.finish("T3-z", {"months_to_recurrence": 20.0, "event": 0}, nota,
                        {"interval_months": [10.0, 30.0]})
    assert "coverage has not been validated" in out["reasoning"]


def test_finish_rechaza_un_numero_invalido():
    nota = "A" * 60
    unc = {"interval_months": [0.0, 1.0]}
    for malo in ({"months_to_recurrence": float("nan"), "event": 0},
                 {"months_to_recurrence": -1.0, "event": 0},
                 {"months_to_recurrence": 5.0, "event": 2}):
        with pytest.raises(ValueError):
            decide.finish("T3-bad", malo, nota, unc)


def test_la_guardia_ganglionar_solo_dispara_en_contradiccion():
    nota = "No lymph nodes were sampled, so nodal status is unknown."
    # ln_unknown == 0: los ganglios SI se muestrearon -> la frase se contradice.
    con = decide.note_issues(nota, "", "", {"ln_unknown": 0})
    assert "nodal_contradiction" in con
    # ln_unknown == 1: no se muestrearon -> la misma frase es correcta.
    sin = decide.note_issues(nota, "", "", {"ln_unknown": 1})
    assert "nodal_contradiction" not in sin
    # Sin findings tampoco debe inventarse una contradicción.
    assert "nodal_contradiction" not in decide.note_issues(nota, "", "", None)


def test_to_gc_outputs_devuelve_el_reasoning_como_cadena_suelta():
    """El gemelo -reasoning.json es UNA CADENA, no un objeto. Contrato del reto."""
    payload = {"case_id": "T3-1", "task": 3, "months_to_recurrence": 12.5,
               "reasoning": "B" * 60}
    out = decide.to_gc_outputs(payload, 0)
    assert isinstance(out[decide.REASONING], str)
    assert out[decide.DECISION] == {"event": 0, "months_to_recurrence": 12.5}
