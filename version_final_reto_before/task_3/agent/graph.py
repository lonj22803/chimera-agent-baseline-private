"""Once intervenciones secuenciales, acta inmutable y fuentes explícitas."""
from __future__ import annotations
import json
import os
from version_final_reto.common import prompt_kit
import time
import urllib.request
import numpy as np
from version_final_reto.common.board import Board
from version_final_reto.common.chimera_experts.io import Case
from version_final_reto.common.chimera_experts import dataset_task3 as ds
from . import decide, prompts, protocol

DOCUMENTS = {
    'surgical_pathology_report': 'What grade, stage, margins, vesicles and nodal sampling are documented?',
    'pathology_report': 'Does biopsy grade differ from the prostatectomy specimen?',
    'radiology_report': 'What local extent and imaging limitations are documented?',
    'previous_notes': 'What treatment and postoperative follow-up are documented?',
}

class Task3Board(Board):
    HEAD = Board.HEAD.replace('biopsy decision', 'postoperative recurrence prognosis')


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return None
    return value


def dump(value):
    return json.dumps(clean(value), ensure_ascii=False, allow_nan=False)


class OllamaChair:
    def __init__(self, url='http://localhost:11434', model='gemma4:e4b'):
        self.url, self.model = url, model

    def __call__(self, prompt):
        request = urllib.request.Request(self.url.rstrip('/') + '/api/chat',
            data=json.dumps({'model': self.model, 'stream': False, 'think': False,
                'messages': [{'role': 'user', 'content': prompt}],
                'options': {'temperature': 0, 'seed': 62, 'num_predict': 600, 'num_ctx': 16384}}).encode(),
            headers={'Content-Type': 'application/json'})
        start = time.monotonic()
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.load(response)
        return result['message']['content'].strip(), {
            'role': 'CHAIR', 'model': self.model, 'temperature': 0,
            'seconds': time.monotonic()-start, 'input_tokens': result.get('prompt_eval_count'),
            'output_tokens': result.get('eval_count'), 'approx': False,
            'done_reason': result.get('done_reason')}


class LocalChair:
    """Same vLLM adapter in batch and Grand Challenge, with role-level sampling."""
    def __init__(self, model, meter=None):
        from version_final_reto.common.sampling import speak_as, VOICES
        self.model = speak_as(model, VOICES['chair'])
        self.meter = meter

    def __call__(self, prompt):
        from langchain_core.messages import HumanMessage
        start = time.monotonic()
        response = self.model.invoke([HumanMessage(content=prompt)],
                                     config={'callbacks': [self.meter] if self.meter else []})
        content = response.content
        if not isinstance(content, str):
            content = ' '.join(b.get('text', '') for b in content if isinstance(b, dict))
        return content, {'role': 'CHAIR', 'temperature': 0, 'backend': 'vllm',
                         'seconds': time.monotonic()-start,
                         'usage': getattr(response, 'usage_metadata', None)}


