"""Comparación pareada de 4.3; consume el juez ya ejecutado, nunca lo invoca."""
import json
from pathlib import Path

from scipy.stats import binomtest

from dev.score_local import load_evaluator, score_task
from delete_final_versions_task_V1_1.task_2.agent.paths import DATA, EVAL_REPO, REPO, RUNS


def signs(a, b, key):
    aa, bb = {r['case_id']: r for r in a}, {r['case_id']: r for r in b}
    assert aa.keys() == bb.keys(), 'Las cohortes deben ser idénticas'
    pairs = []
    for cid in sorted(aa):
        x, y = aa[cid].get(key), bb[cid].get(key)
        if x is None or y is None:
            continue
        pairs.append({'case_id': cid, 'junta': x, 'reference': y, 'delta': x-y})
    wins = sum(r['delta'] > 1e-12 for r in pairs)
    losses = sum(r['delta'] < -1e-12 for r in pairs)
    return {'metric': key, 'n': len(pairs), 'wins': wins, 'losses': losses,
            'ties': len(pairs)-wins-losses,
            'p_two_sided': float(binomtest(wins, wins+losses).pvalue) if wins+losses else 1.0,
            'mean_delta': sum(r['delta'] for r in pairs)/len(pairs) if pairs else None,
            'pairs': pairs}


def main():
    ev = load_evaluator(EVAL_REPO)
    junta = score_task(ev, REPO/'data', RUNS/'labeled'/'output', 2, None, True)
    baseline = score_task(ev, REPO/'data', REPO/'test'/'output', 2, None, True)
    assert junta['_scored'] == baseline['_scored'] == 72, 'No comparar una corrida incompleta'
    rule = []
    for gt in ev.load_ground_truth_records(DATA/'ground_truth', 'task2'):
        cid = ev.get_case_id(gt)
        payload = json.loads((DATA/'agent_input'/cid/'structured-prompt.json').read_text())
        grade = float(payload.get('bx_isup') or 0)
        action = 'continued_surveillance' if grade <= 0 else 'active_surveillance' if grade == 1 else 'active_treatment'
        score, _, _, _ = ev.decision_score('treatment', gt, {'treatment_recommendation': {'primary': action}})
        rule.append({'case_id': cid, 'decision_score': score, 'action': action})
    result = {
        'method': 'Prueba binomial exacta bilateral por caso; empates excluidos, tolerancia 1e-12; sin corrección por multiplicidad. Cohorte de entrenamiento: no demuestra generalización.',
        'rule_scope': 'Regla ISUP sólo define decisión; no se inventa una nota ni un formulario para darle ranking con o sin juez.',
        'no_judge': {
            'junta': junta, 'baseline': baseline,
            'vs_baseline_case_score': signs(junta['_rows'], baseline['_rows'], 'case_score'),
            'vs_baseline_decision': signs(junta['_rows'], baseline['_rows'], 'decision_score'),
            'vs_isup_decision': signs(junta['_rows'], rule, 'decision_score')},
        'isup': {'decision_accuracy': sum(r['decision_score'] for r in rule)/len(rule), 'rows': rule}}
    jp, bp = RUNS/'judge'/'entrega.json', RUNS/'judge'/'baseline.json'
    if jp.exists() and bp.exists():
        j, b = json.loads(jp.read_text()), json.loads(bp.read_text())
        assert len(j['rows']) == len(b['rows']) == 72
        result['judge'] = {'junta': j['aggregate'], 'baseline': b['aggregate'],
                           'vs_baseline_case_score': signs(j['rows'], b['rows'], 'case_score'),
                           'vs_baseline_decision': signs(j['rows'], b['rows'], 'decision_score')}
    (RUNS/'comparison_4_3.json').write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps({k:v for k,v in result['no_judge'].items() if k.startswith('vs_')}, default=str, indent=2))


if __name__ == '__main__':
    main()
