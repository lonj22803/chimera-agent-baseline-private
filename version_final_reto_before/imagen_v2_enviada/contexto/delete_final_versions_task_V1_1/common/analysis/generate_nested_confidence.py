"""CPU evidence for nested_stratified_cv_10x9; no historical predictions.

Run with PYTHONPATH=src:. .venv/bin/python -m
 delete_final_versions_task_V1_1.common.analysis.generate_nested_confidence --workers 20
Task1 uses the fixed delivered decision/agreeing-votes policy and refits the
structured/fusion recipes. Document heads retain the trace recipe's internal
selection threshold, with medians fitted separately in every training split.
Task2 uses the saved uncertainty ensemble of GuidelineCascade, refitting its
three heads and their column selection. Only AGHI (the union of node inputs)
is needed; unused embedding columns never enter any head.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import warnings

sys.dont_write_bytecode = True
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import numpy as np
from sklearn.base import clone
from sklearn.model_selection import StratifiedKFold
from .. import chimera_experts
from ..chimera_experts import dataset as d1, dataset_task2 as d2
from ..chimera_experts.io import load_cases
from ..uncertainty_forms import pool_variance, RUNG_CEILING_TASK2
from .measure_forms import posterior, _check_evidence

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PROTOCOL = 'nested_stratified_cv_10x9'
NODE_BLOCKS = {'cancer': 'GH', 'treat': 'AGH', 'fit': 'AGI'}


def single_thread(estimator):
    params = estimator.get_params(deep=True)
    estimator.set_params(**{k: 1 for k in params if k == 'n_jobs' or k.endswith('__n_jobs')})
    for head in (getattr(estimator, 'heads', None) or {}).values():
        single_thread(head)
    base = getattr(estimator, 'base_estimator', None)
    if base is not None:
        single_thread(base)
    return estimator


def matrix(train, test, dataset, blocks):
    X, names = dataset.build_matrix(train, blocks)
    raw, all_names = dataset.build_matrix(test, blocks, drop_constant=False)
    index = {n: i for i, n in enumerate(all_names)}
    T = np.array([[row[index[n]] if n in index else np.nan for n in names] for row in raw])
    return X, T, names


def document_plans(train, test, recipe):
    """Only document heads affect this measurement; do not fit unused weights.

    The trace recipe selects heads by internal single-case exclusion. Both its
    medians and the mode comparator are recomputed within that training set.
    This selection is wholly inside the outer/inner fitting partition.
    """
    from ..chimera_experts import reasoning_model as rm
    X = np.array([[rm.case_predictors(c)[k] for k in rm.PREDICTORS] for c in train])
    masked_test = [replace(c, clinical={k: v for k, v in c.clinical.items() if k != 'family_history'}) for c in test]
    T = np.array([[rm.case_predictors(c)[k] for k in rm.PREDICTORS] for c in masked_test])
    plans = [[] for _ in test]
    for section in rm.SECTIONS:
        if section == 'family_history':
            continue
        y = np.array([int(section in (c.reasoning.get('reveal_sequence') or [])) for c in train])
        prediction = np.full(len(test), y.mean() >= .5)
        if len(np.unique(y)) == 2:
            hits, floor = [], []
            for i in range(len(train)):
                tr = np.arange(len(train)) != i
                hits.append(int(posterior(X[tr], y[tr], X[[i]])[0].argmax()) == y[i])
                floor.append(int(y[tr].mean() > .5) == y[i])
            if np.mean(hits) - np.mean(floor) >= recipe.min_gain:
                prediction = posterior(X, y, T).argmax(1).astype(bool)
        for plan, chosen in zip(plans, prediction):
            if chosen:
                plan.append(section)
    for case, plan in zip(test, plans):
        if not plan:
            bucket = [c for c in train if c.prompt.get('bx') == case.prompt.get('bx')] or train
            plan.extend(s for s in rm.SECTIONS if s != 'family_history' and
                        np.mean([s in (c.reasoning.get('reveal_sequence') or []) for c in bucket]) >= .5)
    return plans


def task1(train, test):
    import joblib
    from ..chimera_experts.expert_classifier import BiopsyExpert
    from ...task_1.agent.paths import ARTIFACT
    from ...task_1.agent.protocol import consolidate
    from ...task_1.agent.decide import documented_grade
    from ...task_1.experts_1.cohort import criterion
    from ...task_1.experts_1.panel import _verdict_payload
    plans = document_plans(train, test, joblib.load(ARTIFACT['trace'])['model'])
    predictions, schemas = {}, {}
    y = d1.build_labels(train)
    for name in ('structured', 'fusion'):
        expert = BiopsyExpert.load(ARTIFACT[name])
        X, T, names = matrix(train, test, d1, expert.blocks)
        fitted = single_thread(clone(expert.model)).fit(X, y)
        if name == 'fusion':
            masked = [replace(c, clinical={k: v for k, v in c.clinical.items()
                       if k != 'laboratory_results'}) if 'laboratory_results' not in plan else c
                      for c, plan in zip(test, plans)]
            _, T, _ = matrix(train, masked, d1, expert.blocks)
        predictions[name] = fitted.verdicts(T, d1.completeness_vector(masked if name == 'fusion' else test))
        schemas[name] = names
    rows = []
    for i, (case, opened) in enumerate(zip(test, plans)):
        a = predictions['structured'][i]
        b = predictions['fusion'][i] if 'radiology_report' in opened else None
        structured = _verdict_payload(a)
        fusion = _verdict_payload(b) if b else None
        cohort = criterion(case.prompt)
        grade = documented_grade('\n'.join(json.dumps(case.clinical[s], ensure_ascii=False)
                                for s in opened if s in case.clinical))
        result = consolidate(case.prompt, cohort, structured, fusion, None,
                             {'variable_weights': {}, 'reveal_sequence': opened}, grade, opened)
        if result['who'] == 'EXPERT-COHORT':
            rung = {'None': 'no_prior_biopsy', 'Negative': 'negative_biopsy'}.get(
                str(case.prompt.get('bx') or 'None'), 'positive_extreme')
        elif result['who'] == 'documented grade':
            rung = 'grade_ge2' if grade['gg'] >= 2 else 'grade_1'
        else:
            rung = result['who'].replace(' ', '_')
        budget = pool_variance([{'p': float(v.probability),
                   'epistemic_model': float(v.epistemic_model),
                   'epistemic_missing': float(v.epistemic_missing), 'aleatoric': float(v.aleatoric)}
                   for v in (a, b) if v is not None])
        rows.append({'case_id': case.case_id, 'decision': result['decision'], 'rung': rung,
                     'agreement': result['confidence'], 'budget': asdict(budget), 'opened': opened})
    return rows, schemas


def task2(train, test):
    import joblib
    from ..chimera_experts.uncertainty import rubin_pool
    from ..chimera_experts.uncertainty_multiclass import make_verdict
    bundle = joblib.load(ROOT / 'delete_final_versions_task/task_2/experts_2/model/expert_five.joblib')
    wrapper = single_thread(clone(bundle['model']))
    X, T, names = matrix(train, test, d2, 'AGHI')
    cols = {node: [names.index(n) for n in d2.build_matrix(train, blocks)[1] if n in names]
            for node, blocks in NODE_BLOCKS.items()}
    wrapper.base_estimator.columns = cols
    wrapper.fit(X, d2.build_labels(train))
    # The cascade has four fixed outputs even when a rare class is absent in
    # this training partition. No example/label is added to compensate.
    wrapper.classes_ = np.arange(len(d2.CLASSES))
    tensor = wrapper.probability_tensor(T)
    rows = []
    for i, case in enumerate(test):
        v = make_verdict(tensor[i], d2.CLASSES, float(d2.completeness_vector([case])[0]))
        rung = {'continued_surveillance': 'cancer', 'active_surveillance': 'treat',
                'active_treatment': 'fit', 'watchful_waiting': 'fit'}[v.decision]
        # Work on the scalar probability of the decided class, so model and
        # missing are probability variances, not squared mutual information.
        selected = tensor[i, :, :, d2.CLASSES.index(v.decision)]
        _, model_sigma, missing_sigma = rubin_pool(selected)
        agreement = v.confidence
        levels = ['clear', 'borderline', 'uncertain']
        agreement = levels[max(levels.index(agreement), levels.index(RUNG_CEILING_TASK2[rung]))]
        rows.append({'case_id': case.case_id, 'decision': v.decision, 'rung': rung,
                     'agreement': agreement, 'budget': {'model': model_sigma**2,
                     'missing': missing_sigma**2, 'panel': 0., 'aleatoric': v.aleatoric},
                     'node_probabilities': {n: float(np.mean([m.node_probabilities(T[[i]])[n][0]
                                                            for m in wrapper.members_])) for n in NODE_BLOCKS}})
    return rows, {node: [names[j] for j in indexes] for node, indexes in cols.items()}


def fit_job(job):
    task, outer, inner, train_ids, test_ids = job
    start = time.perf_counter()
    cases = [c for c in load_cases(ROOT / f'data/task{task}', task, labelled_only=True) if c.reasoning]
    by_id = {c.case_id: c for c in cases}
    train, test = [[by_id[cid] for cid in ids] for ids in (train_ids, test_ids)]
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        rows, schemas = (task1 if task == 1 else task2)(train, test)
    for row in rows:
        row.update(training_case_ids=train_ids, protocol=PROTOCOL,
                   provenance=f'{PROTOCOL}; refit recipes and preprocessing on training partition; task{task}; outer={outer}; inner={inner}')
    return {'task': task, 'outer': outer, 'inner': inner, 'rows': rows,
            'feature_names': schemas, 'seconds': time.perf_counter() - start}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=20)
    parser.add_argument('--output', type=Path, default=HERE / 'nested_confidence_input.json')
    args = parser.parse_args()
    start = time.perf_counter()
    jobs, cohorts = [], {}
    for task, expected in ((1, 91), (2, 72)):
        cases = [c for c in load_cases(ROOT / f'data/task{task}', task, labelled_only=True) if c.reasoning]
        assert len(cases) == expected
        ids, y = np.array([c.case_id for c in cases]), np.array([c.label for c in cases])
        cohorts[task] = set(ids)
        for outer, (tr, te) in enumerate(StratifiedKFold(10, shuffle=True, random_state=0).split(ids, y)):
            jobs.append((task, outer, -1, ids[tr].tolist(), ids[te].tolist()))
            for inner, (itr, ite) in enumerate(StratifiedKFold(9).split(ids[tr], y[tr])):
                jobs.append((task, outer, inner, ids[tr[itr]].tolist(), ids[tr[ite]].tolist()))
    results = []
    checkpoint = args.output.with_suffix('.fits.jsonl')
    checkpoint.write_text('')
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        pending = [pool.submit(fit_job, job) for job in jobs]
        for future in as_completed(pending):
            result = future.result()
            results.append(result)
            with checkpoint.open('a') as stream:
                stream.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + '\n')
            print(f"{len(results)}/{len(jobs)} task{result['task']} outer={result['outer']} inner={result['inner']} {result['seconds']:.1f}s; wall={time.perf_counter()-start:.1f}s", flush=True)
    output = {}
    for task in (1, 2):
        rows = []
        for outer in range(10):
            group = [r for r in results if r['task'] == task and r['outer'] == outer]
            calibration = sorted([c for r in group if r['inner'] >= 0 for c in r['rows']], key=lambda c: c['case_id'])
            external = next(r['rows'] for r in group if r['inner'] == -1)
            for row in external:
                train = set(row['training_case_ids'])
                assert {c['case_id'] for c in calibration} == train
                assert len(calibration) == len(train)
                assert all(set(c['training_case_ids']) <= train - {c['case_id']} for c in calibration)
                row['calibration'] = calibration
                rows.append(row)
        _check_evidence(rows, cohorts[task])
        output[f'task{task}'] = sorted(rows, key=lambda r: r['case_id'])
    elapsed = time.perf_counter() - start
    output['metadata'] = {'protocol': PROTOCOL, 'workers': args.workers, 'host_cpu_count': os.cpu_count(),
                          'wall_seconds': elapsed, 'jobs': len(jobs),
                          'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                          'task2_agreement': 'Single cascade ensemble tier, capped by terminal node; panel variance=0.',
                          'rare_class': 'Two watchful_waiting cases cannot populate all 10/9 folds. Keep requested splits; degenerate nodes use training prior.',
                          'fits': [{k: v for k, v in r.items() if k != 'rows'} for r in sorted(results, key=lambda r: (r['task'], r['outer'], r['inner']))]}
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    print(f'Written {args.output}; parallel wall time {elapsed:.2f}s', flush=True)


if __name__ == '__main__':
    main()
