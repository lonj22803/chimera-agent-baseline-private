"""Paso 5.3: protocolo reproducible; numpy y biblioteca estándar únicamente."""
from __future__ import annotations
import ast
import hashlib
import json
import pickle
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from version_final_reto.common.chimera_experts import dataset_task3 as ds
from version_final_reto.common.chimera_experts.io import load_cases

BASE = Path(__file__).resolve().parents[1]
FLOORS = {'baseline_actual': .6636, 'CAPRA_S_crudo': .7372, 'constante_60_meses': .5}
SEEDS = (11, 23, 37, 51, 71)
GRID = [(k, a) for k in (1, 2, 4) for a in (1., 10.)]
OFFICIAL = Path.home() / 'PycharmProjects/CHIMERA-agent-eval/evaluation/evaluate.py'


def official_metrics():
    # Sólo funciones puras: no importa evaluate ni arranca el juez.
    names = {'concordance_index', '_censoring_km', '_km_at', 'time_dependent_auc'}
    tree = ast.parse(OFFICIAL.read_text())
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(selected) == len(names)
    scope = {}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(OFFICIAL), 'exec'), scope)
    return scope


class _LazyMetrics(dict):
    """El evaluador sólo se necesita al medir, nunca al cargar modelos desplegados."""
    def __getitem__(self, key):
        if not self:
            self.update(official_metrics())
        return super().__getitem__(key)


METRICS = _LazyMetrics()


def concordance(t, months, e):
    mask = (e[:, None] == 1) & (t[:, None] < t[None, :])
    if not mask.any():
        return None
    d = months[:, None] - months[None, :]
    return float(((d < 0) + .5*(d == 0))[mask].mean())


def interval(t, p, e, other=None):
    rng = np.random.default_rng(20260909)
    values = []
    for _ in range(1000):
        idx = rng.integers(0, len(t), len(t))
        v = concordance(t[idx], p[idx], e[idx])
        if v is not None:
            if other is not None:
                v -= concordance(t[idx], other[idx], e[idx])
            values.append(v)
    return np.quantile(values, [.025, .975]).tolist() if values else None


def measure(t, p, e):
    c = concordance(t, p, e)
    assert c == METRICS['concordance_index'](t.tolist(), p.tolist(), e.tolist())
    return {'c_index': c, 'bootstrap_95': interval(t, p, e), 'bootstrap_n': 1000,
            'td_auc': {str(h): METRICS['time_dependent_auc'](t.tolist(), p.tolist(), e.tolist(), h)
                       for h in (12, 24, 36, 60)}}


def folds(e, seed, n=5):
    rng = np.random.default_rng(seed)
    groups = [np.array_split(rng.permutation(np.flatnonzero(e == value)), n) for value in (0, 1)]
    for k in range(n):
        test = np.sort(np.r_[groups[0][k], groups[1][k]])
        yield np.setdiff1d(np.arange(len(e)), test), test


class Projection:
    """Poda, media, escala y PCA aprendidos exclusivamente del entrenamiento."""
    def fit(self, x, k):
        count = np.isfinite(x).sum(axis=0)
        self.mean = np.divide(np.nansum(x, axis=0), count, out=np.zeros(x.shape[1]), where=count > 0)
        filled = np.where(np.isfinite(x), x, self.mean)
        sd = filled.std(axis=0)
        self.keep = (count >= max(6, int(np.ceil(.08*len(x))))) & (sd > 1e-12)
        self.scale = sd[self.keep]
        z = (filled[:, self.keep]-self.mean[self.keep])/self.scale
        if not z.shape[1]:
            self.components = np.zeros((0, 1)); self.pc_scale = np.ones(1)
        else:
            # Dual PCA: avoids a full SVD of 2944 embedding columns.
            values, vectors = np.linalg.eigh(z @ z.T)
            chosen = np.argsort(values)[::-1][:min(k, z.shape[1], len(z)-1)]
            chosen = chosen[values[chosen] > 1e-10]
            self.components = z.T @ vectors[:, chosen] / np.sqrt(values[chosen])
            self.pc_scale = np.sqrt(values[chosen]/len(z))
        return self

    def transform(self, x):
        filled = np.where(np.isfinite(x), x, self.mean)
        return ((filled[:, self.keep]-self.mean[self.keep])/self.scale) @ self.components / self.pc_scale


