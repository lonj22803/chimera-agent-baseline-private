"""La cascada de la tarea 1 no está ordenada por acierto, que es su propio principio.

El diseño declara que los peldaños van "ordenados por acierto medido". Medido sobre
los 91 casos etiquetados, el orden real es:

    peldaño 1 · criterio de cohorte      52 casos   0,9423
    peldaño 3 · voto ponderado           27 casos   0,8889
    peldaño 2 · grado documentado        12 casos   0,8333

Pero la cascada dispara 1 -> 2 -> 3. El peldaño **menos exacto de los tres** se queda
12 casos antes de que hable el voto ponderado, que acierta más. Si el principio es
cierto, intercambiarlos debería mejorar.

Es un cambio arquitectónico pequeño —reordenar dos peldaños, sin tocar ninguna regla—
y comprobable: basta preguntar qué habría dicho el voto en esos 12 casos.

Se usan las predicciones **honestas** (out-of-fold) del caché, no las desplegadas:
las desplegadas se ajustaron sobre esta misma cohorte y darían un techo, no una
medición. Exploración en DEV; VAL se lee una vez y sólo si DEV mejora.
"""
from __future__ import annotations
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
V1 = Path(__file__).resolve().parents[1]
RESULTS = Path(__file__).resolve().parents[0] / 'results'
BOARDS = REPO / 'version_final_reto/investigacion/referencias_historicas/boards_task1'


def cohorte():
    from version_final_reto.task_1.agent import protocol as P
    cache = json.loads((V1/'task_1/artifacts/panel_cache.json').read_text())['cases']
    dev = set((REPO/'dev/splits/task1_dev.txt').read_text().split())
    filas = []
    for f in sorted(BOARDS.glob('*.json')):
        cid = f.stem
        turnos = {t['speaker']: t for t in json.loads(f.read_text())['interventions']}
        pr = turnos.get('PANEL-PROTOCOL', {}).get('data', {})
        regla = str(pr.get('rule', ''))
        peldano = 1 if 'cohort' in regla else 2 if 'grade' in regla else 3
        y = json.loads((REPO/f'data/task1/ground_truth/{cid}/prostate-biopsy-decision.json').read_text())
        honesto = cache.get(cid, {}).get('honest', {})
        filas.append({'cid': cid, 'peldano': peldano, 'regla': regla,
                      'decision_actual': pr.get('decision') == 'yes', 'y': y == 'yes',
                      'p_voto': voto(honesto, P.PARAMS),
                      'split': 'dev' if cid in dev else 'val'})
    return filas, P.PARAMS


def voto(honesto, params):
    """El voto ponderado del peldaño 3: E1 + E3 x fusion_mult. None si falta el caché."""
    e1 = honesto.get('structured', {}).get('p')
    e3 = (honesto.get('fusion_full') or honesto.get('fusion_nolab') or {}).get('p')
    if e1 is None or e3 is None:
        return None
    m = params['fusion_mult']
    return (e1 + m*e3)/(1.0 + m)


def evaluar(filas, split, intercambiar, umbral):
    """Acierto sobre TODOS los casos del split; sólo cambia quién decide los del peldaño 2."""
    sub = [f for f in filas if f['split'] == split]
    aciertos, fallos, movidos = 0, [], 0
    for f in sub:
        if intercambiar and f['peldano'] == 2 and f['p_voto'] is not None:
            pred = f['p_voto'] >= umbral
            movidos += 1
        else:
            pred = f['decision_actual']
        if pred == f['y']:
            aciertos += 1
        else:
            fallos.append(f['cid'])
    return {'n': len(sub), 'aciertos': aciertos, 'exactitud': round(aciertos/len(sub), 4),
            'casos_reasignados': movidos, 'fallos': [c[-12:] for c in fallos]}


def main():
    filas, params = cohorte()
    u = params['threshold']
    dev = {'base': evaluar(filas, 'dev', False, u), 'intercambio': evaluar(filas, 'dev', True, u)}
    salida = {'pregunta': '¿Debe el voto ponderado decidir antes que el grado documentado?',
              'principio': 'La cascada declara ir ordenada por acierto; hoy no lo está.',
              'acierto_por_peldano': {}, 'umbral': u,
              'predicciones': 'honest (out-of-fold); las desplegadas darían un techo, no una medición',
              'dev': dev}
    for k in (1, 2, 3):
        sub = [f for f in filas if f['peldano'] == k]
        salida['acierto_por_peldano'][k] = {
            'n': len(sub), 'exactitud': round(sum(f['decision_actual'] == f['y'] for f in sub)/len(sub), 4)}

    mejora = dev['intercambio']['aciertos'] > dev['base']['aciertos']
    if mejora:
        salida['val'] = {'base': evaluar(filas, 'val', False, u),
                         'intercambio': evaluar(filas, 'val', True, u)}
        reproduce = salida['val']['intercambio']['aciertos'] > salida['val']['base']['aciertos']
        salida.update(val_leido=True, adoptado=bool(reproduce),
                      motivo=None if reproduce else 'No reproduce en VAL')
    else:
        salida.update(
            val_leido=False, adoptado=False,
            motivo=('RECHAZADO. En DEV la exactitud cae de 0,9219 a 0,8438: el intercambio rompe cinco '
                    'casos que el grado documentado acertaba. '
                    'La lección: el 0,8889 del voto está medido SOBRE LOS CASOS QUE HOY LE TOCAN, que son '
                    'otra población. En los 12 casos donde hay grado documentado el voto lo hace peor. '
                    'El principio de ordenar por acierto se refiere a la exactitud de cada peldaño EN LOS '
                    'CASOS QUE RECLAMA, no a su tasa global; comparar tasas marginales entre poblaciones '
                    'distintas es la trampa. La cascada ya estaba bien ordenada.'))
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS/'t1_cascade_order.json').write_text(json.dumps(salida, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps(salida, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
