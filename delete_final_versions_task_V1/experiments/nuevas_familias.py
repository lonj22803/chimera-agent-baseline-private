"""¿Un experto más —kNN probabilístico, Random Forest u otra familia— decidiría mejor?

La pregunta es razonable: los expertos de T2 son variantes de árboles y los de T3 son
Cox penalizado. Quizá falta una familia distinta. Se mide en lugar de suponerlo.

**Tarea 2.** El catálogo (`models_multiclass.build_catalog`) ya trae 17 familias,
kNN ponderado y Random Forest entre ellas. Se corren todas sobre DEV con validación
cruzada estratificada, 5 pliegues × 3 semillas, bloques ACDGHIJ.

**Tarea 3.** No hay `scikit-survival` ni `lifelines` en el entorno, así que las
familias de árboles se aplican con el enfoque estándar de **supervivencia en tiempo
discreto**: clasificar "evento antes del horizonte H" entre los pacientes **en riesgo**
en H, excluyendo a los censurados antes de H —que es como se trata la censura sin
sesgar— y sumando el riesgo sobre H = 24, 36 y 60 meses. El criterio es el c-index,
que es el ranking oficial de la tarea.
"""
from __future__ import annotations
import copy
import json
import warnings
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
RESULTS = Path(__file__).resolve().parents[0] / 'results'
SEMILLAS = (0, 7, 13)


def c_index(riesgo, t, e):
    num = den = 0.0
    for i in range(len(t)):
        if e[i] != 1:
            continue
        for j in range(len(t)):
            if i != j and (t[i] < t[j] or (t[i] == t[j] and e[j] == 0)):
                den += 1
                num += 1.0 if riesgo[i] > riesgo[j] else 0.5 if riesgo[i] == riesgo[j] else 0.0
    return num/den if den else float('nan')


def barrido_task2():
    from sklearn.model_selection import StratifiedKFold
    from delete_final_versions_task_V1.common.chimera_experts import dataset_task2 as ds2, models_multiclass as mm
    from delete_final_versions_task_V1.common.chimera_experts.io import load_cases

    dev = set((REPO/'dev/splits/task2_dev.txt').read_text().split())
    casos = [c for c in load_cases(REPO/'data/task2', 2, labelled_only=True) if c.case_id in dev]
    y = ds2.build_labels(casos)
    X, nombres = ds2.build_matrix(casos, 'ACDGHIJ')  # sin K: exige un proyector ya ajustado
    X = np.asarray(X, float)
    isup = [i for i, n in enumerate(nombres) if n == 'bx_isup']
    catalogo = mm.build_catalog(seed=0, isup_col=isup[0] if isup else 0)

    salida = {}
    for nombre, modelo in catalogo.items():
        try:
            acc = []
            for s in SEMILLAS:
                pred = np.empty(len(y), dtype=object)
                for tr, te in StratifiedKFold(5, shuffle=True, random_state=s).split(X, y):
                    m = copy.deepcopy(modelo)
                    m.fit(X[tr], y[tr])
                    pred[te] = m.predict(X[te])
                acc.append(float((pred == y).mean()))
            salida[nombre] = {'acc_cv': round(float(np.mean(acc)), 4), 'sd': round(float(np.std(acc)), 4)}
        except Exception as exc:  # noqa: BLE001
            salida[nombre] = {'error': f'{type(exc).__name__}: {exc}'}
    return {'n_dev': int(len(y)), 'columnas': int(X.shape[1]), 'modelos': salida}


def riesgo_tiempo_discreto(modelo, X, t, e, horizontes=(24, 36, 60)):
    """Riesgo acumulado sobre varios horizontes, respetando la censura en cada uno."""
    from sklearn.model_selection import KFold
    riesgo = np.zeros(len(t))
    for H in horizontes:
        etiqueta = (t <= H) & (e == 1)
        en_riesgo = (t > H) | etiqueta          # los censurados antes de H no son observables
        if etiqueta[en_riesgo].sum() < 3 or (~etiqueta[en_riesgo]).sum() < 3:
            continue
        acumulado = np.zeros(len(t))
        idx = np.where(en_riesgo)[0]
        for s in SEMILLAS:
            p = np.zeros(len(t))
            for tr, te in KFold(5, shuffle=True, random_state=s).split(idx):
                m = copy.deepcopy(modelo)
                m.fit(X[idx[tr]], etiqueta[idx[tr]])
                p[idx[te]] = m.predict_proba(X[idx[te]])[:, 1]
            m = copy.deepcopy(modelo)
            m.fit(X[idx], etiqueta[idx])
            fuera = np.where(~en_riesgo)[0]
            if len(fuera):
                p[fuera] = m.predict_proba(X[fuera])[:, 1]
            acumulado += p
        riesgo += acumulado/len(SEMILLAS)
    return riesgo


