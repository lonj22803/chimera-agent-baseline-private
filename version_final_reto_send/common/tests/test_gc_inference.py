"""Exercise the real socket router and bridge without starting a GPU backend."""
import json
import os
from pathlib import Path

import pytest

import importlib.util
_candidate = Path(__file__).resolve().parents[2] / "verification/inference_v1_1.py"
_spec = importlib.util.spec_from_file_location("inference_v1_1_candidate", _candidate)
_wrapper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_wrapper)
# El envoltorio sustituye una función dentro del `inference.py` real; los manejadores
# viven ahí, así que es ese módulo el que hay que sustituir en las pruebas. Parchear
# el envoltorio no cambiaría los globales que los manejadores leen.
inference = _wrapper.base
from version_final_reto.common import gc_entry


@pytest.mark.parametrize('task', [1, 2, 3])
@pytest.mark.parametrize('merged', [True, False])
def test_real_interface_routes_to_selected_backend(task, merged, monkeypatch, tmp_path):
    folder = Path(__file__).resolve().parents[3] / f'test/input/interf{task-1}'
    monkeypatch.setattr(inference, 'INPUT_PATH', folder)
    monkeypatch.setattr(inference, 'OUTPUT_PATH', tmp_path)
    monkeypatch.setattr(inference, 'USE_MERGED_SOLUTION', merged)
    monkeypatch.setenv('CHIMERA_MODEL_DIR', 'before-test')
    calls = []

    def backend(**kwargs):
        calls.append(kwargs)
        return 17

    def unexpected(**kwargs):
        pytest.fail('Wrong backend selected')

    monkeypatch.setattr(gc_entry, 'dispatch', backend if merged else unexpected)
    monkeypatch.setattr(inference, 'run_baseline_for_gc_interface', unexpected if merged else backend)
    assert inference.run() == 17
    assert len(calls) == 1
    call = calls[0]
    assert call['task'] == task
    assert call['structured_prompt'] == json.loads((folder / 'structured-prompt.json').read_text())
    assert call['neural_representations'] == json.loads((folder / gc_entry.FEATURES_FILENAME).read_text())
    assert call['clinical_data'] == json.loads((folder / gc_entry.CLINICAL_FILENAME[task]).read_text())
    if merged:
        assert call['output_path'] == tmp_path
        assert call['embedding_model_dir'] == str(inference.EMBEDDING_MODEL_PATH)
        assert os.environ['CHIMERA_MODEL_DIR'] == str(inference.MODEL_PATH)


def test_el_envoltorio_no_duplica_el_entrypoint():
    """La razón de existir del envoltorio: una pieza sustituida, cero líneas copiadas."""
    assert inference.__file__.endswith('/inference.py'), 'debe correr el entrypoint real'
    assert _wrapper.base.run_merged_solution is _wrapper.run_merged_solution
    assert len(_candidate.read_text().splitlines()) < 100, 'volvió a ser una copia'


def test_el_envoltorio_entrega_la_solucion_v1(monkeypatch, tmp_path):
    """Sustituye el paquete y sólo el paquete: rutas y contrato siguen siendo los del original."""
    visto = {}
    monkeypatch.setattr(gc_entry, 'dispatch', lambda **kw: visto.update(kw) or 0)
    monkeypatch.setattr(inference, 'OUTPUT_PATH', tmp_path)
    assert inference.run_merged_solution(task=1, structured_prompt={}, clinical_data={},
                                         neural_representations={}) == 0
    assert visto['output_path'] == tmp_path
    assert visto['embedding_model_dir'] == str(inference.EMBEDDING_MODEL_PATH)


def test_el_paquete_antiguo_nunca_se_importa(monkeypatch, tmp_path):
    """La imagen entrega sólo V1: `delete_final_versions_task` no existe dentro.

    `inference.py:406` lo importa, pero desde dentro de `run_merged_solution`, que el
    envoltorio sustituye antes de cualquier llamada. Si esa sustitución fallara, el
    contenedor moriría con ModuleNotFoundError en el primer caso — el peor momento.
    Aquí se simula la ausencia del paquete y se comprueba que la ruta real no lo toca.
    """
    import builtins
    real = builtins.__import__

    def sin_paquete_antiguo(name, *a, **kw):
        if name.startswith('delete_final_versions_task.'):
            raise ModuleNotFoundError(f'simulado: {name} no viaja en la imagen')
        return real(name, *a, **kw)

    monkeypatch.setattr(builtins, '__import__', sin_paquete_antiguo)
    monkeypatch.setattr(gc_entry, 'dispatch', lambda **kw: 0)
    monkeypatch.setattr(inference, 'OUTPUT_PATH', tmp_path)
    assert inference.run_merged_solution(task=1, structured_prompt={}, clinical_data={},
                                         neural_representations={}) == 0
