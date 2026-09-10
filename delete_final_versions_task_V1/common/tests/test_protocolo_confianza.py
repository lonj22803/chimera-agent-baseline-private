"""El validador dual de evidencia de confianza.

El paso 1.4 sustituye el LOO exacto (medido en 169,83 h) por CV anidada
declarada. Lo que se relaja es la IGUALDAD de conjuntos; lo que NO se relaja es
la ausencia de fuga. Estos tests fijan esa frontera: si alguien "arregla" el
validador aflojando una comprobación de fuga, falla aquí.
"""
from __future__ import annotations

import pytest

from delete_final_versions_task_V1.common.analysis.measure_forms import _check_evidence

IDS = {f"c{i}" for i in range(10)}
BUDGET = {"model": 0.1, "missing": 0.0, "panel": 0.0, "aleatoric": 0.2}


def _cal(case_id, train):
    return {"case_id": case_id, "decision": "yes", "rung": "r1", "budget": BUDGET,
            "training_case_ids": sorted(train)}


def _row(case_id, train, calibration, protocol="nested_stratified_cv_10x9"):
    return {"case_id": case_id, "decision": "yes", "rung": "r1", "agreement": "clear",
            "budget": BUDGET, "training_case_ids": sorted(train), "protocol": protocol,
            "provenance": "test", "calibration": calibration}


def _valido():
    """Un pliegue honesto: c0 fuera, entrena con 8 de los otros 9."""
    train = sorted(IDS - {"c0", "c9"})
    cal = [_cal(c, [x for x in train if x != c]) for c in train[:4]]
    return [_row("c0", train, cal)]


def test_un_pliegue_honesto_pasa():
    _check_evidence(_valido(), IDS)


def test_rechaza_sin_protocolo_declarado():
    row = _valido()[0]
    del row["protocol"]
    with pytest.raises(ValueError, match="protocolo"):
        _check_evidence([row], IDS)


def test_rechaza_protocolo_desconocido():
    row = _valido()[0]
    row["protocol"] = "loo_de_mentira"
    with pytest.raises(ValueError, match="protocolo"):
        _check_evidence([row], IDS)


def test_rechaza_que_el_caso_se_vea_a_si_mismo():
    row = _valido()[0]
    row["training_case_ids"] = sorted(set(row["training_case_ids"]) | {"c0"})
    with pytest.raises(ValueError, match="se ve a si mismo"):
        _check_evidence([row], IDS)


def test_rechaza_fuga_del_caso_exterior_en_la_calibracion():
    """El requisito explícito del plan: la fuga sigue prohibida en 10x9."""
    row = _valido()[0]
    row["calibration"][0]["training_case_ids"] = sorted(
        set(row["calibration"][0]["training_case_ids"]) | {"c0"})
    with pytest.raises(ValueError, match="fuga del caso exterior"):
        _check_evidence([row], IDS)


def test_rechaza_que_el_caso_interior_se_vea_a_si_mismo():
    row = _valido()[0]
    inner = row["calibration"][0]
    inner["training_case_ids"] = sorted(set(inner["training_case_ids"]) | {inner["case_id"]})
    with pytest.raises(ValueError, match="se ve a si mismo"):
        _check_evidence([row], IDS)


def test_rechaza_un_pliegue_degenerado():
    """Entrenar con dos casos y llamarlo pliegue no cuela."""
    row = _row("c0", ["c1", "c2"], [_cal("c1", ["c2"])])
    with pytest.raises(ValueError, match="degenerado"):
        _check_evidence([row], IDS)


def test_rechaza_calibracion_vacia():
    row = _row("c0", sorted(IDS - {"c0", "c9"}), [])
    with pytest.raises(ValueError, match="sin calibración"):
        _check_evidence([row], IDS)


def test_loo_estricto_sigue_exigiendo_igualdad_de_conjuntos():
    """La rama antigua no se ha aflojado: un pliegue no pasa por LOO."""
    row = _row("c0", sorted(IDS - {"c0", "c9"}),
               [_cal("c1", sorted(IDS - {"c0", "c1"}))], protocol="loo_estricto")
    with pytest.raises(ValueError, match="LOO estricto"):
        _check_evidence([row], IDS)


def test_loo_estricto_bien_formado_pasa():
    train = sorted(IDS - {"c0"})
    cal = [_cal(c, sorted(IDS - {"c0", c})) for c in train]
    _check_evidence([_row("c0", train, cal, protocol="loo_estricto")], IDS)
