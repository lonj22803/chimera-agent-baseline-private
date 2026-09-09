"""Exercise the real socket router and bridge without starting a GPU backend."""
import json
import os
from pathlib import Path

import pytest

import inference
from delete_final_versions_task.common import gc_entry


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
