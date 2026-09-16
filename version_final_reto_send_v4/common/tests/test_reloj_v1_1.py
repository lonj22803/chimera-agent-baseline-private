"""Las cuatro piezas de la V1.1: solape, un hilo por bosque, aplazado y reloj.

Lo que se comprueba aquí es lo que tiene que seguir siendo verdad para que la
V1.1 no cambie ninguna salida: que un precalentamiento que falla no se propaga,
que el reloj nunca bloquea al presidente, y que la variante aplazada se calcula
una sola vez y sólo si alguien la lee.
"""
from __future__ import annotations

import asyncio
import os
import threading
import time

import pytest

from version_final_reto.common import deadline, serial_predict, warmup


# --- warmup ----------------------------------------------------------------

def test_warmup_devuelve_lo_que_calculo_el_hilo():
    warmup.reset()
    warmup.submit("k", lambda: "del hilo")
    assert warmup.result("k", lambda: "en linea") == "del hilo"


def test_warmup_sin_hilo_construye_en_linea():
    warmup.reset()
    assert warmup.result("nunca-lanzado", lambda: "en linea") == "en linea"


def test_warmup_no_propaga_el_fallo_del_hilo():
    """Perder el solape es más lento; perder el caso, no es una opción."""
    warmup.reset()

    def explota():
        raise RuntimeError("sklearn se atragantó")

    warmup.submit("malo", explota)
    assert warmup.result("malo", lambda: "reconstruido") == "reconstruido"


def test_warmup_no_relanza_la_misma_clave():
    warmup.reset()
    veces = []
    warmup.submit("una", lambda: veces.append(1))
    warmup.submit("una", lambda: veces.append(1))
    warmup.result("una", lambda: None)
    assert len(veces) == 1


def test_warmup_usa_hilos_demonio():
    """Si no fueran demonios, el intérprete los esperaría al salir y un caso
    cortado por el reloj colgaría el proceso **después** de escribir la salida."""
    warmup.reset()
    visto = {}
    warmup.submit("d", lambda: visto.setdefault("daemon", threading.current_thread().daemon))
    warmup.result("d", lambda: None)
    assert visto["daemon"] is True


def test_aresult_no_bloquea_el_bucle():
    """El reloj tiene que poder disparar mientras se espera al hilo."""
    warmup.reset()

    async def main():
        warmup.submit("lento", lambda: (time.sleep(0.3), "hecho")[1])
        marcas = []

        async def latido():
            for _ in range(5):
                marcas.append(time.monotonic())
                await asyncio.sleep(0.02)

        tarea = asyncio.create_task(latido())
        valor = await warmup.aresult("lento", lambda: "en linea")
        await tarea
        return valor, marcas

    valor, marcas = asyncio.run(main())
    assert valor == "hecho"
    assert len(marcas) == 5  # el bucle siguió latiendo


# --- deadline --------------------------------------------------------------

def test_reloj_desactivado_permite_todo(monkeypatch):
    monkeypatch.setenv("CHIMERA_CASE_BUDGET_SECONDS", "0")
    deadline.start()
    assert deadline.remaining() == float("inf")
    assert deadline.allows("pass") and deadline.allows("nudge")
    assert deadline.summary() == {"budget_seconds": 0}


def test_reloj_con_holgura_permite_todo(monkeypatch):
    monkeypatch.setenv("CHIMERA_CASE_BUDGET_SECONDS", "780")
    deadline.start()
    assert deadline.allows("nudge") and deadline.allows("pass")
    assert deadline.summary()["budget_skipped"] is None


def test_reloj_apretado_suelta_lo_opcional_pero_nunca_al_presidente(monkeypatch):
    monkeypatch.setenv("CHIMERA_CASE_BUDGET_SECONDS", "100")
    deadline.start()
    assert deadline.allows("pass") is False      # 100 - 90 - 150 < 0
    assert deadline.allows("nudge") is False     # 100 - 90 - 30  < 0
    assert deadline.allows("chair") is True      # sin nota no hay entrega
    soltado = deadline.summary()["budget_skipped"]
    assert soltado == {"pass": 1, "nudge": 1}


