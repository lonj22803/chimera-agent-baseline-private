"""Portavoz CAPRA-S predeclarado; inferencia y reproducción OOF del paso 5.3."""
from __future__ import annotations
import hashlib
import json
import pickle
from pathlib import Path
import numpy as np
from delete_final_versions_task.common.chimera_experts import dataset_task3 as ds
from delete_final_versions_task.task_3.experts_3.train import protocol as trained

BASE = Path(__file__).resolve().parents[1]
EXPERTS = BASE / 'experts_3'

class ModelReader(pickle.Unpickler):
    def find_class(self, module, name):
        if module == 'protocol' and name in {'CoxPipeline', 'Projection', 'Horizon'}:
            return getattr(trained, name)
        return super().find_class(module, name)

class Panel:
    def __init__(self, mode='oof'):
        if mode not in {'oof', 'deployed'}:
            raise ValueError('mode must be oof or deployed')
        self.mode = mode
        self.reports = {}
        self.models = {}
        self.hashes = {}
        for n in ('one', 'two', 'three', 'four', 'five'):
            name = 'expert_' + n
            path = EXPERTS / 'train/artifacts' / (name + '_report.json')
            self.reports[n] = json.loads(path.read_text())
            self.hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            if mode == 'deployed':
                path = EXPERTS / name / 'model' / (name + '.joblib')
                with path.open('rb') as stream:
                    self.models[n] = ModelReader(stream).load()
                self.hashes[name + '_model'] = hashlib.sha256(path.read_bytes()).hexdigest()

    def advice(self, case, n):
        report = self.reports[n]
        if self.mode == 'oof':
            try:
                index = report['case_ids'].index(case.case_id)
            except ValueError as exc:
                raise ValueError('OOF only supports the measured cohort; use deployed for new cases') from exc
            risk = -report['oof_months_order'][index]
        else:
            matrix, names = ds.build_matrix([case], report['blocks'], drop_constant=False)
            model = self.models[n]
            matrix = matrix[:, [names.index(key) for key in model.names]]
            risk = float(model.risk(matrix)[0])
        return {'log_risk': risk, 'mode': self.mode,
                'oof_c_index': report['metrics']['c_index'],
                'delta_capra_bootstrap_95': report['delta_capra_bootstrap_95'],
                'role': 'advisory; does not replace predeclared CAPRA-S spokesperson'}

    def horizon(self, case, risk):
        report = self.reports['five']
        if self.mode == 'oof':
            i = report['case_ids'].index(case.case_id)
            if risk != self.reports['one']['score'][self.reports['one']['case_ids'].index(case.case_id)]:
                raise ValueError('Case CAPRA-S differs from measured OOF input')
            months, event = report['months'][i], report['event_oof'][i]
            fold = next(f for f in report['folds'] if i in f['test'])
            audit = {'held_out_capra': fold['held_out_capra'], 'a': fold['a'], 'b': fold['b'],
                     'threshold': fold['threshold'], 'mode': self.mode}
        else:
            months_array, event_array = self.models['five'].predict([risk])
            months, event = float(months_array[0]), int(event_array[0])
            audit = {'mode': self.mode, 'a': self.models['five'].a, 'b': self.models['five'].b}
        return {'months_to_recurrence': float(months), 'event': int(event), 'calibration': audit}


def uncertainty(months, ln_unknown, missing_count):
    """Banda de sensibilidad explícita; NO intervalo con cobertura validada."""
    base = .20 * months
    imputation = months * (.15 * bool(ln_unknown) + .05 * missing_count)
    width = base + imputation
    return {'interval_months': [max(0., months-width), months+width],
            'base_half_width': base, 'imputation_half_width': imputation,
            'ln_unknown': bool(ln_unknown), 'validated_coverage': False,
            'meaning': 'heuristic sensitivity range, not a calibrated prediction interval'}
