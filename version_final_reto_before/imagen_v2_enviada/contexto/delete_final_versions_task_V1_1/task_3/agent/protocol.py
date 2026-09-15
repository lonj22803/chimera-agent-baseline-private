"""Portavoz CAPRA-S predeclarado; inferencia y reproducción OOF del paso 5.3."""
from __future__ import annotations
import hashlib
import json
import pickle
import os
from pathlib import Path
import numpy as np
from delete_final_versions_task_V1_1.common.chimera_experts import dataset_task3 as ds
from delete_final_versions_task_V1_1.task_3.experts_3.train import protocol as trained

BASE = Path(__file__).resolve().parents[1]
EXPERTS = BASE / 'experts_3'

#: Clases de entrenamiento que los artefactos de la tarea 3 guardan dentro.
TRAINED = {'CoxPipeline', 'Projection', 'Horizon'}


class ModelReader(pickle.Unpickler):
    """Traduce al módulo que tenemos las rutas con las que se guardó cada artefacto.

    Hay dos formas, de dos épocas. Los cinco expertos guardan el módulo pelado
    ``protocol``. El portavoz se volcó más tarde, desde
    ``experiments/survival_total.py``, con ``pickle.dumps``, y ahí quedó la ruta
    **completa** del paquete de entonces: ``delete_final_versions_task_V1.
    task_3.experts_3.train.protocol``.

    Esa segunda forma es la que el renombrado a V1.1 dejó sin resolver, y no la
    cazó ninguna prueba ni ningún smoke porque el árbol de la V1 sigue
    importable al lado —en el repo y en la imagen de la V1, que es donde
    montábamos el código—. Sólo apareció al correr la imagen de la V1.1, que no
    lo lleva: la tarea 3 entera se iba al respaldo con
    ``ModuleNotFoundError: No module named 'delete_final_versions_task_V1'``.

    Se compara por el final de la ruta, no por el nombre exacto del paquete, para
    que el próximo renombrado no vuelva a romperlo.
    """

    HISTORICO = 'task_3.experts_3.train.protocol'

    def find_class(self, module, name):
        if name in TRAINED and (module == 'protocol' or module.endswith(self.HISTORICO)):
            return getattr(trained, name)
        return super().find_class(module, name)

class Panel:
    def __init__(self, mode='oof', spokesperson=None):
        if mode not in {'oof', 'deployed'}:
            raise ValueError('mode must be oof or deployed')
        self.mode = mode
        # Adoptado el 11-sep-2026: el portavoz sale de la selección anidada, no de
        # CAPRA-S predeclarado. c-index 0,7372 -> 0,8235 sobre los 75. El protocolo
        # estaba pre-registrado (plan 6.3.2) y lo pasó: selección dentro de cada
        # pliegue externo, IC pareado de DEV que excluye cero, VAL que reproduce.
        # `capra` conserva la política anterior para poder comparar y volver atrás.
        self.spokesperson = spokesperson or os.environ.get('CHIMERA_T3_SPOKESPERSON', 'selected')
        if self.spokesperson not in ('capra', 'selected'):
            raise ValueError('Unknown T3 spokesperson')
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
        self.selected = None
        if self.spokesperson == 'selected':
            self.selected = json.loads((EXPERTS/'train/artifacts/spokesperson_candidate.json').read_text())
            if not self.selected['evaluation']['eligible']:
                raise ValueError('Nested DEV/VAL/total gate did not pass')
            if mode == 'deployed':
                with (EXPERTS/'train/artifacts/spokesperson_candidate.joblib').open('rb') as stream:
                    self.selected_model = ModelReader(stream).load()

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
        if self.selected is not None:
            if self.mode == 'oof':
                index = self.selected['case_ids'].index(case.case_id)
                months = self.selected['months'][index]
                percentile = self.selected['percentiles'][index]
            else:
                selection = self.selected['final_selection']
                if selection['family'] == 'CAPRA-S':
                    raw = -risk
                else:
                    blocks = 'S' if selection['family'] == 'S+anchor' else 'ASGDE'
                    matrix, names = ds.build_matrix([case], blocks, drop_constant=False)
                    matrix = matrix[:, [names.index(n) for n in self.selected_model.names]]
                    raw = -float(self.selected_model.risk(matrix)[0])
                reference = np.asarray(self.selected['train_raw'])
                percentile = (np.sum(reference < raw) + .5*np.sum(reference == raw))/len(reference)
                months = self.selected['a'] * np.exp(-self.selected['b']*self.selected['risk_scale']*(1-percentile))
            audit = {**audit, 'spokesperson': 'nested-selected fusion', 'percentile': float(percentile),
                     'months_map': '90 exp(-0.1 * 12 * (1-percentile))',
                     'event_policy': 'unchanged CAPRA event policy',
                     'validation': self.selected['evaluation']}
        elif os.environ.get('CHIMERA_T3_HORIZON') == '105':
            months = 105 * np.exp(-.1*risk)
            audit = {**audit, 'a': 105., 'b': .1, 'selection': 'DEV, confirmed once in VAL'}
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
