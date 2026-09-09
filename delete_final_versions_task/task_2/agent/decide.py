"""Guardias de tarea 2 y salida determinista validada."""
import json
from delete_final_versions_task.common import guards
from . import protocol as P

# Verificada antes de activarla: 0 coincidencias en los 72 free_text task2.
process_language = guards.process_language


def clinical_sources(payload, documents):
    text = json.dumps(payload, ensure_ascii=False) + '\n' + json.dumps(documents, ensure_ascii=False)
    # Las claves estructuradas también documentan grados; no sólo la prosa.
    if payload.get('bx_isup') is not None:
        text += f"\nISUP {payload['bx_isup']}"
    if payload.get('bx_gl_prim') is not None and payload.get('bx_gl_sec') is not None:
        text += f"\nGleason {payload['bx_gl_prim']}+{payload['bx_gl_sec']}"
    return text


def note_faults(note, payload, documents):
    source = clinical_sources(payload, documents)
    return process_language(note) + guards.unsourced_values(note, source, '') + guards.unsourced_grades(note, source)


def clinical_note(payload, decision):
    values = []
    for key, label in (('age', 'Age'), ('psa', 'PSA'), ('pirads', 'PI-RADS'),
                       ('psad', 'PSA density'), ('bx_isup', 'ISUP'), ('ct', 'Clinical stage')):
        value = payload.get(key)
        if value is not None:
            values.append(f'{label} {value}')
    text = '; '.join(values) + '. ' if values else 'The available clinical record is incomplete. '
    text += {'continued_surveillance': 'Continue surveillance and reassess if the clinical findings change.',
             'active_surveillance': 'Active surveillance with reassessment of disease extent and progression.',
             'active_treatment': 'Active treatment is proposed; establish treatment suitability and preferences.',
             'watchful_waiting': 'Watchful waiting is proposed; review competing illness and symptom control.'}[decision]
    text += ' Individual benefit and patient preferences require clinical review.'
    return text


def build_output(case_id, payload, proto, opened, note=None):
    weights = dict(proto['variable_weights'])
    # T2 has the grade, staging and MRI headline on the structured panel.
    # Only family history is hidden in the schema. No blanket section-silencing.
    weights, downgraded = guards.enforce_grounding(weights, opened, {'fh': 'family_history'})
    out = dict(case_id=case_id, task=2, action=proto['decision'], confidence='clear',
               variable_weights=weights, reveal_sequence=[],
               reasoning=note or clinical_note(payload, proto['decision']))
    ok, why = guards.validate_output(2, out)
    if not ok:
        raise ValueError(why)
    return out, downgraded


def to_gc_outputs(structured):
    ok, why = guards.validate_output(2, structured)
    if not ok:
        raise ValueError(why)
    return structured['action'], {k: structured[k] for k in
        ('confidence', 'variable_weights', 'reveal_sequence')} | {'free_text': structured['reasoning']}