def test_reloj_suelta_el_pase_antes_que_el_empujon(monkeypatch):
    """Un pase son cuatro llamadas; un empujón, una. El orden importa."""
    monkeypatch.setenv("CHIMERA_CASE_BUDGET_SECONDS", "200")
    deadline.start()
    assert deadline.allows("pass") is False      # 200 - 90 - 150 < 0
    assert deadline.allows("nudge") is True      # 200 - 90 - 30 > 0 y no fuerza cierre
    assert deadline.must_close() is False


def test_cierre_forzado_cuando_solo_caben_verificador_y_presidente(monkeypatch):
    """A 150 s ya no cabe deliberar: tras un empujón aún faltarían verificador y presidente."""
    monkeypatch.delenv("CHIMERA_CIERRE_FORZADO_S", raising=False)
    monkeypatch.setenv("CHIMERA_CASE_BUDGET_SECONDS", "150")
    deadline.start()
    assert deadline.must_close() is True         # 150 <= 90 + 90
    assert deadline.allows("nudge") is False
    assert deadline.allows("pass") is False
    assert deadline.allows("chair") is True
    assert deadline.summary()["forced_close_at"] is not None


def test_cierre_forzado_por_instante_explicito(monkeypatch):
    monkeypatch.setenv("CHIMERA_CASE_BUDGET_SECONDS", "780")
    monkeypatch.setenv("CHIMERA_CIERRE_FORZADO_S", "0")
    deadline.start()
    assert deadline.must_close() is True
    assert deadline.allows("nudge") is False


def test_cierre_forzado_no_actua_con_holgura_ni_con_reloj_apagado(monkeypatch):
    monkeypatch.delenv("CHIMERA_CIERRE_FORZADO_S", raising=False)
    monkeypatch.setenv("CHIMERA_CASE_BUDGET_SECONDS", "780")
    deadline.start()
    assert deadline.must_close() is False
    assert deadline.summary()["forced_close_at"] is None
    monkeypatch.setenv("CHIMERA_CASE_BUDGET_SECONDS", "0")
    monkeypatch.setenv("CHIMERA_CIERRE_FORZADO_S", "0")
    deadline.start()
    assert deadline.must_close() is False        # reloj apagado: comparaciones byte a byte


def test_cierre_forzado_ignora_un_valor_invalido(monkeypatch):
    monkeypatch.setenv("CHIMERA_CASE_BUDGET_SECONDS", "780")
    monkeypatch.setenv("CHIMERA_CIERRE_FORZADO_S", "catorce")
    deadline.start()
    assert deadline.must_close() is False


# --- serial_predict --------------------------------------------------------

class _Bosque:
    def __init__(self):
        self.n_jobs = -1


class _Tubo:
    """Imita un ``Pipeline``: ``steps`` son tuplas, que es donde se esconden."""

    def __init__(self):
        self.steps = [("impute", object()), ("clf", _Bosque())]
        self.named_steps = dict(self.steps)


class _Ensemble:
    def __init__(self):
        self.members_ = [_Tubo() for _ in range(3)]
        self.n_jobs = -1


def test_serialize_alcanza_los_bosques_dentro_de_las_tuplas():
    modelo = _Ensemble()
    assert serial_predict.serialize(modelo) == 4   # el ensemble y sus tres clf
    assert modelo.n_jobs == 1
    assert all(t.named_steps["clf"].n_jobs == 1 for t in modelo.members_)


def test_serialize_es_idempotente():
    modelo = _Ensemble()
    serial_predict.serialize(modelo)
    assert serial_predict.serialize(modelo) == 0


def test_serialize_se_puede_apagar(monkeypatch):
    """El brazo de control de la verificación no puede tocar los estimadores."""
    monkeypatch.setenv("CHIMERA_SERIAL_PREDICT", "0")
    modelo = _Ensemble()
    assert serial_predict.serialize_bundles({"e": {"model": modelo}}) == 0
    assert modelo.n_jobs == -1


def test_serialize_bundles_acepta_dicts_listas_y_objetos():
    a, b = _Ensemble(), _Ensemble()
    assert serial_predict.serialize_bundles({"x": {"model": a}}) > 0
    assert serial_predict.serialize_bundles([b]) > 0


# --- la variante aplazada de la tarea 1 ------------------------------------