class Conference:
    def __init__(self, panel, chair, guideline_evidence=None):
        self.panel, self.chair = panel, chair
        self.guideline_evidence = guideline_evidence

    def invoke(self, case):
        # Build an input-only case. Neither labels nor reference reasoning reach any role.
        case = Case(case.case_id, 3, prompt=dict(case.prompt),
                    clinical=dict(case.clinical), embeddings=dict(case.embeddings))
        board = Task3Board(case.case_id, 3)
        intake = {k: case.prompt.get(k) for k in ('age', 'psa', 'dre', 'active_treatment_prior_to_surgery')}
        board.say('INTAKE', dump(intake), intake)
        surgical_case = Case(case.case_id, 3, prompt=case.prompt, clinical={
            k: case.clinical[k] for k in ('surgical_pathology_report', 'pathology_report') if k in case.clinical})
        findings = ds._surgical(surgical_case)
        risk = findings['capra_s']
        if not np.isfinite(risk):
            raise ValueError('CAPRA-S cannot be computed from the available record')
        capra = {'score': risk, 'group': 'bajo' if risk <= 2 else 'intermedio' if risk <= 5 else 'alto',
                 'ln_unknown': findings['ln_unknown'], 'published_c_index': .77,
                 'reference': 'Cooperberg et al. 2011, doi:10.1002/cncr.26169',
                 'source': 'surgical_pathology_report and preoperative PSA',
                 'surgical_report': case.clinical.get('surgical_pathology_report')}
        board.say('EXPERT-CAPRA', dump(capra), clean(capra))
        surgical = {'findings': findings, **self.panel.advice(surgical_case, 'two'),
                    'biopsy_source': surgical_case.clinical.get('pathology_report')}
        board.say('EXPERT-SURGICAL', dump(surgical), clean(surgical))
        digital = self.panel.advice(case, 'three')
        digital['prostatectomy_slides'] = len(case.embeddings.get('Prostatectomy slide') or [])
        digital['limitation'] = 'Frozen vectors; no visual histology interpretation or independent BCR validation.'
        board.say('EXPERT-DIGITAL', dump(digital), digital)
        if os.environ.get('CHIMERA_T3_ADVICE') == 'enhanced':
            from ..experts_3.experience import ProfessionalExperience, render
            from ..experts_3.guideline import assess
            recalled = ProfessionalExperience().recall(case, risk)
            board.say('EXPERT-EXPERIENCE', render(recalled), recalled)
            guideline = assess(surgical_case, findings)
            if self.guideline_evidence is not None:
                guideline['rag'] = self.guideline_evidence
            board.say('EXPERT-GUIDELINE', dump(guideline), guideline)
        board.say('MODERATOR', '\n'.join(f'{k}: {q}' for k, q in DOCUMENTS.items()), {'questions': DOCUMENTS})
        opened = {key: case.clinical.get(key) for key in DOCUMENTS}
        board.say('REGISTRAR', dump(opened), {'opened': list(opened), 'documents': opened})
        fusion_case = Case(case.case_id, 3, prompt=case.prompt,
                           clinical={k: v for k, v in opened.items() if v is not None}, embeddings=case.embeddings)
        fusion = self.panel.advice(fusion_case, 'four')
        board.say('EXPERT-FUSION', dump(fusion), fusion)
        selected = getattr(self.panel, 'spokesperson', 'capra') == 'selected'
        decision = {'risk': risk, 'spokesperson': 'nested-selected fusion' if selected else 'CAPRA-S',
                    'rule': ('Selection inside outer folds; DEV, VAL and full-cohort results recorded.' if selected
                             else 'Predeclared CAPRA-S; advisory comparisons do not reselect the spokesperson.')}
        board.say('PANEL-PROTOCOL', dump(decision), decision)
        horizon = self.panel.horizon(case, risk)
        missing = [key for key, value in opened.items() if not value]
        band = protocol.uncertainty(horizon['months_to_recurrence'], findings['ln_unknown'] == 1, len(missing))
        board.say('EXPERT-HORIZON', dump({'horizon': horizon, 'uncertainty': band}),
                  {'horizon': horizon, 'uncertainty': band})
        verification = {'ready': True, 'missing_documents': missing,
                        'ln_unknown': findings['ln_unknown'] == 1,
                        'limitations': 'Numerically ready; postoperative PSA trajectory and follow-up may be absent. '
                        'Sensitivity range is heuristic; no confidence calibration is validated.',
                        'nodal_status': ('No nodes sampled; pNx is not pN0.' if findings['ln_unknown'] == 1
                                         else 'Nodes were sampled; do not claim missing nodal sampling.')}
        board.say('VERIFIER', dump(verification), verification)
        corpus = dump({'intake': intake, 'documents': opened})
        calls, attempts = [], []
        prompt = prompts.chair_prompt(board, case.prompt, case.case_id)
        note = ''
        for attempt in range(2):
            try:
                candidate, telemetry = self.chair(prompt)
                calls.append(telemetry)
                issues = decide.note_issues(candidate, corpus, '', findings)
                attempts.append({'text': candidate, 'issues': issues})
                if not issues:
                    note = candidate
                    break
                prompt = prompts.chair_prompt(board, case.prompt, case.case_id) + '\n' + prompt_kit.chair_challenge(issues)
            except (OSError, ValueError, KeyError) as exc:
                attempts.append({'error': f'{type(exc).__name__}: {exc}'})
                break
        fallback = not bool(note)
        if fallback:
            note = decide.fallback_note(case, findings)
        payload = decide.finish(case.case_id, horizon, note, band)
        board.say('CHAIR', payload['reasoning'], {'fallback': fallback, 'attempts': attempts})
        return {'payload': payload, 'event': horizon['event'], 'board': board,
                'risk': risk, 'uncertainty': band, 'calls': calls, 'fallback': fallback,
                'opened': list(opened), 'mode': self.panel.mode}


def create_conference_graph(panel=None, chair=None, guideline_evidence=None):
    return Conference(panel or protocol.Panel(), chair or OllamaChair(), guideline_evidence)
