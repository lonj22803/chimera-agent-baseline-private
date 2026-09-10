"""Contratos desde ficheros sueltos; el backend GPU se sustituye explícitamente."""
import importlib
import json
from pathlib import Path

import pytest

from delete_final_versions_task_V1.common import gc_entry as gc
from delete_final_versions_task_V1.common.chimera_experts.io import CLINICAL_FILENAME, FEATURES_FILENAME
from delete_final_versions_task_V1.common.guards import validate_output


@pytest.mark.parametrize('task', [1, 2, 3])
@pytest.mark.parametrize('failure', [False, True])
def test_files_dispatch_and_fallback(tmp_path, monkeypatch, task, failure):
    """No se confunde esta prueba de contrato con una corrida real del LLM."""
    monkeypatch.setenv('CHIMERA_SLUG_STRICT', 'canonical')
    runner = importlib.import_module(f'delete_final_versions_task_V1.task_{task}.agent.run_task{task}')
    source = gc.REPO / f'data/task{task}/agent_input'
    cid = sorted(p.name for p in source.iterdir() if p.is_dir())[0]
    folder = source / cid
    seen = []
    fallback_calls = []
    original_fallback = runner.fallback_case

    def fallback(case):
        fallback_calls.append(case.case_id)
        return original_fallback(case)

    monkeypatch.setattr(runner, "fallback_case", fallback)

    async def backend(actual_task, actual_runner, case, input_dir, embeddings):
        assert actual_task == task and actual_runner is runner
        assert str(input_dir).startswith('/tmp/chimera-')
        assert json.loads((input_dir / cid / CLINICAL_FILENAME[task]).read_text()) == case.clinical
        assert (input_dir / cid / FEATURES_FILENAME).exists()
        from chimera_agent_baseline.tools.base import CaseDataStore
        from chimera_agent_baseline.features import FeatureStore
        assert CaseDataStore(input_dir).get_case(cid) == case.clinical
        assert cid in FeatureStore(input_dir).list_case_ids()
        seen.append(input_dir)
        if failure:
            raise RuntimeError('forced backend failure')
        # Existing valid output fixture, independent of the fallback under test.
        root = gc.REPO / f'delete_final_versions_task/task_{task}/runs/labeled/output/task{task}'
        if task == 1:
            root = gc.REPO / 'delete_final_versions_task/task_1/runs/labeled/output/task1'
        case_folder = root / cid
        decision = json.loads((case_folder / gc.DECISION_FILENAME[task]).read_text())
        reasoning = json.loads((case_folder / gc.DECISION_FILENAME[task].replace('.json', '-reasoning.json')).read_text())
        payload = {'case_id': cid, 'task': task}
        if task == 3:
            return payload | {'months_to_recurrence': decision['months_to_recurrence'], 'reasoning': reasoning}, decision['event']
        payload |= {k: reasoning[k] for k in ('confidence', 'variable_weights', 'reveal_sequence')}
        from chimera_agent_baseline.output.schema import normalise_to_full_shape
        payload = normalise_to_full_shape(task, payload)
        payload['reasoning'] = reasoning['free_text']
        payload['biopsy_decision' if task == 1 else 'action'] = decision == 'yes' if task == 1 else decision
        return payload, None

    monkeypatch.setattr(gc, '_run', backend)
    out = tmp_path / 'output'
    assert gc.dispatch(task, structured_prompt=folder / 'structured-prompt.json',
                       clinical_data=folder / CLINICAL_FILENAME[task],
                       neural_representations=folder / FEATURES_FILENAME, output_path=out) == 0
    assert len(fallback_calls) == int(failure)
    assert len(list(out.iterdir())) == 2
    assert seen and not seen[0].exists()
    decision = json.loads((out / gc.DECISION_FILENAME[task]).read_text())
    reasoning = json.loads((out / gc.DECISION_FILENAME[task].replace('.json', '-reasoning.json')).read_text())
    payload = {'case_id': cid, 'task': task}
    if task == 3:
        assert isinstance(reasoning, str)
        assert decision['event'] in (0, 1)
        payload |= {'months_to_recurrence': decision['months_to_recurrence'], 'reasoning': reasoning}
    else:
        payload |= {k: reasoning[k] for k in ('confidence', 'variable_weights', 'reveal_sequence')}
        payload['reasoning'] = reasoning['free_text']
        payload['biopsy_decision' if task == 1 else 'action'] = decision == 'yes' if task == 1 else decision
    assert validate_output(task, payload)[0]


def test_unknown_task_rejected(tmp_path):
    with pytest.raises(ValueError, match='task must'):
        gc.dispatch(4, structured_prompt={}, clinical_data={}, neural_representations={}, output_path=tmp_path)
    assert not list(tmp_path.iterdir())


def test_deployed_task3_needs_no_external_evaluator():
    import subprocess
    import sys
    code = '''
from pathlib import Path
original = Path.read_text
def guarded(self, *args, **kwargs):
    if self.name == "evaluate.py":
        raise AssertionError("Runtime must not read external evaluator")
    return original(self, *args, **kwargs)
Path.read_text = guarded
from delete_final_versions_task_V1.task_3.agent.protocol import Panel
panel = Panel("deployed")
assert len(panel.models) == 5
'''
    subprocess.run([sys.executable, '-c', code], cwd=gc.REPO, check=True)
