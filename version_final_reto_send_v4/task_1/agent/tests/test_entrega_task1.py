"""Las constantes y guardias de la tarea 1 entregada, fijadas.

La tarea 1 está cerrada en 0,8390 y **no tenía ni un test propio**. Estos fijan
lo que, si alguien lo cambia sin volver a medir, mueve la nota en silencio: las
constantes del protocolo (cada una elegida con el evaluador oficial sobre los 91)
y las guardias que impiden que la nota entregada invente.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from version_final_reto.common.vocab import VARIABLES_BY_TASK
VARIABLES = VARIABLES_BY_TASK[1]

from version_final_reto.common import guards
from version_final_reto.task_1.agent import decide, protocol as P

DATA = Path(__file__).resolve().parents[4] / "data" / "task1"
GT = DATA / "ground_truth"
REASONING = "prostate-biopsy-decision-reasoning.json"


# --- las constantes medidas -------------------------------------------------

def test_la_biblioteca_no_vota():
    """library_weight=0.0. Con 0.5 el ranking cae de 0.8384 a 0.8054."""
    assert P.PARAMS["library_weight"] == 0.0


def test_el_umbral_es_045():
    """Carga de la prueba. Rejilla medida: 0.8215 a 0.50, 0.8384 a 0.45, 0.8222 a 0.40."""
    assert P.PARAMS["threshold"] == 0.45


def test_la_confianza_es_la_politica_que_informa():
    """'agreement' empata en ranking con 'trace' y gana en el componente medido."""
    assert P.PARAMS["confidence_policy"] == "agreement"


def test_los_pesos_del_formulario_vienen_del_experto_de_traza():
    assert P.PARAMS["form_weights"] == "trace"


def test_la_regla_de_grado_esta_encendida():
    assert P.PARAMS["grade_rule"] is True


def test_los_tramos_de_fiabilidad_no_cambian():
    assert P.PARAMS["tier_weight"] == {"firm": 3.0, "supports": 2.0, "discuss": 1.0}


# --- las guardias sobre la prosa real del urólogo ---------------------------

def _free_texts() -> list[tuple[str, str]]:
    out = []
    for d in sorted(p for p in GT.iterdir() if p.is_dir()):
        f = d / REASONING
        if not f.exists():
            continue
        data = json.loads(f.read_text())
        text = data if isinstance(data, str) else (
            data.get("free_text") or data.get("reasoning") or "")
        if text:
            out.append((d.name, str(text)))
    return out


@pytest.mark.skipif(not GT.exists(), reason="los datos de task1 no están disponibles")
def test_process_language_no_marca_la_prosa_del_urologo():
    """La misma exigencia que en la tarea 2: 0 falsos positivos sobre lo real."""
    textos = _free_texts()
    assert textos, "no se encontró ningún free_text de referencia"
    culpables = {cid: hits for cid, t in textos if (hits := decide.process_language(t))}
    assert not culpables, f"la guardia marca prosa legítima: {dict(list(culpables.items())[:5])}"


def test_process_language_si_marca_lenguaje_de_proceso():
    """La contraparte: que no pase por no detectar nunca nada."""
    assert decide.process_language("The panel reached consensus and the evidence converged.")


# --- el contrato de salida --------------------------------------------------

def test_validate_output_acepta_una_salida_bien_formada():
    payload = {"case_id": "PT-x", "task": 1, "biopsy_decision": True,
               "confidence": "clear", "variable_weights": {**dict.fromkeys(VARIABLES, "not_used"), "psa": "important"},
               "reveal_sequence": ["psa_trend"], "reasoning": "C" * 60}
    ok, err = guards.validate_output(1, payload)
    assert ok, err


def _payload(**over):
    base = {"case_id": "PT-x", "task": 1, "biopsy_decision": True, "confidence": "clear",
            "variable_weights": {**dict.fromkeys(VARIABLES, "not_used"), }, "reveal_sequence": [], "reasoning": "C" * 60}
    return {**base, **over}


@pytest.mark.parametrize("valor", ["yes", "no", "true", "false", 1, 0])
def test_la_decision_acepta_las_formas_que_la_corrida_escribe(valor):
    """Pydantic coacciona 'yes'/'no' a booleano. Comprobado, no supuesto: el
    runner escribe la cadena y el esquema la admite, así que la salida del reto
    valida sin conversión previa."""
    ok, err = guards.validate_output(1, _payload(biopsy_decision=valor))
    assert ok, err


@pytest.mark.parametrize("valor", ["maybe", "", None, "Positive"])
def test_la_decision_rechaza_lo_que_no_es_una_respuesta(valor):
    """La coerción tiene límite: sólo las formas booleanas conocidas pasan."""
    ok, _ = guards.validate_output(1, _payload(biopsy_decision=valor))
    assert not ok


def test_validate_output_rechaza_una_seccion_inventada():
    payload = {"case_id": "PT-x", "task": 1, "biopsy_decision": True,
               "confidence": "clear", "variable_weights": {**dict.fromkeys(VARIABLES, "not_used"), },
               "reveal_sequence": ["seccion_que_no_existe"], "reasoning": "C" * 60}
    ok, _ = guards.validate_output(1, payload)
    assert not ok


# --- la extracción de grado -------------------------------------------------

def test_documented_grade_encuentra_un_gleason_escrito():
    got = decide.documented_grade("Biopsy showed Gleason 4+3 in two cores.")
    assert got.get("gg") == 3, got


def test_documented_grade_no_inventa_cuando_no_hay_nada():
    got = decide.documented_grade("No prior biopsy is recorded.")
    assert not got.get("gg")
