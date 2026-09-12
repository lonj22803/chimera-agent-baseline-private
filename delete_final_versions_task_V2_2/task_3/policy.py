"""Sustituye el percentil empírico de T3 por la CDF suave. Nada más.

Se reimplementa la rama desplegada de `Panel.horizon` porque el percentil se
calcula **dentro** del método y no hay dónde engancharse sin duplicar esas
líneas. Se copian tal cual salvo una: la del percentil.

Lo que NO cambia: el portavoz, los expertos, `a`, `b`, `risk_scale`, la política
de evento y el contrato de salida. Sólo desaparecen los empates.
"""
from __future__ import annotations

import numpy as np

from .export import ExportadorSuave


def aplicar() -> None:
    """Parchea `Panel.horizon` en el módulo real de la V1.1."""
    from delete_final_versions_task_V1_1.task_3.agent import protocol as P
    from delete_final_versions_task_V1_1.common.chimera_experts import dataset_task3 as ds

    if getattr(P.Panel.horizon, "_v2_2", False):
        return
    original = P.Panel.horizon
    suave = ExportadorSuave()

    def horizon(self, case, risk):
        salida = original(self, case, risk)
        # Sólo la rama desplegada con portavoz seleccionado usa el percentil
        # empírico; el resto (oof, respaldos) se deja intacto.
        if self.selected is None or self.mode == "oof":
            return salida
        seleccion = self.selected["final_selection"]
        if seleccion["family"] == "CAPRA-S":
            raw = -risk
        else:
            bloques = "S" if seleccion["family"] == "S+anchor" else "ASGDE"
            matriz, nombres = ds.build_matrix([case], bloques, drop_constant=False)
            matriz = matriz[:, [nombres.index(n) for n in self.selected_model.names]]
            raw = -float(self.selected_model.risk(matriz)[0])
        meses = suave.meses(raw)
        cal = dict(salida.get("calibration") or {})
        cal.update({
            "percentile": suave.percentil(raw),
            "months_map": "90 exp(-0.1 * 12 * (1 - CDF_normal_train(raw)))",
            "exportador": suave.version,
            "sustituye": "percentil por CDF empírica de 75 valores",
            "meses_cdf_empirica": float(salida["months_to_recurrence"]),
            "nota": ("El orden del riesgo se conserva exactamente: la CDF normal es "
                     "estrictamente creciente. a, b y risk_scale no se reajustan, "
                     "así que el rango de salida es el de V1."),
        })
        return {**salida, "months_to_recurrence": float(meses), "calibration": cal}

    horizon._v2_2 = True
    P.Panel.horizon = horizon