class CoxPipeline:
    """Breslow + ridge; Newton amortiguado, pérdida por evento, <=5 coeficientes."""
    def fit(self, x, t, e, names, k, alpha):
        self.names = names
        emb = np.array([n.startswith('emb_') for n in names])
        self.parts = []
        for mask, components in ((~emb, 1 if emb.any() else k), (emb, k)):
            if mask.any():
                self.parts.append((mask, Projection().fit(x[:, mask], components)))
        z = self.transform(x)
        self.beta = np.zeros(z.shape[1])
        groups = [(int(((t == u) & (e == 1)).sum()), z[(t == u) & (e == 1)].sum(axis=0), z[t >= u])
                  for u in np.unique(t[e == 1])]
        def objective(beta):
            loss = .5*alpha*(beta @ beta)
            grad = alpha*beta
            hess = alpha*np.eye(len(beta))
            for d, observed, risk_set in groups:
                eta = risk_set @ beta
                maximum = eta.max()
                weights = np.exp(eta-maximum); total = weights.sum(); weights /= total
                mean = weights @ risk_set
                loss += (d*(maximum+np.log(total))-observed @ beta)/e.sum()
                grad = grad + (d*mean-observed)/e.sum()
                centered = risk_set-mean
                hess += d*(centered.T @ (weights[:, None]*centered))/e.sum()
            return loss, grad, hess
        for iteration in range(100):
            loss, grad, hess = objective(self.beta)
            if np.max(np.abs(grad), initial=0) < 1e-7:
                break
            step = np.linalg.solve(hess, grad)
            rate = 1.
            while objective(self.beta-rate*step)[0] > loss-1e-4*rate*(grad @ step):
                rate *= .5
                if rate < 1e-12:
                    raise RuntimeError('Cox line search failed')
            self.beta -= rate*step
        else:
            raise RuntimeError('Cox did not converge')
        self.k, self.alpha = k, alpha
        self.iterations = iteration
        return self

    def transform(self, x):
        return np.column_stack([p.transform(x[:, mask]) for mask, p in self.parts])

    def risk(self, x):
        # Log relative hazard; monotonic with exp(eta), better numerical stability.
        return self.transform(x) @ self.beta


def select(x, t, e, names, seed):
    splits = list(folds(e, seed, 3))
    scores = []
    for k, alpha in GRID:
        predictions = np.empty(len(t))
        for tr, va in splits:
            model = CoxPipeline().fit(x[tr], t[tr], e[tr], names, k, alpha)
            predictions[va] = -model.risk(x[va])
        scores.append(concordance(t, predictions, e))
    # Ties prefer fewer components then stronger ridge.
    best = max(range(len(GRID)), key=lambda i: (scores[i], -GRID[i][0], GRID[i][1]))
    return GRID[best], scores


def nested(x, t, e, names):
    predictions, audits = [], []
    for seed in SEEDS:
        p = np.empty(len(t))
        for fold, (tr, va) in enumerate(folds(e, seed)):
            (k, alpha), scores = select(x[tr], t[tr], e[tr], names, seed+100+fold)
            model = CoxPipeline().fit(x[tr], t[tr], e[tr], names, k, alpha)
            p[va] = -model.risk(x[va])
            audits.append({'seed': seed, 'fold': fold, 'train': tr.tolist(), 'test': va.tolist(),
                          'k': k, 'alpha': alpha, 'coefficients': len(model.beta), 'inner_scores': scores})
        predictions.append(p)
    return np.array(predictions), audits