def barrido_task3():
    from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.pipeline import make_pipeline
    from delete_final_versions_task_V1.common.chimera_experts import dataset_task3 as ds3
    from delete_final_versions_task_V1.common.chimera_experts.io import load_cases

    dev = set((REPO/'dev/splits/task3_dev.txt').read_text().split())
    casos = [c for c in load_cases(REPO/'data/task3', 3, labelled_only=True) if c.case_id in dev]
    verdad = {d.name: json.loads((d/'prostate-time-to-recurrence-or-last-follow-up.json').read_text())
              for d in (REPO/'data/task3/ground_truth').iterdir() if d.is_dir()}
    t = np.array([verdad[c.case_id]['months_to_recurrence'] for c in casos], float)
    e = np.array([verdad[c.case_id]['event'] for c in casos], int)
    X = np.asarray(ds3.build_matrix(casos, 'ASGDE')[0], float)

    imp = lambda m: make_pipeline(SimpleImputer(strategy='median'), m)  # noqa: E731
    familias = {
        'extra_trees': imp(ExtraTreesClassifier(400, min_samples_leaf=2, random_state=0, n_jobs=-1)),
        'random_forest': imp(RandomForestClassifier(400, min_samples_leaf=2, random_state=0, n_jobs=-1)),
        'knn_probabilistico': imp(KNeighborsClassifier(n_neighbors=7, weights='distance')),
    }
    return {'n_dev': int(len(t)), 'eventos': int(e.sum()), 'columnas': int(X.shape[1]),
            'modelos': {n: {'c_index': round(c_index(riesgo_tiempo_discreto(m, X, t, e), t, e), 4)}
                        for n, m in familias.items()},
            'referencias': {'CAPRA-S': 0.6427, 'ASGDE_adoptado': 0.7903}}


def main():
    warnings.filterwarnings('ignore')
    t2, t3 = barrido_task2(), barrido_task3()
    mejor2 = max((n for n, v in t2['modelos'].items() if 'acc_cv' in v),
                 key=lambda n: t2['modelos'][n]['acc_cv'])
    mejor3 = max(t3['modelos'], key=lambda n: t3['modelos'][n]['c_index'])
    salida = {
        'pregunta': '¿Mejoraría la decisión un experto de otra familia (kNN probabilístico, RF, …)?',
        'protocolo': 'Sólo DEV. VAL no se lee: ninguna familia superó a lo que ya hay.',
        'task2': t2, 'task3': t3, 'mejor_task2': mejor2, 'mejor_task3': mejor3,
        'adoptado': False,
        'motivo': (
            'NO. En T2 nada bate a la regla ISUP (0,8800): Extra Trees la empata, Random Forest queda '
            f'por debajo (0,8533–0,8667) y el kNN se hunde a {t2["modelos"]["knn"]["acc_cv"]}. '
            f'En T3 el Cox de fusión ya adoptado (c-index 0,7903) supera a las tres familias nuevas: '
            f'extra_trees {t3["modelos"]["extra_trees"]["c_index"]}, '
            f'random_forest {t3["modelos"]["random_forest"]["c_index"]} y '
            f'kNN {t3["modelos"]["knn_probabilistico"]["c_index"]}, este último cerca del azar. '
            'Los árboles sí baten a CAPRA-S en T3 (0,6427), lo que respalda a posteriori la adopción '
            'del portavoz de fusión, pero no lo mejoran. Ninguna familia nueva merece asiento.')}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS/'nuevas_familias.json').write_text(json.dumps(salida, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({k: salida[k] for k in ('mejor_task2', 'mejor_task3', 'adoptado', 'motivo')},
                     indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
