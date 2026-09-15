"""Historical postoperative cases, strictly narrative and self-excluding."""
import json
from pathlib import Path
import numpy as np
from version_final_reto.common.chimera_experts import dataset_task3 as ds

ARTIFACT = Path(__file__).parent/'train/artifacts/experience_dev.json'


def group(score):
    return 'low' if score <= 2 else 'intermediate' if score <= 5 else 'high'


class ProfessionalExperience:
    def __init__(self, artifact=ARTIFACT):
        path = Path(artifact)
        self.rows = json.loads(path.read_text())['rows'] if path.exists() else []

    def recall(self, case, score):
        eligible = [r for r in self.rows if r['case_id'] != case.case_id and r['group'] == group(score)]
        # CAPRA-S defines the neighbourhood; structured age/PSA only break ties.
        def distance(row):
            d = abs(row['score']-score)
            for key, scale in [('age', 10), ('psa', 10)]:
                try:
                    values = float(case.prompt[key]), float(row[key])
                    if all(np.isfinite(v) for v in values):
                        d += min(abs(values[0]-values[1])/scale, 2)*.1
                except (ValueError, KeyError, TypeError):
                    pass
            return d
        neighbours = sorted(eligible, key=lambda r: (distance(r), r['case_id']))[:3]
        return {'neighbours': neighbours, 'exclude_self': True, 'self_match': False,
                'authority': 'narrative only; no risk estimate, vote, or horizon',
                'limitation': '19 events in 75 historical patients cannot support local survival estimation.'}


def render(result):
    lines = ['I recall these other postoperative patients in the same CAPRA-S group. '
             'Each outcome belongs to another patient, not this patient. '
             'These observations cannot estimate this patient\'s survival or recurrence date.']
    for row in result['neighbours']:
        lines.append(f"Another patient, {row['case_id']}: CAPRA-S {row['score']}; "
                     f"observed {'recurrence' if row['event'] else 'censored follow-up without recurrence'} "
                     f"at {row['months']} months. Do not copy this outcome into the current note.")
    if not result['neighbours']:
        lines.append('No comparable historical patients are available; I abstain.')
    return '\n'.join(lines)
