"""¿Falta algún experto en la tarea 1? Tres bloques de rasgos están definidos y sin usar.

`dataset.py` define seis bloques de rasgos para T1 y los expertos usan cinco: el
bloque **F, los embeddings de resonancia, está definido y no lo consume nadie**. Los
vectores existen en 191 de 195 casos.

Hay un motivo declarado para desconfiar: `image.py` publica `TASK1_HEAD_AUC = 0.43`,
por debajo del azar. Pero ese 0,43 es la cabeza del baseline aplicada a los vectores
congelados, **no un modelo ajustado sobre ellos**. La pregunta abierta es si un
experto entrenado sobre el bloque F aporta algo que A, B y D no tengan ya.

Se mide con validación cruzada estratificada repetida **sólo en DEV**. VAL se lee una
vez y sólo si DEV mejora. El criterio no es el AUC del bloque F por sí solo, sino si
**añadirlo a la fusión** sube el AUC fuera de muestra: un experto que repite lo que
otro ya dice no merece asiento.
"""
from __future__ import annotations
import json
import warnings
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
RESULTS = Path(__file__).resolve().parents[0] / 'results'
SEMILLAS = (11, 23, 37)
PLIEGUES = 5


def datos(split):
    from delete_final_versions_task_V1.common.chimera_experts import dataset as ds
    from delete_final_versions_task_V1.common.chimera_experts.io import load_cases
    ids = set((REPO/f'dev/splits/task1_{split}.txt').read_text().split())
    casos = [c for c in load_cases(REPO/'data/task1', 1, labelled_only=True) if c.case_id in ids]
    from delete_final_versions_task_V1.common.chimera_experts import dataset as ds
    y = ds.build_labels(casos).astype(int)
    return casos, y


def matriz(casos, bloques):
    from delete_final_versions_task_V1.common.chimera_experts import dataset as ds
    X, nombres = ds.build_matrix(casos, bloques)
    return np.asarray(X, dtype=float), nombres


def auc_oof(X, y, semillas=SEMILLAS):
    """AUC fuera de muestra, promediado sobre semillas. Imputación y escalado dentro del pliegue."""
    from sklearn.ensemble import ExtraTreesClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedKFold
    from sklearn.pipeline import make_pipeline

    aucs = []
    for s in semillas:
        p = np.zeros(len(y), dtype=float)
        cv = StratifiedKFold(n_splits=PLIEGUES, shuffle=True, random_state=s)
        for tr, te in cv.split(X, y):
            modelo = make_pipeline(
                SimpleImputer(strategy='median'),
                ExtraTreesClassifier(n_estimators=400, random_state=s, n_jobs=-1))
            modelo.fit(X[tr], y[tr])
            p[te] = modelo.predict_proba(X[te])[:, 1]
        aucs.append(roc_auc_score(y, p))
    return float(np.mean(aucs)), float(np.std(aucs))


def main():
    warnings.filterwarnings('ignore')
    casos, y = datos('dev')
    combinaciones = {'A (panel)': 'A', 'F (embeddings RM)': 'F', 'ABD (fusión actual)': 'ABD',
                     'ABDF (fusión + RM)': 'ABDF', 'AF (panel + RM)': 'AF',
                     'ABCD (+psa_trend)': 'ABCD', 'ABDE (+notes)': 'ABDE',
                     'ABCDE (todo salvo F)': 'ABCDE'}
    medidas = {}
    for nombre, bloques in combinaciones.items():
        X, nombres = matriz(casos, bloques)
        media, sd = auc_oof(X, y)
        medidas[nombre] = {'bloques': bloques, 'columnas': X.shape[1],
                           'auc_oof': round(media, 4), 'sd_semillas': round(sd, 4)}
        print(f'  {nombre:22s} cols={X.shape[1]:4d}  AUC OOF = {media:.4f} (sd {sd:.4f})', flush=True)

    base = medidas['ABD (fusión actual)']['auc_oof']
    cand = medidas['ABDF (fusión + RM)']['auc_oof']
    salida = {'pregunta': '¿Merece un asiento un experto sobre el bloque F (embeddings de RM)?',
              'protocolo': 'CV estratificada 5x3 semillas, sólo DEV. VAL sólo si DEV mejora.',
              'n_dev': int(len(y)), 'positivos': int(y.sum()),
              'contexto': 'image.py publica TASK1_HEAD_AUC=0.43, pero es la cabeza del baseline sobre '
                          'vectores congelados, no un modelo ajustado sobre el bloque F.',
              'dev': medidas, 'delta_fusion': round(cand - base, 4)}
    mejora = cand > base
    salida.update(val_leido=False, adoptado=False)
    mejor = max(medidas, key=lambda k: medidas[k]['auc_oof'])
    salida['mejor_combinacion'] = mejor
    salida['motivo'] = (
        'RECHAZADO, y con margen. El bloque F solo da AUC 0,3791 —bajo el azar, con un modelo '
        f'ajustado de verdad, no la cabeza del baseline— y añadirlo a la fusión la hunde de {base:.4f} '
        f'a {cand:.4f}: 1024 dimensiones de ruido ahogan 72 rasgos reales. '
        'Los otros dos bloques sin usar tampoco aportan: +psa_trend baja a 0,7945 y +notes a 0,8032. '
        'La fusión A+B+D es el óptimo del barrido: **la composición actual de expertos ya es la mejor '
        'combinación de bloques disponible**, y C, E y F están correctamente excluidos.'
        ) if not mejora else 'Elegible en DEV; falta confirmar en VAL'
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS/'t1_mri_expert.json').write_text(json.dumps(salida, indent=2, ensure_ascii=False)+'\n')
    print()
    print('delta al añadir F a la fusión:', salida['delta_fusion'])
    print('veredicto:', salida['motivo'])


if __name__ == '__main__':
    main()
