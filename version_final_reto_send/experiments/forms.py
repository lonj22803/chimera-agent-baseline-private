"""Frozen DEV references, leave-one-out comparison and a single VAL confirmation."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from version_final_reto.common.chimera_experts.io import load_cases
from version_final_reto.task_2.experts_2.experience import ProfessionalExperience, bucket, features, ARTIFACT
from version_final_reto.task_2.agent.protocol import trace
from version_final_reto.task_3.experts_3.experience import ARTIFACT as T3_ARTIFACT, group
from version_final_reto.common.chimera_experts import dataset_task3 as ds

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent/'results/forms.json'
LEVELS = {'not_used': 0, 'noted': 1, 'important': 2, 'decisive': 3}
CONF = {'uncertain': 0, 'borderline': 1, 'clear': 2}


def measure(gt, pred):
    g, p = gt['variable_weights'], pred['variable_weights']
    gs = {k for k,v in g.items() if v in ('important', 'decisive')}
    ps = {k for k,v in p.items() if v in ('important', 'decisive')}
    return {'factor_f1': 2*len(gs&ps)/(len(gs)+len(ps)) if gs or ps else 1.,
            'variable_weight': 1-float(np.mean([abs(LEVELS[v]-LEVELS[p.get(k,'not_used')])/3 for k,v in g.items()])),
            'confidence': 1-abs(CONF[gt['confidence']]-CONF[pred['confidence']])/2}


def average(rows):
    return {k: float(np.mean([r[k] for r in rows])) for k in rows[0]} if rows else {}


def main():
    if OUT.exists():
        raise SystemExit('A frozen experiment already exists; use its results, do not repeatedly inspect VAL.')
    cases = load_cases(ROOT/'data/task2', 2, labelled_only=True)
    dev_ids = set((ROOT/'dev/splits/task2_dev.txt').read_text().splitlines())
    val_ids = set((ROOT/'dev/splits/task2_val.txt').read_text().splitlines())
    assert not dev_ids & val_ids
    dev, val = [c for c in cases if c.case_id in dev_ids], [c for c in cases if c.case_id in val_ids]
    rows = [{'case_id': c.case_id, 'bucket': bucket(c.prompt),
             'features': [float(v) if np.isfinite(v) else None for v in features(c.prompt)],
             **{k: c.reasoning[k] for k in ('confidence','variable_weights','free_text')}} for c in dev]
    expert = ProfessionalExperience(rows=rows)
    result = {'selection': 'DEV LOO; VAL read once only if DEV improves factor F1; no treatment votes',
              'references': sorted(dev_ids), 'exclude_self': True}
    def evaluate(cohort):
        measured = []
        for c in cohort:
            base = trace(c.prompt)
            pred = expert.recall(c.case_id, c.prompt)
            if not pred['available']:
                pred = base
            measured.append({'case_id':c.case_id, 'bucket':bucket(c.prompt),
                             'baseline':measure(c.reasoning,base), 'candidate':measure(c.reasoning,pred)})
        return {'baseline':average([r['baseline'] for r in measured]),
                'candidate':average([r['candidate'] for r in measured]), 'rows':measured}
    result['dev'] = evaluate(dev)
    improve = result['dev']['candidate']['factor_f1'] > result['dev']['baseline']['factor_f1']
    if improve:
        result['val'] = evaluate(val)
    result['eligible_for_paired_judge'] = bool(improve and result['val']['candidate']['factor_f1'] > result['val']['baseline']['factor_f1'])
    result['adopted'] = False  # Requires paired official judge: changing factors affects its rubric too.
    result['reason'] = 'Paired judge required' if result['eligible_for_paired_judge'] else 'Did not reproduce an improvement; baseline retained'
    validation = {}
    for b in sorted({r['bucket'] for r in result['dev']['rows']}):
        sub = [r for r in result['dev']['rows'] if r['bucket']==b]
        validation[b] = {'n':len(sub), 'baseline':average([r['baseline'] for r in sub]),
                         'experience':average([r['candidate'] for r in sub]), 'protocol':'DEV LOO'}
    ARTIFACT.parent.mkdir(parents=True,exist_ok=True)
    ARTIFACT.write_text(json.dumps({'rows':rows,'validation':validation,'split':'dev','adopted':False},indent=2)+'\n')
    # Narrative T3 memory: frozen DEV observations, never VAL outcomes.
    t3_ids = set((ROOT/'dev/splits/task3_dev.txt').read_text().splitlines())
    report=json.loads((T3_ARTIFACT.parent/'expert_one_report.json').read_text())
    score_by_id=dict(zip(report['case_ids'],report['score']))
    t3 = []
    for c in load_cases(ROOT/'data/task3',3,labelled_only=True):
        if c.case_id not in t3_ids:
            continue
        score=score_by_id[c.case_id]
        assert score == ds._surgical(c)['capra_s']
        t3.append({'case_id':c.case_id,'score':score,'group':group(score),
                   'age':c.prompt.get('age'),'psa':c.prompt.get('psa'),
                   'months':c.label['months_to_recurrence'],'event':c.label['event']})
    T3_ARTIFACT.write_text(json.dumps({'rows':t3,'split':'dev','authority':'narrative only'},indent=2)+'\n')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('dev','val','references')},indent=2))
    for split in ('dev','val'):
        if split in result:
            print(split,{k:v for k,v in result[split].items() if k!='rows'})


if __name__=='__main__':
    main()
