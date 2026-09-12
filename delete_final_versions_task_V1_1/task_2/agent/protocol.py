"""Cascada y portavoz; las réplicas y los LLM nunca suman votos."""
from __future__ import annotations

import json
from pathlib import Path

from delete_final_versions_task_V1_1.common import uncertainty_forms as U
from delete_final_versions_task_V1_1.task_2.experts_2 import panel as trained

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = TASK_ROOT.parents[1]
DATA = ROOT / 'data' / 'task2'
# Suelo del reasoning_task2 congelado, comprobado contra el artefacto en tests.
MODE_WEIGHTS = dict(pirads='important', ct='noted', fh='noted', comorbidity='noted',
                    psa='important', age='important', psad='noted', cspca='noted',
                    bx_isup='important', bx_gl_prim='noted', bx_gl_sec='noted')
SECTION_BY_TOOL = {**trained.__dict__.get('SECTION_BY_TOOL', {}),
    'get_mri_report': 'radiology_report', 'get_pathology_report': 'pathology_report',
    'get_previous_notes': 'previous_notes', 'get_family_history': 'family_history',
    'get_psa_trend': 'psa_trend', 'get_lab_results': 'laboratory_results'}
# Plan interno fijo de fuentes de los expertos y de las casillas por moda.
# La cabeza reveal de reasoning_task2 es vacía: no es un plan de lectura interno.
INTERNAL_PLAN = tuple(SECTION_BY_TOOL.values())
PRIMARY = ('expert_one', 'expert_two', 'expert_four', 'expert_five')

def _node_auc():
    """AUC por nodo leidos del artefacto entrenado, nunca hardcodeados.

    El acta publica estos numeros; si el experto se reentrena y cambian, el acta
    cambia con el. Fallback explicito si el informe no esta, para no inventar.
    """
    report = TASK_ROOT / 'experts_2' / 'reports' / 'expert_five_report.json'
    try:
        nodes = json.loads(report.read_text())['nodes']
        return {n['nodo']: float(n['auc']) for n in nodes}
    except (OSError, KeyError, ValueError, TypeError):
        return {}


NODE_AUC = _node_auc()


ACTIONS = ('active_surveillance', 'continued_surveillance', 'active_treatment', 'watchful_waiting')


def trace(payload):
    try:
        graded = float(payload.get('bx_isup') or 0) > 0
    except (TypeError, ValueError):
        graded = False
    return {'confidence': 'clear', 'variable_weights': {
        k: v if graded or not k.startswith('bx_') else 'not_used'
        for k, v in MODE_WEIGHTS.items()},
        'reveal_sequence': [], 'internal_plan': list(INTERNAL_PLAN), 'policy': 'moda'}


def fitness_needed(experts):
    return all(experts.get(k, {}).get('available') and
               experts[k].get('ladder') == 'discuss' for k in PRIMARY)


def consolidate(payload, experts, opened):
    # E1 is the calibration anchor (ECE .0425); E5 supplies the open cascade.
    # A firmer cascade can speak when the anchor remains in discuss.
    one, five = experts.get('expert_one', {}), experts.get('expert_five', {})
    who = 'expert_one'
    if not one.get('available') or (one.get('ladder') == 'discuss' and
                                    five.get('available') and five.get('ladder') != 'discuss'):
        who = 'expert_five'
    if fitness_needed(experts) and experts.get('expert_three', {}).get('available'):
        who = 'expert_three'
    chosen = experts.get(who, {})
    action = chosen.get('decision') if chosen.get('available') else None
    if action not in ACTIONS:
        # Explicit deterministic degraded-service fallback, not a fitted policy.
        try:
            grade = float(payload.get('bx_isup') or 0)
        except (TypeError, ValueError):
            grade = 0
        action = 'continued_surveillance' if grade <= 0 else (
            'active_surveillance' if grade == 1 else 'active_treatment')
        who = 'structured_fallback'
    diagnostic, explanation = U.confidence_from_rung(
        'fit' if who == 'expert_three' else 'treat', U.VarianceBudget(0, 0, 0, 0), {})
    return {**trace(payload), 'decision': action, 'who': who,
            'rule': 'reliability_spokesperson', 'nodes': five.get('nodes', {}),
            'replicas': {'expert_two': 'expert_one', 'expert_four': 'expert_one'},
            'fitness_auc': NODE_AUC.get('fit'), 'consistency_ceiling': 0.931,
            'consistency_warning': 'Five cases share an exact profile with a contrary label; individual certainty is limited.',
            'confidence_diagnostic': {'value': diagnostic, 'reason': explanation,
                                      'validated': False, 'adopted': False},
            'opened': list(opened)}


class ExpertReader:
    """Frozen models, evaluated on the supplied visible view, never a full-case cache."""
    def __init__(self):
        self.live = None

    def predict(self, name, case_id, payload, clinical, features):
        import numpy as np
        if self.live is None:
            self.live = trained._live_models()
        case = trained.io.Case(case_id, 2, prompt=payload, clinical=clinical,
                               embeddings={k: v for k, v in features.items() if isinstance(v, list)})
        bundle = self.live['bundles'][name]
        X = trained.align(case, bundle, self.live['projector'])
        model = bundle['model']
        tensor = (model.probability_tensor(X) if hasattr(model, 'probability_tensor')
                  else model.predict_proba(X)[:, None, None, :])
        result = trained.make_verdict(tensor[0], trained.d2.CLASSES,
                                     float(trained.d2.completeness_vector([case])[0])).to_dict()
        result.pop('confidence', None)
        result.update(available=True, confidence='clear', variable_weights=trace(payload)['variable_weights'])
        if hasattr(model, 'node_probabilities'):
            result['nodes'] = {k: float(v[0]) for k, v in model.node_probabilities(X).items()}
        return result


def render_expert(name, result):
    if not result.get('available'):
        return 'Reading pending: the required document has not been retrieved.'
    text = f"{name}: {result['decision']}; reliability rung {result.get('ladder', 'unknown')}."
    if name in ('expert_two', 'expert_four'):
        text += ' Confirmatory replica of Expert 1: identical 72 historical decisions, not an independent vote.'
    if name == 'expert_one':
        text += ' Grade block G, 28 variables; calibration anchor, measured ECE 0.0425.'
    if name == 'expert_five':
        text += '\nCancer? Treat? Benefit? ' + json.dumps(result.get('nodes', {}))
        auc = ' '.join(f'{k} {NODE_AUC[k]:.4f};' for k in ('cancer', 'treat', 'fit') if k in NODE_AUC)
        text += f'\nMeasured node AUC (LOO): {auc}' if auc else ''
        if NODE_AUC.get('fit') is not None:
            text += (f" The benefit node is at chance (AUC {NODE_AUC['fit']:.4f}, accuracy equals the"
                     ' majority floor): it carries no information beyond the base rate.')
    if name == 'expert_three':
        fit = NODE_AUC.get('fit')
        text += (f"\nFitness benefit AUC {fit:.4f}" if fit is not None else '\nFitness benefit AUC unavailable')
        text += '; watchful_waiting only 2/72: not learnable here.'
    return text + '\nForm baseline (not attribution): ' + json.dumps(result.get('variable_weights', {}))