def test_deferred_solo_calcula_si_alguien_la_lee():
    from version_final_reto.task_1.experts_1.panel import _DeferredVerdicts

    veces = []
    v = _DeferredVerdicts({"structured": {"p": 1}, "fusion_full": {"p": 2}, "trace": {}},
                          lambda: veces.append(1) or {"p": 3})
    assert v["fusion_full"] == {"p": 2}
    assert veces == []                      # nadie pidió la cara
    assert v["fusion_nolab"] == {"p": 3}
    assert v["fusion_nolab"] == {"p": 3}
    assert len(veces) == 1                  # y se calcula una sola vez


def test_deferred_no_inventa_otras_claves():
    from version_final_reto.task_1.experts_1.panel import _DeferredVerdicts

    v = _DeferredVerdicts({"structured": {}}, lambda: {})
    with pytest.raises(KeyError):
        v["fusion_full"]


def test_deferred_materialise_da_un_dict_completo():
    from version_final_reto.task_1.experts_1.panel import _DeferredVerdicts

    v = _DeferredVerdicts({"structured": {}}, lambda: {"p": 9})
    completo = v.materialise()
    assert type(completo) is dict and completo["fusion_nolab"] == {"p": 9}


# --- el paquete viejo no puede hacer falta en tiempo de ejecución ------------

class _Bloqueo:
    """Hace desaparecer ``delete_final_versions_task_V1`` del intérprete.

    Es lo que ocurre en la imagen de la V1.1, que no lleva el árbol de la V1.
    Aquí sí está —en el repo y en la imagen de la V1, donde montábamos el
    código— y por eso el fallo de la tarea 3 no se vio hasta correr la imagen
    de entrega: un pickle del portavoz guardaba la ruta completa del paquete de
    entonces y nadie la traducía.
    """

    VIEJO = "delete_final_versions_task_V1"

    def find_module(self, name, path=None):      # pragma: no cover - API vieja
        return self.find_spec(name, path)

    def find_spec(self, name, path=None, target=None):
        if name == self.VIEJO or name.startswith(self.VIEJO + "."):
            # ``ModuleNotFoundError`` y no ``ImportError``: es el error exacto que
            # dio la imagen de entrega, y así la prueba reproduce el fallo real.
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        return None


def test_la_tarea_3_carga_sus_artefactos_sin_el_paquete_viejo():
    import sys

    bloqueo = _Bloqueo()
    guardados = {k: v for k, v in sys.modules.items()
                 if k == bloqueo.VIEJO or k.startswith(bloqueo.VIEJO + ".")}
    for k in guardados:
        del sys.modules[k]
    sys.meta_path.insert(0, bloqueo)
    try:
        import pickle
        from pathlib import Path as _Path

        from version_final_reto.task_3.agent.protocol import EXPERTS, Panel

        # Primero, que el bloqueo muerde de verdad y que este pickle lo necesita:
        # con el desempaquetador estándar tiene que reventar, o la prueba no mide nada.
        artefacto = _Path(EXPERTS) / "train/artifacts/spokesperson_candidate.joblib"
        with pytest.raises(ModuleNotFoundError):
            pickle.loads(artefacto.read_bytes())

        # Y ahora, que el nuestro lo traduce.
        panel = Panel("deployed")
        assert panel.selected_model is not None
        assert type(panel.selected_model).__name__ == "CoxPipeline"
    finally:
        sys.meta_path.remove(bloqueo)
        sys.modules.update(guardados)


def test_ningun_artefacto_mas_pide_el_paquete_viejo():
    """Un `grep` sobre los binarios: el pickle del portavoz era el único."""
    from pathlib import Path
    import re

    raiz = Path(__file__).resolve().parents[2]
    patron = re.compile(rb"delete_final_versions_task_V1[^_]")
    culpables = []
    for f in raiz.rglob("*"):
        if not f.is_file() or "__pycache__" in f.parts:
            continue
        # `.json` fuera: los informes de E00 y la auditoría citan las rutas
        # históricas de V1 como **procedencia de datos**, no como clase de un
        # pickle. Lo que esta guardia persigue es un artefacto binario que pida
        # un módulo inexistente y mande la tarea al respaldo; un JSON que
        # documenta de dónde salió una cifra no hace eso.
        if (f.suffix in (".md", ".log", ".py", ".json")
                or "gc_profile_" in str(f) or "verification" in f.parts):
            continue
        if patron.search(f.read_bytes()):
            culpables.append(str(f.relative_to(raiz)))
    assert culpables == ["task_3/experts_3/train/artifacts/spokesperson_candidate.joblib"], culpables
