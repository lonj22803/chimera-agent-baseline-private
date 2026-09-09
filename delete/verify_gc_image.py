"""CPU-only audit; run with the built image's Python, from /opt/app."""
from pathlib import Path
import json
import os
import re

root = Path.cwd()
base = root / 'delete_final_versions_task'
required = [base / 'common/chimera_experts/__init__.py',
            base / 'task_1/artifacts/panel_cache.json',
            base / 'task_2/experts_2/artifacts/panel_cache.json',
            base / 'task_3/experts_3/train/__init__.py',
            base / 'task_3/experts_3/train/protocol.py',
            base / 'task_3/experts_3/train/artifacts/historical_probes_report.json',
            root / 'resources/guidelines_db/chroma.sqlite3']
for name in ('expert_one', 'expert_three', 'expert_two_psa_projector', 'reasoning_trace_model'):
    required.append(base / f'task_1/experts_1/model/{name}.joblib')
for name in ('expert_one', 'expert_two', 'expert_three', 'expert_four', 'expert_five', 'reasoning_task2', 'embedding_projector'):
    required.append(base / f'task_2/experts_2/model/{name}.joblib')
for name in ('one', 'two', 'three', 'four', 'five'):
    required.extend([base / f'task_2/experts_2/reports/expert_{name}_report.json',
                     base / f'task_3/experts_3/expert_{name}/model/expert_{name}.joblib',
                     base / f'task_3/experts_3/train/artifacts/expert_{name}_report.json'])
for path in required:
    assert path.is_file(), path
    assert path.name == "__init__.py" or path.stat().st_size, path
for part in ('agent_input', 'ground_truth'):
    cases = [p for p in (root / 'data/task1' / part).iterdir() if p.is_dir()]
    assert len(cases) == 91, (part, len(cases))
assert not (root / 'data/task2').exists()
assert not (root / 'data/task3').exists()
assert not list((root / 'data/task1').rglob('prostate-modality-level-neural-representations.json'))
assert not any(p.is_dir() and p.name in ('runs', 'analysis', '__pycache__') for p in base.rglob('*'))
assert (root / 'model').is_symlink()
assert os.readlink(root / 'model') == '/opt/ml/model'
for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_DATASETS_OFFLINE', 'DO_NOT_TRACK'):
    assert os.environ[key] == '1', key
# Report paths/names only, never suspected secret values.
secret = re.compile(rb'(?<![A-Za-z0-9_])(?:hf_[A-Za-z0-9]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{20,})')
suspects = []
for path in root.rglob('*'):
    if path.is_symlink() or not path.is_file():
        continue
    if path.name == '.env' or path.name.startswith('.env.'):
        suspects.append(str(path.relative_to(root)))
    with path.open('rb') as stream:
        tail = b''
        while chunk := stream.read(1024 * 1024):
            if secret.search(tail + chunk):
                suspects.append(str(path.relative_to(root)))
                break
            tail = chunk[-256:]
assert not suspects, suspects
assert not any(re.search(r'(?:^|_)(?:TOKEN|API_KEY|SECRET|PASSWORD)$', k, re.I) and v
               for k, v in os.environ.items()), 'Credential environment variable present'
# Register historical module aliases before deserializing the trusted local artifacts.
from delete_final_versions_task.common import gc_entry
import joblib
for path in required:
    if path.suffix == '.joblib' and '/task_3/' not in str(path):
        joblib.load(path)
from delete_final_versions_task.task_3.agent.protocol import Panel
assert len(Panel('deployed').models) == 5
print(json.dumps({'required_artifacts': len(required), 'task1_precedents': 91,
                  'joblib_bytes': sum(p.stat().st_size for p in required if p.suffix == '.joblib'),
                  'secret_pattern_matches': 0, 'deserialization': 'passed'}))
