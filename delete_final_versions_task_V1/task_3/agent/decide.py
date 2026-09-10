"""Guardias comunes y serialización exacta del contrato T3."""
import math
import re
from delete_final_versions_task_V1.common.guards import (
    process_language, unsourced_grades, unsourced_values, validate_output,
)

DECISION = 'prostate-time-to-recurrence-or-last-follow-up.json'
REASONING = DECISION.replace('.json', '-reasoning.json')

def note_issues(note, corpus, board, findings=None):
    issues = {'process': process_language(note), 'grades': unsourced_grades(note, corpus),
              'values': unsourced_values(note, corpus, board)}
    if len(note.strip()) < 40:
        issues['length'] = ['fewer than 40 characters']
    if findings and findings.get('ln_unknown') == 0:
        bad = re.findall(r'[^.!?]*(?:missing nodal|no lymph nodes|nodes were not|nodal sampling|pNx)[^.!?]*', note, re.I)
        if bad:
            issues['nodal_contradiction'] = bad
    return {key: value for key, value in issues.items() if value}


def fallback_note(case, findings):
    parts = ['Postoperative prognosis depends on the preoperative PSA and the prostatectomy findings.']
    for key, label in [('epe', 'Extraprostatic extension'), ('margins', 'Positive surgical margins'),
                       ('svi', 'Seminal vesicle invasion'), ('lvi', 'Lymphovascular invasion')]:
        value = findings.get(key)
        if value in (0, 1):
            parts.append(f'{label} is ' + ('documented.' if value == 1 else 'reported absent.'))
    if findings.get('ln_unknown') == 1:
        parts.append('No lymph nodes were sampled; pNx does not establish node-negative disease and widens uncertainty.')
    parts.append('Postoperative PSA and its subsequent trajectory are needed to refine this prognosis; '
                 'a future recurrence date cannot be established from surgical risk factors alone.')
    return ' '.join(parts)


def finish(case_id, horizon, note, uncertainty):
    months = horizon['months_to_recurrence']
    if not math.isfinite(months) or months < 0 or horizon['event'] not in (0, 1):
        raise ValueError('Invalid numeric horizon')
    lo, hi = uncertainty['interval_months']
    semantics = ('This is a predicted recurrence horizon, not evidence of observed recurrence.'
                 if horizon['event'] else
                 'This represents expected follow-up without an event, not a known recurrence date.')
    note += (f' The fixed estimated horizon is {months:.2f} months. {semantics} '
             f'The sensitivity range is {lo:.2f}–{hi:.2f} months; its coverage has not been validated.')
    payload = {'case_id': case_id, 'task': 3, 'months_to_recurrence': months, 'reasoning': note}
    valid, error = validate_output(3, payload)
    if not valid:
        raise ValueError(error)
    return payload


def to_gc_outputs(payload, event):
    valid, error = validate_output(3, payload)
    if not valid or not math.isfinite(payload['months_to_recurrence']) or event not in (0, 1):
        raise ValueError(error or 'Invalid numeric output')
    return {DECISION: {'event': int(event), 'months_to_recurrence': payload['months_to_recurrence']},
            REASONING: payload['reasoning']}
