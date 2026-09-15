"""Mide el coste real de los clasificadores task1 antes del LOO anidado.

No genera calibración ni usa predicciones del artefacto entrenado: clone
conserva sólo la receta del estimador. Para estimar el coste se conserva el
esquema de columnas del bundle histórico; NO es un veredicto LOO honesto:
el generador definitivo debe seleccionar columnas dentro de cada partición.
Usa las dependencias ya instaladas de los expertos
originales porque el paso 1.3 exige reentrenar esas mismas recetas.
Se desactiva la escritura de bytecode en las zonas de sólo lectura.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'delete_expert_modelate'))


def main():
    import numpy as np
    from sklearn.base import clone
    from chimera_experts.expert_classifier import BiopsyExpert
    from chimera_experts.io import load_cases
    from chimera_experts.dataset import completeness_vector

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('nested_confidence_cost.json'))
    args = parser.parse_args()
    cases = [c for c in load_cases(ROOT / 'data/task1', task=1, labelled_only=True) if c.reasoning]
    assert len(cases) == 91
    y = np.array([int(str(c.label).lower() == 'yes') for c in cases])
    comp = completeness_vector(cases)
    report = {'purpose': 'cost benchmark, not a confidence cache', 'n': len(cases), 'runs': []}
    for name, folder, artifact in (
        ('structured', 'expert_one', 'expert_one.joblib'),
        ('fusion', 'expert_three', 'expert_three.joblib'),
    ):
        path = ROOT / 'delete_expert_modelate/task_one' / folder / 'model' / artifact
        expert = BiopsyExpert.load(path)
        X = expert._matrix(cases)
        for excluded in ((0,), (0, 1)):
            tr = [i for i in range(len(cases)) if i not in excluded]
            te = list(excluded)
            model = clone(expert.model)
            start = time.perf_counter()
            print(f'{name}: fit {len(tr)} cases, excluded {te}', flush=True)
            model.fit(X[tr], y[tr])
            fitted = time.perf_counter()
            verdicts = model.verdicts(X[te], comp[te])
            finished = time.perf_counter()
            row = {'expert': name, 'artifact_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                   'training_case_ids': [cases[i].case_id for i in tr],
                   'excluded_case_ids': [cases[i].case_id for i in te],
                   'n_members': model.n_members, 'n_imputations': model.n_imputations,
                   'base_estimator': repr(model.base_estimator),
                   'fit_seconds': fitted - start, 'predict_seconds': finished - fitted,
                   'total_seconds': finished - start,
                   'probabilities': [float(v.probability) for v in verdicts]}
            report['runs'].append(row)
            args.output.write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps({k: row[k] for k in ('expert', 'fit_seconds', 'predict_seconds', 'total_seconds')}), flush=True)
    print(f'Report: {args.output}', flush=True)


if __name__ == '__main__':
    main()
