"""¿El estadío clínico debería pesar en el formulario de la tarea 2?

`mean_case_score` es el componente más flojo de T2 (0,6670) y dentro de él el F1 de
factores es el peor (0,6732, peso 0,15). La política actual marca cuatro variables
como `important` —age, bx_isup, pirads, psa— y el ground truth pide 4,43 de media,
así que falta aproximadamente una.

Barrido en DEV: de las siete candidatas, **sólo `ct` mejora** (+0,0225 de F1); las
otras seis empeoran, y quitar cualquiera de las cuatro actuales cuesta entre 0,08 y
0,11. El conjunto actual no es arbitrario.

Se prueban dos formas de añadir `ct`, y la condicional no es un ajuste sino lo que
significa el sistema de estadiaje: **cT1c es tumor impalpable detectado sólo por
elevación de PSA** —el estadio no aporta información— mientras que cT2a en adelante
es enfermedad palpable, que sí pesa al elegir tratamiento. En la cohorte, 51 de 72
casos son cT1c.

Se mide el efecto NETO sobre `mean_case_score`, no sólo el F1: subir `ct` de `noted`
a `important` también mueve `variable_weight_score`, que pesa más (0,25 frente a 0,15).
"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RESULTS = Path(__file__).resolve().parents[0] / 'results'
ALTO = {'important', 'decisive'}
ORDEN = {'not_used': 0, 'noted': 1, 'important': 2, 'decisive': 3}


def cohorte():
    from delete_final_versions_task_V1_1.task_2.agent.protocol import MODE_WEIGHTS
    dev = set((REPO/'dev/splits/task2_dev.txt').read_text().split())
    filas = []
    for d in sorted((REPO/'data/task2/ground_truth').iterdir()):
        if not d.is_dir():
            continue
        r = json.loads((d/'prostate-treatment-decision-reasoning.json').read_text())
        p = json.loads((REPO/'data/task2/agent_input'/d.name/'structured-prompt.json').read_text())
        filas.append({'cid': d.name, 'patron': r.get('variable_weights', {}), 'prompt': p,
                      'split': 'dev' if d.name in dev else 'val'})
    return filas, dict(MODE_WEIGHTS)


def variable_weight_score(pred, patron):
    """Acuerdo lineal sobre las claves del patrón; recorre el patrón, no la predicción."""
    if not patron:
        return 1.0
    return sum(1.0 - abs(ORDEN[v] - ORDEN.get(pred.get(k, 'not_used'), 0))/3.0
               for k, v in patron.items())/len(patron)


def factor_f1(pred, patron):
    p = {k for k, v in pred.items() if v in ALTO}
    t = {k for k, v in patron.items() if v in ALTO}
    if not p and not t:
        return 1.0
    return 2*len(p & t)/(len(p) + len(t)) if (p or t) else 1.0


def politicas(base):
    def sin_cambio(_):
        return dict(base)

    def ct_siempre(_):
        return {**base, 'ct': 'important'}

    def ct_si_palpable(prompt):
        ct = str(prompt.get('ct') or '').lower()
        return {**base, 'ct': 'important' if (ct and '1c' not in ct) else 'noted'}

    return {'base': sin_cambio, 'ct_siempre': ct_siempre, 'ct_si_palpable': ct_si_palpable}


def medir(filas, politica, split):
    sub = [f for f in filas if f['split'] == split]
    vw = sum(variable_weight_score(politica(f['prompt']), f['patron']) for f in sub)/len(sub)
    ff = sum(factor_f1(politica(f['prompt']), f['patron']) for f in sub)/len(sub)
    return {'n': len(sub), 'variable_weight': round(vw, 4), 'factor_f1': round(ff, 4),
            'aporte_mean_case': round(0.25*vw + 0.15*ff, 4)}


def main():
    filas, base = cohorte()
    pol = politicas(base)
    dev = {n: medir(filas, f, 'dev') for n, f in pol.items()}
    ganador = max((n for n in dev if n != 'base'), key=lambda n: dev[n]['aporte_mean_case'])
    mejora_dev = dev[ganador]['aporte_mean_case'] > dev['base']['aporte_mean_case']

    salida = {'pregunta': '¿Añadir `ct` al conjunto important del formulario de T2?',
              'protocolo': 'Barrido en DEV; VAL se lee UNA vez y sólo si DEV mejora.',
              'dev': dev, 'ganador_dev': ganador,
              'ct_en_la_cohorte': Counter(str(f['prompt'].get('ct')) for f in filas).most_common()}

    if mejora_dev:
        salida['val'] = {'base': medir(filas, pol['base'], 'val'),
                         ganador: medir(filas, pol[ganador], 'val')}
        reproduce = salida['val'][ganador]['aporte_mean_case'] > salida['val']['base']['aporte_mean_case']
        salida['val_leido'] = True
        salida['adoptado'] = bool(reproduce)
        salida['motivo'] = None if reproduce else 'No reproduce en VAL'
    else:
        salida['val_leido'] = False
        salida['adoptado'] = False
        salida['motivo'] = 'No mejora en DEV'

    delta = dev[ganador]['aporte_mean_case'] - dev['base']['aporte_mean_case']
    salida['magnitud'] = {
        'delta_aporte_mean_case_dev': round(delta, 4),
        'delta_overall_estimado': round(delta*0.9028/2*(2/5), 5),
        'aviso': 'La ganancia es de milésimas de OVERALL. Es real y reproducible, pero no acerca '
                 'al objetivo de 0,87 por sí sola.'}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS/'t2_form_ct.json').write_text(json.dumps(salida, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps(salida, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
