"""A specialist's historical form completion; never a treatment vote.

Reference rows are frozen offline. Every recall excludes the patient's ID and
fits its distance scaling only on the remaining reference rows. Clinical
outcomes of the query are neither accepted nor read by this interface.
"""
from collections import Counter
import json
import math
from pathlib import Path
import numpy as np
from delete_final_versions_task_V1_1.task_1.experts_1.experience import features as panel_features
from delete_final_versions_task_V1_1.common.chimera_experts.features_grading import extract
from delete_final_versions_task_V1_1.common.vocab import VARIABLES_BY_TASK

ARTIFACT = Path(__file__).parent/'artifacts/experience_dev.json'
WEIGHTS = np.array([1.5, 1., 1., .5, 1., .7, .5, 1., 1., 1.])


def bucket(payload):
    try:
        grade = float(payload.get('bx_isup'))
    except (ValueError, TypeError):
        return 'unknown'
    return str(int(grade)) if grade in (0, 1, 2) else '3+' if math.isfinite(grade) and grade >= 3 else 'unknown'


def features(payload):
    grading = extract(payload)
    return np.r_[panel_features(payload), [grading[k] for k in ('gleason_prim', 'gleason_sec', 'ct_stage')]]


class ProfessionalExperience:
    def __init__(self, artifact=ARTIFACT, *, rows=None, k=3, exclude_self=True):
        if not exclude_self:
            raise ValueError('Professional experience always excludes the current patient')
        self.k = k
        data = json.loads(Path(artifact).read_text()) if rows is None else {'rows': rows}
        self.rows = data['rows']
        self.validation = data.get('validation', {})

    def recall(self, case_id, payload):
        available = [r for r in self.rows if r['case_id'] != case_id]
        group = bucket(payload)
        pool = [r for r in available if r['bucket'] == group]
        if not pool:
            return {'available': False, 'bucket': group, 'exclude_self': True, 'self_match': False,
                    'neighbours': [], 'authority': 'advisory form only; no treatment vote'}
        x = np.asarray([r['features'] for r in available], dtype=float)
        counts = np.isfinite(x).sum(axis=0)
        mu = np.divide(np.nansum(x, axis=0), counts, out=np.zeros(x.shape[1]), where=counts > 0)
        filled = np.where(np.isfinite(x), x, mu)
        sd = filled.std(axis=0)
        sd[sd < 1e-9] = 1
        z = np.nan_to_num((features(payload)-mu)/sd)
        neighbours = []
        for r in pool:
            rz = np.nan_to_num((np.asarray(r['features'], float)-mu)/sd)
            distance = float(np.linalg.norm((rz-z)*WEIGHTS))
            neighbours.append({**r, 'distance': distance, 'weight': 1/(distance+.05)})
        neighbours = sorted(neighbours, key=lambda r: (r['distance'], r['case_id']))[:self.k]
        def vote(key, default):
            votes = Counter()
            for r in neighbours:
                votes[key(r)] += r['weight']
            return sorted(votes, key=lambda v: (-votes[v], v))[0] if votes else default
        weights = {v: vote(lambda r: r['variable_weights'].get(v, 'not_used'), 'not_used')
                   for v in VARIABLES_BY_TASK[2]}
        return {'available': True, 'bucket': group, 'exclude_self': True, 'self_match': False,
                'confidence': vote(lambda r: r['confidence'], 'clear'), 'variable_weights': weights,
                'neighbours': neighbours, 'pool': len(pool), 'validation': self.validation.get(group),
                'authority': 'advisory form only; no treatment vote'}


def render(result):
    if not result['available']:
        return 'I have no comparable historical form in this ISUP group. I abstain.'
    lines = [f"I recall {result['pool']} other patients in ISUP group {result['bucket']}. "
             'Their forms show what the reading urologist weighed, not facts about this patient. '
             'This experience has no treatment vote.']
    for r in result['neighbours']:
        lines.append('Another patient: ' + json.dumps({'case_id': r['case_id'],
            'distance': round(r['distance'], 3), 'variable_weights': r['variable_weights'],
            'confidence': r['confidence'], 'note': r.get('free_text', '')}, ensure_ascii=False))
    lines.append('LOO form validation in this group: ' + json.dumps(result.get('validation')))
    return '\n'.join(lines)
