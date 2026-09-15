import importlib
import json
from pathlib import Path
import pytest
from delete_final_versions_task_V1_1.common import guards, slugs
from delete_final_versions_task_V1_1.common.contract import validate_case
from delete_final_versions_task_V1_1.common.chimera_experts.io import Case
from delete_final_versions_task_V1_1.common.vocab import VARIABLES_BY_TASK
from delete_final_versions_task_V1_1.task_2.agent.protocol import trace

@pytest.mark.parametrize('grade', [None, 0, '', 'unknown', 1, 2, 5])
def test_all_eleven_weights(grade):
    weights = trace({'bx_isup': grade})['variable_weights']
    assert set(weights) == set(VARIABLES_BY_TASK[2])
    if grade in (None, 0, '', 'unknown'):
        assert all(weights[k] == 'not_used' for k in ('bx_isup', 'bx_gl_prim', 'bx_gl_sec'))

@pytest.mark.parametrize('task', [1, 2])
def test_guard_rejects_incomplete_and_unknown_weights(task):
    runner = importlib.import_module(f'delete_final_versions_task_V1_1.task_{task}.agent.run_task{task}')
    payload, _ = runner.fallback_case(Case('minimal', task))
    assert guards.validate_output(task, payload)[0]
    assert not guards.validate_output(task, {**payload, 'variable_weights': {}})[0]
    weights = {**payload['variable_weights'], 'invented': 'important'}
    assert not guards.validate_output(task, {**payload, 'variable_weights': weights})[0]

@pytest.mark.parametrize('task', [1, 2, 3])
@pytest.mark.parametrize('strict', ['', 'canonical', 'legacy'])
def test_roundtrip_and_alias_integrity(task, strict, tmp_path):
    runner = importlib.import_module(f'delete_final_versions_task_V1_1.task_{task}.agent.run_task{task}')
    payload, event = runner.fallback_case(Case('minimal', task))
    values = runner.to_gc_outputs(payload, event).values() if task == 3 else runner.to_gc_outputs(payload)
    decision, reasoning = values
    for name, value in slugs.output_files(task, decision, reasoning, strict).items():
        (tmp_path/name).write_text(json.dumps(value))
    assert validate_case(task, tmp_path, strict)
    if not strict and task in slugs.ALIASES:
        (tmp_path/slugs.ALIASES[task][1]).write_text('null')
        with pytest.raises(ValueError, match='Aliases'):
            validate_case(task, tmp_path, strict)

def test_disk_scan_rejects_historically_incomplete_form(tmp_path):
    task = 2
    decision = 'continued_surveillance'
    reasoning = {'confidence': 'clear', 'variable_weights': {}, 'reveal_sequence': [], 'free_text': 'The clinical reasoning is long enough; the form is incomplete.'}
    for name, value in slugs.output_files(task, decision, reasoning).items():
        (tmp_path/name).write_text(json.dumps(value))
    with pytest.raises(ValueError, match='variable_weights'):
        validate_case(task, tmp_path)
