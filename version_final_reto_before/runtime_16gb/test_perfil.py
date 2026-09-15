"""El perfil de §13.1 tiene que LLEGAR al constructor, no sólo existir.

El fallo que persigue esta prueba es silencioso: alguien renombra una clave en
`resources.configure` o en `models/_load_vllm`, el perfil deja de aplicarse, el
motor vuelve a quedarse con toda la tarjeta y nada falla — hasta la entrega.
Es la misma forma de fallo que en la V1.1 tumbó la tarea 3 dentro de la imagen.

No necesita GPU.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest
from omegaconf import OmegaConf

RAIZ = Path(__file__).resolve().parents[2]
CONSTRUCTOR = RAIZ / "src" / "chimera_agent_baseline" / "models" / "__init__.py"

from version_final_reto.runtime_16gb import resources  # noqa: E402


def _cfg():
    cfg = OmegaConf.create({"generation": {"max_model_len": 32768,
                                           "gpu_memory_utilization": 0.9,
                                           "temperature": 1.0}})
    OmegaConf.set_struct(cfg, True)  # como lo entrega Hydra
    return cfg


def _es_generation(nodo) -> bool:
    return isinstance(nodo, ast.Attribute) and nodo.attr == "generation"


def _claves_que_lee_el_constructor() -> set[str]:
    """Nombres que `_load_vllm` saca de `cfg.generation`, por las tres vías.

    `.get("x")` para las opciones del motor, `cfg.generation.x` directo para lo
    que va a `SamplingParams`, y el bucle `for clave in (...)` que pasa varias
    de golpe. Si se mira sólo una de las tres, la prueba falla por vacía.
    """
    arbol = ast.parse(CONSTRUCTOR.read_text())
    claves: set[str] = set()
    for nodo in ast.walk(arbol):
        # cfg.generation.get("x", ...)
        if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == "get" and nodo.args
                and _es_generation(nodo.func.value)
                and isinstance(nodo.args[0], ast.Constant)):
            claves.add(nodo.args[0].value)
        # cfg.generation.x
        elif isinstance(nodo, ast.Attribute) and _es_generation(nodo.value):
            claves.add(nodo.attr)
        # for clave in ("a", "b", ...)
        elif isinstance(nodo, ast.For) and isinstance(nodo.iter, ast.Tuple):
            for elemento in nodo.iter.elts:
                if isinstance(elemento, ast.Constant) and isinstance(elemento.value, str):
                    claves.add(elemento.value)
    return claves


def test_el_extractor_de_claves_no_pasa_por_vacio():
    """Si el extractor dejara de ver el fichero, la prueba de abajo pasaría sola."""
    lee = _claves_que_lee_el_constructor()
    assert {"max_model_len", "gpu_memory_utilization", "temperature",
            "kv_cache_memory_bytes"} <= lee


def test_presupuesto_sigue_la_formula_del_plan():
    p = resources.presupuesto(16 * resources.GIB)
    assert p["techo_global_gib"] == 14.0        # min(14, 16-1)
    assert p["presupuesto_motor_gib"] == 12.0   # min(12, 14-2)


def test_una_tarjeta_demasiado_pequena_se_declara_no_se_disimula():
    # 12 GiB nominales dejan el motor en 9 GiB, bajo el suelo medido: el PLAN
    # pide declararlo, no rebajar la arquitectura en silencio.
    with pytest.raises(ValueError, match="suelo medido"):
        resources.presupuesto(12 * resources.GIB)


def test_configure_anade_claves_sobre_una_config_en_modo_struct(monkeypatch):
    monkeypatch.setenv("CHIMERA_SIM_VRAM_GIB", "16")
    monkeypatch.setattr(resources, "inventario",
                        lambda: {"total_bytes": 32 * resources.GIB, "libre_bytes": 0,
                                 "usada_bytes": 0, "fuente": "falso",
                                 "nombre": "prueba", "driver": "0"})
    cfg = resources.configure(_cfg())
    g = cfg.generation
    assert g.max_num_seqs == 1                     # un paciente por contenedor
    assert g.max_model_len == 32768                # el contexto NO se recorta
    assert g.kv_cache_memory_bytes == resources.GIB
    assert g.limit_mm_image == 0
    assert g.temperature == 0.0
    # 12 GiB de presupuesto sobre una tarjeta real de 32 GiB.
    assert 0.36 < g.gpu_memory_utilization < 0.39


def test_cada_clave_del_perfil_llega_al_constructor(monkeypatch):
    """La prueba que importa: sin esto el perfil sería decorativo."""
    monkeypatch.setenv("CHIMERA_SIM_VRAM_GIB", "16")
    monkeypatch.setattr(resources, "inventario",
                        lambda: {"total_bytes": 32 * resources.GIB, "libre_bytes": 0,
                                 "usada_bytes": 0, "fuente": "falso",
                                 "nombre": "prueba", "driver": "0"})
    cfg = resources.configure(_cfg())
    lee = _claves_que_lee_el_constructor()
    # `presupuesto` es sólo para el manifiesto y no viaja al motor.
    escribe = {k for k in cfg.generation.keys() if k != "presupuesto"}
    huerfanas = escribe - lee
    assert not huerfanas, (
        f"El perfil escribe {sorted(huerfanas)} y `_load_vllm` no las lee: "
        "estarían declaradas pero desconectadas del motor.")


def test_la_entrada_de_v2_sustituye_el_perfil_de_la_v1_1():
    """En un subproceso a propósito.

    `inference_v2` y `inference_v1_1` reasignan ambos
    `inference.run_merged_solution` al importarse: cada uno es el único
    entrypoint de su contenedor, pero en un mismo intérprete gana el último. Si
    esta prueba importara V2 en el proceso de pytest, rompería las pruebas de la
    V1.1 que comprueban su propia reasignación. Aislarlo también es más fiel:
    así es como se ejecuta de verdad.
    """
    import subprocess
    import sys

    codigo = (
        "import version_final_reto.investigacion.inference_solo_perfil as v2;"
        "from version_final_reto.common import gc_entry;"
        "from version_final_reto.runtime_16gb import resources;"
        "import inference;"
        "assert gc_entry.configure is resources.configure, 'el perfil no quedó sustituido';"
        "assert inference.run_merged_solution is v2.run_merged_solution, 'la entrada no quedó sustituida';"
        "print('OK')")
    env = {**os.environ, "PYTHONPATH": f"{RAIZ}:{RAIZ / 'src'}"}
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True,
                       env=env, cwd=str(RAIZ))
    assert r.returncode == 0, r.stderr[-2000:]
    assert "OK" in r.stdout


def test_sin_cuda_no_se_reparte_vram_pero_el_muestreo_sigue_siendo_determinista(monkeypatch):
    monkeypatch.setattr(resources, "inventario",
                        lambda: {"total_bytes": 0, "libre_bytes": 0, "usada_bytes": 0,
                                 "fuente": None, "nombre": None, "driver": None})
    cfg = resources.configure(_cfg())
    assert cfg.generation.temperature == 0.0
    assert "kv_cache_memory_bytes" not in cfg.generation