def time_score(t, p, e):
    error = np.where(e == 1, np.abs(p-t), np.maximum(t-p, 0))
    return float(np.maximum(0, 1-error/np.maximum(t, 1)).mean())


class Horizon:
    """Calibración estrictamente decreciente con un offset y umbral event.

    Selección por CV interna; la parametrización evita empates nuevos. No ajusta
    un orden. El riesgo de entrada predeclarado es CAPRA-S (ancla portavoz).
    """
    def fit(self, risk, t, e, seed=101):
        # Predeclared bands about 90*exp(-0.1*CAPRA); width < one score unit.
        # Distinct integer CAPRA groups cannot cross, even with different fits.
        candidates = [(90.*np.exp(-.1*offset), .1) for offset in (-.4, 0., .4)]
        splits = list(folds(e, seed, 3))
        # Cada candidato es una función fija: la puntuación de selección es OOF.
        scores = [np.mean([time_score(t[va], a*np.exp(-b*risk[va]), e[va]) for _, va in splits])
                  for a, b in candidates]
        self.a, self.b = candidates[int(np.argmax(scores))]
        thresholds = [float('inf'), 7., 9.]
        accuracy = [np.mean((risk >= threshold) == e) for threshold in thresholds]
        self.threshold = thresholds[int(np.argmax(accuracy))]
        return self

    def predict(self, risk):
        return self.a*np.exp(-self.b*np.asarray(risk)), (np.asarray(risk) >= self.threshold).astype(int)


def save_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False)+'\n')


def save_model(name, model):
    path = BASE / name / 'model'
    path.mkdir(parents=True, exist_ok=True)
    # Uncompressed pickle is also readable by joblib.load; no joblib dependency.
    (path / (name+'.joblib')).write_bytes(pickle.dumps(model, protocol=5))


def ladder(t, p, e, completeness):
    result = []
    for name, mask in [('firm', completeness >= .9), ('supports', (completeness >= .75) & (completeness < .9)),
                       ('discuss', completeness < .75)]:
        result.append({'tier': name, 'n': int(mask.sum()), **measure(t[mask], p[mask], e[mask])})
    values = [r['c_index'] for r in result if r['c_index'] is not None]
    return {'definition': 'firm >=0.90; supports [0.75,0.90); discuss <0.75 de completitud de fuentes',
            'rows': result, 'monotone': len(values) == 3 and values[0] >= values[1] >= values[2]}


