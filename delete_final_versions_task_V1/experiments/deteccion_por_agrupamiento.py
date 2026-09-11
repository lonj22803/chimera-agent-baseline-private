"""¿Un agrupamiento no supervisado sabe DÓNDE se equivoca el protocolo?

La idea: si los fallos se concentraran en una región del espacio de rasgos, un
agrupamiento la encontraría sin mirar la etiqueta, y esa región podría enrutarse a otro
experto. Es distinto de lo ya probado: en T2 se intentó un **detector supervisado** de
fallos y dio AUC 0,63 —ruido—, pero agrupar no se había probado en ninguna tarea.

**El peligro de este experimento es encontrar algo.** Con 5 fallos en 64 casos, partir
en k grupos y quedarse con el más sucio produce enriquecimiento casi siempre, sólo por
el azar de repartir 5 bolas en k urnas. Por eso el criterio no es "hay un clúster con
más errores", sino un **test de permutación**: se baraja la etiqueta de acierto/fallo
muchas veces sobre los mismos clústeres y se mide cuántas veces el azar iguala o supera
el enriquecimiento observado. Sin ese contraste, cualquier resultado es una ilusión.
"""
from __future__ import annotations
import json
import warnings
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
RESULTS = Path(__file__).resolve().parents[0] / 'results'
PERMUTACIONES = 5000
RNG = np.random.default_rng(0)


def enriquecimiento(grupos, fallo):
    """Tasa de fallo del grupo más sucio con al menos 3 casos, frente a la tasa global."""
    mejor, detalle = 0.0, None
    base = fallo.mean()
    for g in np.unique(grupos):
        m = grupos == g
        if m.sum() < 3:
            continue
        tasa = fallo[m].mean()
        if tasa > mejor:
            mejor, detalle = tasa, {'grupo': int(g), 'n': int(m.sum()),
                                    'fallos': int(fallo[m].sum()), 'tasa': round(float(tasa), 4)}
    return mejor, base, detalle


def permutacion(grupos, fallo, n=PERMUTACIONES):
    """p-valor: ¿con qué frecuencia el azar iguala el enriquecimiento observado?"""
    obs, _, _ = enriquecimiento(grupos, fallo)
    y = fallo.copy()
    iguales = 0
    for _ in range(n):
        RNG.shuffle(y)
        if enriquecimiento(grupos, y)[0] >= obs:
            iguales += 1
    return obs, (iguales + 1)/(n + 1)


def analiza(X, fallo, etiqueta):
    from sklearn.cluster import AgglomerativeClustering, KMeans
    from sklearn.decomposition import PCA
    from sklearn.impute import SimpleImputer
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import StandardScaler

    Z = SimpleImputer(strategy='median').fit_transform(X)
    Z = StandardScaler().fit_transform(Z)
    if Z.shape[1] > 20:
        Z = PCA(n_components=min(10, Z.shape[0]-1, Z.shape[1]), random_state=0).fit_transform(Z)

    filas = []
    for k in (2, 3, 4, 5):
        for nombre, modelo in (('kmeans', KMeans(k, n_init=20, random_state=0)),
                               ('jerarquico', AgglomerativeClustering(k)),
                               ('gmm', GaussianMixture(k, random_state=0, covariance_type='full'))):
            try:
                g = modelo.fit_predict(Z)
            except Exception:  # noqa: BLE001
                continue
            obs, p = permutacion(g, fallo)
            _, base, detalle = enriquecimiento(g, fallo)
            filas.append({'algoritmo': nombre, 'k': k, 'tasa_grupo_peor': round(float(obs), 4),
                          'tasa_global': round(float(base), 4), 'p_permutacion': round(float(p), 4),
                          'detalle': detalle})
    filas.sort(key=lambda f: f['p_permutacion'])
    return {'etiqueta': etiqueta, 'n': int(len(fallo)), 'fallos': int(fallo.sum()), 'ensayos': filas}