def main():
    cases = load_cases(ROOT/'data/task3', task=3, labelled_only=True)
    t, e = ds.build_labels(cases)
    assert len(t) == 75 and e.sum() == 19
    capra = np.array([ds._surgical(c)['capra_s'] for c in cases])
    assert np.isfinite(capra).all()
    completeness = ds.completeness_vector(cases)
    ids = [c.case_id for c in cases]
    protocol = {'outer': '5-fold stratified x 5 seeds', 'seeds': SEEDS, 'inner': '3-fold stratified',
                'grid': GRID, 'selection': 'inner pooled Harrell; ties fewer PCs then stronger ridge',
                'report_prediction': 'mean of five held-out log hazards (repeated cross-fitting)',
                'bootstrap': '1000 case resamples of fixed OOF predictions; conditional, no refitting',
                'n': 75, 'events': 19, 'floors': FLOORS,
                'official_sha256': hashlib.sha256(OFFICIAL.read_bytes()).hexdigest()}
    reports = {}
    reports['expert_one'] = {'blocks': 'S', 'model': 'deterministic CAPRA-S', 'protocol': protocol,
                            'metrics': measure(t, -capra, e), 'score': capra.tolist(),
                            'risk_group': ['bajo' if v <= 2 else 'intermedio' if v <= 5 else 'alto' for v in capra],
                            'case_ids': ids, 'oof_months_order': (-capra).tolist(),
                            'ladder': ladder(t, -capra, e, completeness)}
    save_model('expert_one', {'rule': 'CAPRA-S', 'blocks': 'S', 'implementation': 'dataset_task3._surgical',
                              'risk_groups': {'bajo': [0, 2], 'intermedio': [3, 5], 'alto': [6, 12]}})
    cached = {}
    def evaluate(blocks, rp_only=False):
        key = (blocks, rp_only)
        if key not in cached:
            x, names = ds.build_matrix(cases, blocks, drop_constant=False)
            if rp_only:
                keep = [i for i, n in enumerate(names) if n.startswith('emb_rp_')]
                x, names = x[:, keep], [names[i] for i in keep]
            print('Nested Cox:', blocks, 'RP only:', rp_only, flush=True)
            pred, audit = nested(x, t, e, names)
            cached[key] = (x, names, pred, audit)
        return cached[key]
    for name, blocks, rp_only in [('expert_two', 'SG', False), ('expert_three', 'E', True),
                                  ('expert_four', 'ASGDE', False)]:
        x, names, pred, audit = evaluate(blocks, rp_only)
        p = pred.mean(axis=0)
        (k, alpha), scores = select(x, t, e, names, 999)
        model = CoxPipeline().fit(x, t, e, names, k, alpha)
        save_model(name, model)
        reports[name] = {'blocks': blocks, 'rp_only': rp_only, 'model': 'ridge CoxPH + fold-local PCA',
                         'protocol': protocol, 'metrics': measure(t, p, e), 'case_ids': ids,
                         'oof_months_order': p.tolist(), 'seed_predictions': pred.tolist(),
                         'seed_c_index': [concordance(t, a, e) for a in pred], 'folds': audit,
                         'final_params': {'k': k, 'alpha': alpha, 'coefficients': len(model.beta)},
                         'ladder': ladder(t, p, e, completeness),
                         'delta_capra': concordance(t, p, e)-concordance(t, -capra, e),
                         'delta_capra_bootstrap_95': interval(t, p, e, -capra),
                         'adds_over_anchor': concordance(t, p, e) > concordance(t, -capra, e)}
    ablations = []
    full = np.array(reports['expert_four']['oof_months_order'])
    for block in 'ASGDE':
        _, _, pred, audit = evaluate('ASGDE'.replace(block, ''))
        p = pred.mean(axis=0)
        ci = interval(t, full, e, p)
        ablations.append({'removed': block, 'metrics_without': measure(t, p, e),
                          'case_ids': ids, 'seed_predictions': pred.tolist(), 'folds': audit,
                          'delta_full_minus_without': concordance(t, full, e)-concordance(t, p, e),
                          'paired_bootstrap_95': ci, 'redundant_no_evidence': ci[0] <= 0 <= ci[1]})
    reports['expert_four']['ablations'] = ablations
    # Leave one complete score group out: tied scores share one held-out model.
    # Bounded disjoint bands also preserve ordering between held-out groups.
    p, bit = np.empty(len(t)), np.empty(len(t), int)
    calibration_folds = []
    for score in np.unique(capra):
        tr, va = np.flatnonzero(capra != score), np.flatnonzero(capra == score)
        model = Horizon().fit(capra[tr], t[tr], e[tr])
        p[va], bit[va] = model.predict(capra[va])
        calibration_folds.append({'held_out_capra': float(score), 'train': tr.tolist(), 'test': va.tolist(),
            'a': model.a, 'b': model.b, 'threshold': None if np.isinf(model.threshold) else model.threshold,
            'c_index_before': concordance(t[va], -capra[va], e[va]),
            'c_index_after': concordance(t[va], p[va], e[va])})
    event_accuracy = float((bit == e).mean()); constant_accuracy = float((e == 0).mean())
    final = Horizon().fit(capra, t, e)
    if event_accuracy <= constant_accuracy:
        final.threshold = float('inf')
    save_model('expert_five', final)
    reports['expert_five'] = {'blocks': 'riesgo del portavoz', 'spokesperson': 'expert_one, predeclared anchor; no selection on outer results',
        'protocol': {**protocol, 'outer': 'leave-one-CAPRA-score-group-out',
                     'report_prediction': 'one held-out prediction per case; all tied scores held out together',
                     'inner': '3-fold candidate scoring on outer training only',
                     'grid': {'a': [90.*np.exp(-.1*v) for v in (-.4, 0., .4)], 'b': [.1]},
                     'design_note': 'Disjoint bands and grouped CV introduced to enforce global order, not selected on time_score.'},
        'case_ids': ids, 'metrics': measure(t, p, e), 'months': p.tolist(),
        'event_oof': bit.tolist(), 'event_oof_accuracy': event_accuracy, 'constant_zero_accuracy': constant_accuracy,
        'deployed_event': 'constant 0' if np.isinf(final.threshold) else f'CAPRA >= {final.threshold}',
        'event_policy_selection_warning': 'deployment fallback chosen from OOF comparison; not an independent evaluation of selected policy',
        'time_score': time_score(t, p, e), 'constant_60_time_score': time_score(t, np.full(len(t), 60.), e),
        'delta_time_score': time_score(t, p, e)-time_score(t, np.full(len(t), 60.), e),
        'delta_c_index_pooled': concordance(t, p, e)-concordance(t, -capra, e),
        'folds': calibration_folds, 'ladder': ladder(t, p, e, completeness),
        'global_order_acceptance': concordance(t, p, e) == concordance(t, -capra, e)}
    # Rehacer también las sondas históricas; ninguna selecciona el portavoz.
    probes = {}
    for label, source in [('CAPRA-S Cox', 'capra'), ('RM Cox', 'mri'),
                          ('biopsia Cox', 'bx'), ('CAPRA-S + prostatectomia Cox', 'capra_rp')]:
        print('Nested historical probe:', label, flush=True)
        selected = np.ones(len(t), dtype=bool)
        if source == 'bx':
            selected = np.array([bool(c.embeddings.get('Biopsy slide')) for c in cases])
        subcases = [c for c, keep in zip(cases, selected) if keep]
        if source == 'capra':
            x, names = capra[selected, None], ['capra_s']
        else:
            x, names = ds.build_matrix(subcases, 'E', drop_constant=False)
            prefix = 'emb_rp_' if source == 'capra_rp' else 'emb_'+source+'_'
            keep = [i for i, name in enumerate(names) if name.startswith(prefix)]
            x, names = x[:, keep], [names[i] for i in keep]
            if source == 'capra_rp':
                x, names = np.column_stack([capra[selected], x]), ['capra_s']+names
        pred, audit = nested(x, t[selected], e[selected], names)
        probes[label] = {'n': len(subcases), 'events': int(e[selected].sum()),
                         'case_ids': [c.case_id for c in subcases], 'protocol': protocol,
                         'metrics': measure(t[selected], pred.mean(axis=0), e[selected]),
                         'seed_predictions': pred.tolist(), 'folds': audit}
    probes['prostatectomia Cox'] = {k: reports['expert_three'][k] for k in
                                    ('protocol', 'metrics', 'case_ids', 'seed_predictions', 'folds')}
    probes['prostatectomia Cox']['n'] = len(t)
    save_json(BASE/'train/artifacts/historical_probes_report.json', probes)
    for name, report in reports.items():
        save_json(BASE/'train/artifacts'/f'{name}_report.json', report)
    write_readme(reports, probes)
    print(json.dumps({name: r['metrics'] for name, r in reports.items()}, indent=2), flush=True)


def fmt(v):
    return 'no estimable' if v is None else f'{v:.4f}'


def metric_row(name, m):
    ci = m['bootstrap_95']
    return f"| {name} | {fmt(m['c_index'])} | {str([round(v,4) for v in ci]) if ci else 'no estimable'} | " + ' / '.join(fmt(v) for v in m['td_auc'].values()) + ' |'


def write_readme(reports, probes):
    lines = ['# Tarea 3 — cinco expertos (paso 5.3)', '',
        '75 casos, 19 eventos. Cox de Breslow con ridge fuerte (alpha 1/10); 5 pliegues externos × 5 semillas y 3 internos. '
        'Poda, imputación media, escalado y PCA se ajustan dentro de cada entrenamiento. '
        'Se eligen 1/2/4 componentes dentro de la CV interna. Fusión usa un componente estructurado y 1/2/4 de embeddings: máximo cinco coeficientes. '
        'Las cargas PCA también se estiman con pocos casos: limitar coeficientes no elimina el riesgo de sobreajuste.', '',
        'Cada predicción publicada promedia cinco predicciones fuera de muestra. IC percentil de 1000 remuestreos de casos; '
        'son condicionales a las predicciones, no incluyen incertidumbre de reentrenamiento ni selección. '
        'Las AUC IPCW y la semántica Harrell se extraen como funciones puras del evaluador oficial, sin ejecutar el juez.', '',
        '## Comparativa', '', '| experto | c-index | IC 95% (1000) | AUC 12 / 24 / 36 / 60 |', '|---|---:|---|---|']
    for name, r in reports.items():
        lines.append(metric_row(name, r['metrics']))
    lines += ['| baseline actual (referencia histórica) | 0.6636 | no disponible | no disponible |',
              '| CAPRA-S crudo (referencia histórica) | 0.7372 | ver ancla medida | ver ancla medida |',
              '| constante 60 meses | 0.5000 | [0.5000, 0.5000] | 0.5 / 0.5 / 0.5 / 0.5 |', '',
              'Las referencias históricas no se reestiman como si se dispusiera de sus predicciones. '
              'El score CAPRA-S y el grupo de riesgo por caso se publican en expert_one_report.json.', '']
    for name in ('expert_two', 'expert_three', 'expert_four'):
        r = reports[name]
        lines += [f"- {name}: Δ frente al ancla {r['delta_capra']:+.4f}, IC pareado {r['delta_capra_bootstrap_95']}. " +
                  ('Supera puntualmente al ancla; no implica una mejora demostrada.' if r['adds_over_anchor'] else 'No aporta frente al ancla.')]
    lines += ['', '## Sondas históricas rehechas con Cox y CV anidada', '',
              'No se conservan 4/8/16 PCs elegidos mirando la cohorte: se eligen 1/2/4 dentro de cada entrenamiento '
              'para limitar los coeficientes a cinco. La biopsia se evalúa sólo donde está disponible; su cohorte no es directamente comparable. '
              'Suelos históricos de referencia: baseline 0.6636 · CAPRA-S 0.7372 · constante 60 meses 0.5000.', '',
              '| sonda (n) | c-index | IC 95% (1000) | AUC 12 / 24 / 36 / 60 |', '|---|---:|---|---|']
    for name, probe in probes.items():
        lines.append(metric_row(f"{name} ({probe['n']})", probe['metrics']))
    lines += ['', '## Ablación por bloque', '', 'Suelos de toda esta tabla: baseline 0.6636 · CAPRA-S 0.7372 · constante 60 meses 0.5000.', '',
              '| bloque retirado | c-index sin bloque (IC 1000) | Δ completo − sin bloque (IC pareado 1000) | conclusión |', '|---|---|---|---|']
    for a in reports['expert_four']['ablations']:
        lines.append(f"| {a['removed']} | {fmt(a['metrics_without']['c_index'])} {a['metrics_without']['bootstrap_95']} | {a['delta_full_minus_without']:+.4f} {a['paired_bootstrap_95']} | " +
                     ('redundante: sin evidencia de aporte' if a['redundant_no_evidence'] else 'efecto detectado; consultar signo')+' |')
    lines += ['', 'Los bloques sin evidencia de aporte se documentan como redundantes. El modelo completo se conserva como control experimental '
              'exigido para el experto cuatro, no como recomendación de despliegue. No se selecciona una nueva combinación con esta ablación.', '',
              '## Escaleras fuera de muestra', '',
              'Tramos predeclarados por completitud de fuentes: firm ≥0.90, supports [0.75,0.90), discuss <0.75. '
              'Miden disponibilidad, no una probabilidad calibrada de acierto. Suelos: baseline 0.6636 · CAPRA-S 0.7372 · constante 60 meses 0.5000.', '',
              '| experto | tramo | n | c-index (IC 1000) |', '|---|---|---:|---|']
    for name, r in reports.items():
        for row in r['ladder']['rows']:
            lines.append(f"| {name} | {row['tier']} | {row['n']} | {fmt(row['c_index'])} {row['bootstrap_95']} |")
    lines += ['', 'Monotonía: '+', '.join(name+': '+('sí' if r['ladder']['monotone'] else 'no demostrada / no monótona') for name,r in reports.items())+'.', '',
              '## Experto cinco: horizonte y event', '']
    r = reports['expert_five']
    lines += ['Portavoz predeclarado: CAPRA-S. No se elige al ganador de la comparación usando los mismos resultados externos. '
              'El calibrador selecciona entre tres curvas 90·exp(−0.1·(CAPRA+offset)), offset −0.4/0/0.4, usando sólo el entrenamiento externo; '
              'event selecciona entre constante 0, CAPRA≥7 y CAPRA≥9. Las decisiones se miden en el pliegue externo.', '',
              f"time_score OOF: {r['time_score']:.4f}; constante 60: {r['constant_60_time_score']:.4f}; Δ {r['delta_time_score']:+.4f}.", '',
              f"event OOF: {r['event_oof_accuracy']:.4f}; constante 0: {r['constant_zero_accuracy']:.4f}; entrega: {r['deployed_event']}.", '',
              f"Δ c-index OOF global: {r['delta_c_index_pooled']:+.4f}. "
              'Validación del calibrador: leave-one-CAPRA-score-group-out. Cada grupo de empates comparte un calibrador '
              'que no ha visto sus etiquetas; bandas disjuntas garantizan el orden entre grupos enteros. '
              'Esta validación difiere de la CV estratificada de Cox. La restricción se introdujo para garantizar '
              'invariancia global, sin elegirla por time_score. Las bandas restringen la calidad del horizonte. '
              + ('Aceptación global satisfecha.' if r['global_order_acceptance'] else '**NO se cumple el criterio global Δ c-index = 0.0000.**'), '',
              'El artefacto final usa una única curva estrictamente decreciente y conserva el orden en inferencia. '
              'Las cifras de entrenamiento final no se presentan como rendimiento. No se implementa el paso siguiente.', '',
              '## Reproducción', '', 'Desde la raíz:', '```bash',
              'OPENBLAS_NUM_THREADS=1 .venv/bin/python version_final_reto/task_3/experts_3/train/run_training.py',
              '.venv/bin/python -m pytest -q version_final_reto/task_3/experts_3/train/test_acceptance.py',
              '.venv/bin/python -m pytest -q', '```', '',
              'Cada train_expert_N.py ejecuta el protocolo compartido completo para mantener comparables pliegues y ablaciones. '
              'Los .joblib usan pickle sin compresión (compatible con joblib.load), sin dependencia nueva; '
              'para cargar clases se debe añadir train/ a sys.path y luego pickle.load. Sólo cargar artefactos de confianza. Horizon acepta el score CAPRA-S, mayor = más riesgo, y devuelve (months, event). CoxPipeline.risk devuelve log-hazard, mayor = más riesgo; los valores negativos usados para c-index no son horizontes clínicos.', '']
    (BASE/'README.md').write_text('\n'.join(lines))