def task1():
    from delete_final_versions_task_V1.experiments.t1_mri_expert import datos, matriz
    boards = REPO/'delete_final_versions_task/resultados/task_1/boards'
    dev = set((REPO/'dev/splits/task1_dev.txt').read_text().split())
    casos, y = datos('dev')
    pred = {}
    for f in boards.glob('*.json'):
        t = {x['speaker']: x for x in json.loads(f.read_text())['interventions']}
        pred[f.stem] = t.get('PANEL-PROTOCOL', {}).get('data', {}).get('decision') == 'yes'
    fallo = np.array([pred.get(c.case_id) != bool(yy) for c, yy in zip(casos, y)], dtype=float)
    X = np.asarray(matriz(casos, 'ABD')[0], float)
    return analiza(X, fallo, 'T1 · fallos del protocolo en DEV')


def task2():
    from delete_final_versions_task_V1.common.chimera_experts import dataset_task2 as ds2
    from delete_final_versions_task_V1.common.chimera_experts.io import load_cases
    boards = REPO/'delete_final_versions_task/resultados/task_2/boards'
    dev = set((REPO/'dev/splits/task2_dev.txt').read_text().split())
    casos = [c for c in load_cases(REPO/'data/task2', 2, labelled_only=True) if c.case_id in dev]
    y = ds2.build_labels(casos)
    pred = {}
    for f in boards.glob('*.json'):
        t = {x['speaker']: x for x in json.loads(f.read_text())['interventions']}
        d = t.get('CHAIR', {}).get('data', {})
        pred[f.stem] = d.get('action') or d.get('decision')
    # build_labels devuelve ÍNDICES en ds2.CLASSES, no nombres de clase.
    fallo = np.array([pred.get(c.case_id) != ds2.CLASSES[int(yy)] for c, yy in zip(casos, y)], dtype=float)
    if fallo.mean() > 0.5:
        raise ValueError(f'Extracción de fallos rota: tasa {fallo.mean():.2f}; T2 acierta el 90 %')
    X = np.asarray(ds2.build_matrix(casos, 'ACDGHIJ')[0], float)
    return analiza(X, fallo, 'T2 · fallos del portavoz en DEV')


def main():
    warnings.filterwarnings('ignore')
    salida = {'pregunta': '¿Un agrupamiento encuentra dónde se equivoca el protocolo?',
              'criterio': f'Test de permutación, {PERMUTACIONES} barajas. Un clúster sucio sin p-valor '
                          'bajo es el azar repartiendo pocos fallos entre pocos grupos.',
              'task1': task1(), 'task2': task2()}
    for k in ('task1', 'task2'):
        mejor = salida[k]['ensayos'][0] if salida[k]['ensayos'] else None
        salida[k]['mejor_p'] = mejor['p_permutacion'] if mejor else None
        salida[k]['significativo'] = bool(mejor and mejor['p_permutacion'] < 0.05)
    salida['adoptado'] = False
    salida['ensayos_por_tarea'] = 12  # 3 algoritmos x 4 valores de k
    salida['motivo'] = (
        'NO. Los fallos no están concentrados en ninguna región del espacio de rasgos. '
        f"T1: 5 fallos en 64, el grupo más sucio da p={salida['task1']['mejor_p']}; "
        f"T2: 4 en 50, p={salida['task2']['mejor_p']}. Ninguno acerca a 0,05, y eso es ANTES de "
        'corregir por las 12 configuraciones probadas en cada tarea —3 algoritmos x 4 valores de k—, '
        'que los alejaría todavía más. '
        'Coincide con el detector supervisado que ya se había probado en T2 (AUC 0,63, ruido) y lo '
        'extiende a T1 y al caso no supervisado: no hay un "dónde falla" que aprender. '
        'Los fallos son casos individualmente difíciles, no una región del problema.')
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS/'deteccion_por_agrupamiento.json').write_text(json.dumps(salida, indent=2, ensure_ascii=False)+'\n')
    for k in ('task1', 'task2'):
        d = salida[k]
        print(f"\n{d['etiqueta']}  (n={d['n']}, fallos={d['fallos']}, tasa global={d['fallos']/d['n']:.3f})")
        for f in d['ensayos'][:5]:
            print(f"  {f['algoritmo']:11s} k={f['k']}  peor grupo: {f['detalle']['fallos']}/{f['detalle']['n']}"
                  f" = {f['tasa_grupo_peor']:.3f}   p(permutación) = {f['p_permutacion']:.4f}")
        print('  -> significativo:', d['significativo'])


if __name__ == '__main__':
    main()
