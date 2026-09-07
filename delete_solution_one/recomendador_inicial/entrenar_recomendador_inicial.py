"""Recomendador inicial de la tarea 1 (biopsia sí/no) — clasificación con A ± ΔA.

Qué resuelve
------------
El agente necesita una **primera opinión escribible en la pizarra**: un veredicto con su
barra de error, para que el resto de expertos puedan discutirla. Este módulo entrega
exactamente eso a partir de UN solo fichero:

    data/task1/<case_id>/structured-prompt.json

Nada más. Ni historia clínica (`*-clinical-data.json`) ni embeddings. Es una restricción
deliberada, no una limitación: según el evaluador del reto `tool_score` premia la
*precisión* en la revelación de documentos, así que un experto que vive solo del prompt es
gratis en presupuesto de revelación.

Diseño (todo lo cuantitativo sale de expertos_analisis/clasificator_for_task.ipynb)
----------------------------------------------------------------------------------
* **Variables**: el núcleo de 8 de la sección 2.3 del notebook, menos `ehr_fh`, que venía
  de la historia clínica. Quitarla no cuesta nada — de hecho sube algo la exactitud (§5.3
  del notebook: 0.670 con 9 variables incluyendo `ehr_fh`; 0.692 aquí con las 8 del prompt).
* **Clasificador**: kNN probabilístico (núcleo gaussiano + suavizado de Laplace), el
  `SoftKNN` de la sección 5.1. Se elige por lo que devuelve, no por lo que acierta: da
  posterior continua, vecinos citables y la mejor log-loss de las variantes kNN.
* **A ± ΔA**: la novedad respecto al notebook. El voto ponderado del kNN *es* una posterior
  Beta:

      A ~ Beta(Σw·1[y=sí] + α ,  Σw·1[y=no] + α)

  y su desviación típica ya es una ΔA. Pero esa Beta solo captura la duda *dentro* de un
  conjunto de entrenamiento fijo. Para capturar también la duda *sobre* el conjunto de
  entrenamiento (91 casos son pocos), se hace **bagging**: B remuestreos estratificados,
  un kNN probabilístico en cada uno, y la ley de la varianza total sobre la mezcla:

      Var(A) = E_b[Var_Beta(A|b)]  +  Var_b(E[A|b])
               └── aleatoria ──┘     └── epistémica ──┘

  La aleatoria dice "los vecinos no se ponen de acuerdo"; la epistémica dice "con otros
  91 pacientes la respuesta habría sido otra". Su suma es ΔA.
* **Por qué bagging y no la densidad local**: el notebook (§8.4) midió que `densidad_local`
  NO detecta errores en esta cohorte (AUC 0.53, azar). La ΔA epistémica del bagging sí
  (AUC 0.670 en la validación de abajo). Es la corrección concreta que aporta este módulo.

Artefacto
---------
El `.joblib` que se escribe es **numpy puro**: no guarda ningún objeto de sklearn ni de
este módulo, así que se puede cargar desde cualquier proceso sin importar nada especial.
La inferencia (`_predecir`) es la misma función que usa la validación cruzada, de modo que
lo que se mide es literalmente lo que se sirve.

Uso
---
    # entrenar + validar + verificar (escribe el .joblib)
    python entrenar_recomendador_inicial.py

    # consultar un caso
    python entrenar_recomendador_inicial.py --caso data/task1/PT-pseudo_0bd72f429a8b

    # desde código
    from entrenar_recomendador_inicial import RecomendadorInicial
    rec = RecomendadorInicial.cargar()
    rec.recomendar('data/task1/PT-pseudo_0bd72f429a8b/structured-prompt.json')
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import joblib
import numpy as np
from scipy import stats

# ---------------------------------------------------------------------------
# 0. Constantes de diseño
# ---------------------------------------------------------------------------
AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]                      # …/CHIMERA_challenge_alone
DATA_T1 = RAIZ / 'data' / 'task1'
DECISION = 'prostate-biopsy-decision'
ARTEFACTO = AQUI / 'recomendador_inicial_task1.joblib'

# Núcleo de la §2.3 del notebook restringido a lo que trae structured-prompt.json.
NUCLEO = ['pirads', 'bx_ord', 'psa', 'age', 'psad', 'dre_ord', 'vol', 'n_pmhx']

# Codificaciones ordinales — importan porque el kNN mide distancias (§3 del notebook).
DRE_ORD = {'Normal': 0., 'Negative': 0., 'Benign': 0., 'Nodus': 1.,
           'Abnormal': 2., 'Suspicious': 2., 'Not done': np.nan}
BX_ORD = {'None': 0., 'Negative': 1., 'ASAP/HGPIN': 2., 'Positive': 3.}

CLASES = np.array(['no', 'yes'])            # índice 1 = clase positiva = "biopsiar"

SEED = 0
K = 10                    # = round(sqrt(91)); regla fijada A PRIORI, sin mirar la CV
ALPHA_LAPLACE = 1.0
B_BOOTSTRAP = 200
N_FOLDS, N_REPS = 5, 5
ALPHA_CONFORMAL = 0.20    # cobertura objetivo 80 %

# Escalera operativa: cuántas ΔA tiene que haber entre A y el umbral 0.5 para cada tramo.
Z_FIRME, Z_APOYA = 1.96, 1.00


# ---------------------------------------------------------------------------
# 1. Extracción de características — SOLO desde structured-prompt.json
# ---------------------------------------------------------------------------
def num(x):
    """Primer número que aparezca en x; NaN si no hay ninguno."""
    if x is None or isinstance(x, bool):
        return np.nan
    if isinstance(x, (int, float)):
        return float(x)
    m = re.search(r'-?\d+\.?\d*', str(x))
    return float(m.group()) if m else np.nan


def caracteristicas(prompt: dict) -> dict:
    """Las 8 variables del núcleo. Lo ausente sale NaN, nunca 0."""
    d = prompt or {}
    return {
        'pirads':  num(d.get('pirads')),
        'bx_ord':  BX_ORD.get(d.get('bx'), np.nan),
        'psa':     num(d.get('psa')),
        'age':     num(d.get('age')),
        'psad':    num(d.get('psad')),
        'dre_ord': DRE_ORD.get(d.get('dre'), np.nan),
        'vol':     num(d.get('vol')),
        'n_pmhx':  float(len(d.get('pmhx') or [])),
    }


def vector(prompt: dict):
    """(vector 1xD, lista de variables del núcleo que faltan)."""
    f = caracteristicas(prompt)
    faltan = [c for c in NUCLEO if not np.isfinite(f.get(c, np.nan))]
    return np.array([[f.get(c, np.nan) for c in NUCLEO]], float), faltan


# ---------------------------------------------------------------------------
# 2. El motor: bagging del kNN probabilístico, en numpy puro
# ---------------------------------------------------------------------------
def _estandarizar(Xr):
    """Mediana para imputar y media/desv para escalar, calculadas sobre Xr."""
    med = np.nanmedian(Xr, axis=0)
    med = np.where(np.isfinite(med), med, 0.)
    Xi = np.where(np.isnan(Xr), med, Xr)
    mu = Xi.mean(0)
    sd = Xi.std(0)
    sd = np.where(sd > 1e-12, sd, 1.)        # columna constante en el remuestreo
    return med, mu, sd, (Xi - mu) / sd


def _aplicar(Xq, med, mu, sd):
    return (np.where(np.isnan(Xq), med, Xq) - mu) / sd


def ajustar(Xr, y, ids, k=K, alpha=ALPHA_LAPLACE, B=B_BOOTSTRAP, seed=SEED) -> dict:
    """Ajusta el estado del recomendador. Devuelve un dict de numpy puro."""
    Xr = np.asarray(Xr, float)
    y_pos = (np.asarray(y) == CLASES[1]).astype(np.int8)
    n = len(y_pos)
    k = int(min(k, n))

    # --- modelo base sobre TODOS los casos: es el que aporta los vecinos citables ---
    med0, mu0, sd0, Z0 = _estandarizar(Xr)

    # Ancho del núcleo gaussiano: mediana de las distancias no nulas entre vecinos.
    D0 = np.sqrt(((Z0[:, None, :] - Z0[None, :, :]) ** 2).sum(-1))
    dk = np.sort(D0, axis=1)[:, 1:k + 1]
    h = float(np.median(dk[dk > 0])) if (dk > 0).any() else 1.0
    if not np.isfinite(h) or h <= 0:
        h = 1.0

    # --- miembros del bagging: remuestreo estratificado con reemplazo ---
    rng = np.random.default_rng(seed)
    pos, neg = np.where(y_pos == 1)[0], np.where(y_pos == 0)[0]
    IDX = np.empty((B, n), np.int32)
    MED = np.empty((B, Xr.shape[1]))
    MU = np.empty_like(MED)
    SD = np.empty_like(MED)
    Z = np.empty((B, n, Xr.shape[1]))
    for b in range(B):
        sel = np.concatenate([rng.choice(pos, len(pos), replace=True),
                              rng.choice(neg, len(neg), replace=True)])
        IDX[b] = sel
        MED[b], MU[b], SD[b], Z[b] = _estandarizar(Xr[sel])

    return {
        'version': 1,
        'tarea': 1,
        'decision': DECISION,
        'variables': list(NUCLEO),
        'clases': CLASES,
        'k': k, 'alpha': float(alpha), 'h': h, 'B': int(B), 'seed': int(seed),
        # base (vecinos citables)
        'med0': med0, 'mu0': mu0, 'sd0': sd0, 'Z0': Z0,
        'X_raw': Xr, 'y_pos': y_pos, 'ids': np.asarray(ids),
        # bagging
        'IDX': IDX, 'MED': MED, 'MU': MU, 'SD': SD, 'Z': Z,
    }


def _predecir(est: dict, Xq, excluir=None) -> dict:
    """A ± ΔA para cada fila de Xq. `excluir` = índices del entrenamiento a ignorar.

    Es la ÚNICA ruta de inferencia: la usan la validación cruzada y la herramienta.
    """
    Xq = np.atleast_2d(np.asarray(Xq, float))
    nq = len(Xq)
    B, n, _ = est['Z'].shape
    k, h, a0 = est['k'], est['h'], est['alpha']
    ypos_mi = est['y_pos'][est['IDX']]                       # (B, n) etiquetas del remuestreo

    fuera = np.zeros(n, bool)
    if excluir is not None and len(np.atleast_1d(excluir)):
        fuera[np.atleast_1d(excluir)] = True
    mask_mi = fuera[est['IDX']]                              # (B, n) posiciones a ignorar

    medias = np.empty((B, nq))
    varianzas = np.empty((B, nq))
    for b in range(B):
        Zq = _aplicar(Xq, est['MED'][b], est['MU'][b], est['SD'][b])      # (nq, D)
        d2 = ((est['Z'][b][None, :, :] - Zq[:, None, :]) ** 2).sum(-1)    # (nq, n)
        d2 = np.where(mask_mi[b][None, :], np.inf, d2)
        vec = np.argpartition(d2, min(k, n - 1) - 1, axis=1)[:, :k]       # k más cercanos
        dd = np.take_along_axis(d2, vec, 1)
        w = np.exp(-dd / (2 * h ** 2))
        yv = ypos_mi[b][vec]
        a = (w * yv).sum(1) + a0                              # pseudo-cuentas Beta
        c = (w * (1 - yv)).sum(1) + a0
        s = a + c
        medias[b] = a / s
        varianzas[b] = a * c / (s * s * (s + 1))

    A = medias.mean(0)
    var_ale = varianzas.mean(0)          # E_b[Var(A|b)]  — desacuerdo entre vecinos
    var_epi = medias.var(0)              # Var_b(E[A|b])  — sensibilidad a la muestra
    delta = np.sqrt(var_ale + var_epi)

    # --- vecinos citables: del modelo base, sin remuestrear ---
    Zq0 = _aplicar(Xq, est['med0'], est['mu0'], est['sd0'])
    d20 = ((est['Z0'][None, :, :] - Zq0[:, None, :]) ** 2).sum(-1)
    d20 = np.where(fuera[None, :], np.inf, d20)
    orden = np.argsort(d20, axis=1)[:, :k]
    dist = np.sqrt(np.take_along_axis(d20, orden, 1))
    w0 = np.exp(-np.take_along_axis(d20, orden, 1) / (2 * h ** 2))

    return {'A': A, 'delta': delta,
            'delta_ale': np.sqrt(var_ale), 'delta_epi': np.sqrt(var_epi),
            'vecinos': orden, 'distancias': dist, 'pesos': w0,
            'n_efectivo': w0.sum(1)}


def _intervalo(A, delta, z):
    """Intervalo de A al nivel z·ΔA, ajustando una Beta por momentos (queda en [0,1])."""
    A = np.atleast_1d(A)
    delta = np.atleast_1d(delta)
    q = stats.norm.cdf(-z), stats.norm.cdf(z)
    lo, hi = np.empty_like(A), np.empty_like(A)
    for i, (m, s) in enumerate(zip(A, delta)):
        v, vmax = s ** 2, m * (1 - m)
        if 0 < v < vmax * 0.999:
            c = vmax / v - 1
            lo[i], hi[i] = stats.beta.ppf(q, m * c, (1 - m) * c)
        else:                                   # cola degenerada: normal recortada
            lo[i], hi[i] = max(0., m - z * s), min(1., m + z * s)
    return lo, hi


# ---------------------------------------------------------------------------
# 3. La herramienta
# ---------------------------------------------------------------------------
class RecomendadorInicial:
    """Primera opinión para la pizarra: veredicto, A ± ΔA y la evidencia que lo sostiene."""

    def __init__(self, estado: dict):
        self.e = estado

    @classmethod
    def cargar(cls, ruta=ARTEFACTO):
        return cls(joblib.load(ruta))

    # -- entrada -------------------------------------------------------------
    @staticmethod
    def _leer(ruta_prompt=None, prompt=None) -> dict:
        if prompt is not None:
            return prompt
        p = Path(ruta_prompt)
        if p.is_dir():
            p = p / 'structured-prompt.json'
        with open(p, encoding='utf-8') as fh:
            return json.load(fh)

    # -- salida --------------------------------------------------------------
    def recomendar(self, ruta_prompt=None, prompt=None, k_evidencia=5,
                   excluir_si_entrenado=True) -> dict:
        """Devuelve el dict serializable que el agente escribe en la pizarra."""
        e = self.e
        d = self._leer(ruta_prompt, prompt)
        x, faltan = vector(d)
        cid = str(d.get('case_id') or d.get('pid') or '')

        # Si el caso está en el entrenamiento, se excluye a sí mismo: si no, se vería
        # como su propio vecino más próximo y A saldría artificialmente confiado.
        en_train = bool(cid) and cid in set(map(str, e['ids']))
        excluir = np.where(e['ids'].astype(str) == cid)[0] if (en_train and excluir_si_entrenado) else None

        r = _predecir(e, x, excluir=excluir)
        A = float(r['A'][0])
        delta = float(r['delta'][0])
        lo68, hi68 = (float(v[0]) for v in _intervalo(A, delta, 1.0))
        lo95, hi95 = (float(v[0]) for v in _intervalo(A, delta, 1.96))

        pred = CLASES[1] if A >= .5 else CLASES[0]
        p_pred = A if A >= .5 else 1 - A
        z = abs(A - .5) / delta if delta > 0 else np.inf
        tramo = 'firme' if z >= Z_FIRME else ('apoya' if z >= Z_APOYA else 'discutir')

        # Conjunto conformal Mondrian (garantía formal de cobertura, §8.3 del notebook).
        P = {'no': 1 - A, 'yes': A}
        conformal = [c for c in CLASES if (1 - P[c]) <= e['q_conformal'][c]]

        idx = r['vecinos'][0][:k_evidencia]
        dist = r['distancias'][0][:k_evidencia]
        concord = float((e['y_pos'][r['vecinos'][0]] == (1 if pred == 'yes' else 0)).mean())
        ent = -(A * np.log(max(A, 1e-12)) + (1 - A) * np.log(max(1 - A, 1e-12))) / np.log(2)

        return {
            'case_id': cid,
            'tarea': 1,
            'pregunta': DECISION,
            # ---- lo que va a la pizarra ----
            'prediccion': str(pred),
            'A': round(A, 4),
            'delta_A': round(delta, 4),
            'pizarra': self._frase(pred, A, delta, lo95, hi95, tramo),
            'magnitud_A': 'p(biopsia = yes)',
            'intervalo_68': [round(lo68, 4), round(hi68, 4)],
            'intervalo_95': [round(lo95, 4), round(hi95, 4)],
            # ---- incertidumbre desglosada ----
            'incertidumbre': {
                'delta_total': round(delta, 4),
                'delta_aleatoria': round(float(r['delta_ale'][0]), 4),   # vecinos en desacuerdo
                'delta_epistemica': round(float(r['delta_epi'][0]), 4),  # pocos datos parecidos
                'confianza': round(float(p_pred), 4),
                'margen_z': round(float(z), 3),                          # cuántas ΔA hasta 0.5
                'entropia_normalizada': round(float(ent), 4),
                'vecinos_efectivos': round(float(r['n_efectivo'][0]), 2),
                'de_k_vecinos': int(e['k']),
                'concordancia_vecinos': round(concord, 3),
                'conjunto_conformal': [str(c) for c in conformal],
                'cobertura_conformal': round(1 - e['alpha_conformal'], 2),
            },
            # ---- qué hacer con esto ----
            'veredicto_operativo': tramo,
            'lectura': e['lectura_tramos'][tramo],
            'acierto_esperado': e['acc_tramos'][tramo],
            # ---- evidencia citable ----
            'evidencia': [
                {'case_id': str(e['ids'][i]),
                 'decision': str(CLASES[e['y_pos'][i]]),
                 'distancia': round(float(dd), 3),
                 'variables': {c: (None if not np.isfinite(v) else round(float(v), 2))
                               for c, v in zip(NUCLEO, e['X_raw'][i])}}
                for i, dd in zip(idx, dist)],
            # ---- trazabilidad ----
            'variables_usadas': {c: (None if not np.isfinite(v) else round(float(v), 3))
                                 for c, v in zip(NUCLEO, x[0])},
            'variables_faltantes': faltan,
            'caso_en_entrenamiento': en_train,
            'nota_entrenamiento': ('El caso está entre los 91 etiquetados; se ha excluido de '
                                   'sus propios vecinos, así que esta respuesta es honesta.'
                                   if en_train and excluir is not None else None),
            'rendimiento_validacion': e['metricas'],
        }

    @staticmethod
    def _frase(pred, A, delta, lo, hi, tramo):
        etiqueta = 'SÍ biopsiar' if pred == 'yes' else 'NO biopsiar'
        return (f'{etiqueta}  ·  p(biopsia=yes) = {A:.2f} ± {delta:.2f}  '
                f'(IC95 {lo:.2f}–{hi:.2f})  ·  {tramo}')


# ---------------------------------------------------------------------------
# 4. Entrenamiento, validación y verificación
# ---------------------------------------------------------------------------
def cargar_datos(solo_etiquetados=True):
    """Lee data/task1 y devuelve (X, y, ids). Solo toca structured-prompt.json."""
    Xs, ys, ids = [], [], []
    for carpeta in sorted(p for p in DATA_T1.iterdir() if p.is_dir()):
        lab = carpeta / f'{DECISION}.json'
        if solo_etiquetados and not lab.exists():
            continue
        with open(carpeta / 'structured-prompt.json', encoding='utf-8') as fh:
            f = caracteristicas(json.load(fh))
        Xs.append([f[c] for c in NUCLEO])
        ids.append(carpeta.name)
        if lab.exists():
            with open(lab, encoding='utf-8') as fh:
                ys.append(str(json.load(fh)))
        else:
            ys.append(None)
    return np.array(Xs, float), np.array(ys), np.array(ids)


def validar(X, y, k=K, B=B_BOOTSTRAP, n_folds=N_FOLDS, n_reps=N_REPS):
    """CV estratificada repetida usando la MISMA ruta de inferencia que la herramienta."""
    from sklearn.model_selection import StratifiedKFold
    n = len(y)
    Aa, Va, Ve = [], [], []
    for s in range(n_reps):
        A = np.zeros(n); va = np.zeros(n); ve = np.zeros(n)
        for tr, te in StratifiedKFold(n_folds, shuffle=True, random_state=s).split(X, y):
            est = ajustar(X[tr], y[tr], np.arange(len(tr)), k=k, B=B, seed=s)
            r = _predecir(est, X[te])
            A[te] = r['A']; va[te] = r['delta_ale'] ** 2; ve[te] = r['delta_epi'] ** 2
        Aa.append(A); Va.append(va); Ve.append(ve)
    return np.mean(Aa, 0), np.mean(Va, 0), np.mean(Ve, 0)


def _ece(conf, ok, n_bins=8):
    e, bordes = 0., np.linspace(.5, 1, n_bins + 1)
    for lo, hi in zip(bordes[:-1], bordes[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.sum():
            e += m.mean() * abs(ok[m].mean() - conf[m].mean())
    return float(e)


def metricas_oof(A, delta, y):
    from sklearn.metrics import roc_auc_score, balanced_accuracy_score, log_loss
    yb = (y == CLASES[1]).astype(int)
    pred = (A >= .5).astype(int)
    ok = pred == yb
    conf = np.where(A >= .5, A, 1 - A)
    z = np.abs(A - .5) / np.maximum(delta, 1e-12)
    cov, acc_c = np.arange(1, len(y) + 1) / len(y), np.cumsum(ok[np.argsort(-z)]) / np.arange(1, len(y) + 1)
    return {
        'n': int(len(y)),
        'clase_mayoritaria': round(float(max(yb.mean(), 1 - yb.mean())), 3),
        'acc': round(float(ok.mean()), 3),
        'bal_acc': round(float(balanced_accuracy_score(yb, pred)), 3),
        'auc': round(float(roc_auc_score(yb, A)), 3),
        'logloss': round(float(log_loss(yb, np.clip(A, 1e-9, 1 - 1e-9))), 3),
        'brier': round(float(np.mean((A - yb) ** 2)), 3),
        'ece': round(_ece(conf, ok), 3),
        'acc@30%': round(float(acc_c[int(.3 * len(y)) - 1]), 3),
        'acc@50%': round(float(acc_c[int(.5 * len(y)) - 1]), 3),
        'acc@70%': round(float(acc_c[int(.7 * len(y)) - 1]), 3),
        'auc_delta_detecta_error': round(float(roc_auc_score((~ok).astype(int), delta)), 3),
        'protocolo': f'{N_REPS}x{N_FOLDS} StratifiedKFold, out-of-fold',
    }


def entrenar(k=K, B=B_BOOTSTRAP, verbose=True):
    """Entrena con TODOS los casos etiquetados, valida, y escribe el artefacto."""
    def eco(*a):
        if verbose:
            print(*a)

    X, y, ids = cargar_datos()
    eco(f'Casos etiquetados : {len(y)}   ·   clases: '
        f'{ {c: int((y == c).sum()) for c in CLASES} }')
    eco(f'Variables ({len(NUCLEO)})      : {", ".join(NUCLEO)}')
    eco(f'% NaN por variable: '
        f'{ dict(zip(NUCLEO, np.isnan(X).mean(0).round(3))) }')

    # --- validación honesta (out-of-fold) ---
    eco(f'\nValidación cruzada {N_REPS}x{N_FOLDS} (k={k}, B={B})…')
    A, va, ve = validar(X, y, k=k, B=B)
    delta = np.sqrt(va + ve)
    met = metricas_oof(A, delta, y)
    eco('  ' + '  '.join(f'{kk}={vv}' for kk, vv in met.items() if kk not in ('protocolo', 'n')))

    # --- escalera operativa: se MIDE aquí, no se supone ---
    yb = (y == CLASES[1]).astype(int)
    ok = ((A >= .5).astype(int) == yb)
    z = np.abs(A - .5) / np.maximum(delta, 1e-12)
    tramos = {'firme': z >= Z_FIRME,
              'apoya': (z >= Z_APOYA) & (z < Z_FIRME),
              'discutir': z < Z_APOYA}
    acc_tramos, ic_tramos = {}, {}
    eco('\nEscalera operativa (A ± ΔA frente al umbral 0.5):')
    for nombre, m in tramos.items():
        s, nn = int(ok[m].sum()), int(m.sum())
        acc_tramos[nombre] = round(s / nn, 3) if nn else None
        lo = float(stats.beta.ppf(.025, s, nn - s + 1)) if s > 0 else 0.
        hi = float(stats.beta.ppf(.975, s + 1, nn - s)) if s < nn else 1.
        ic_tramos[nombre] = [round(lo, 3), round(hi, 3)]
        eco(f'  {nombre:9} n={nn:3d} ({m.mean():4.0%})  acc={acc_tramos[nombre]}  '
            f'IC95 [{lo:.2f}, {hi:.2f}]')

    # --- umbrales conformales Mondrian sobre las probabilidades OOF ---
    P = np.stack([1 - A, A], 1)
    s_nc = 1 - P[np.arange(len(y)), yb]
    q = {}
    for j, c in enumerate(CLASES):
        sc = np.sort(s_nc[yb == j])
        kk = min(len(sc), int(np.ceil((len(sc) + 1) * (1 - ALPHA_CONFORMAL))))
        q[str(c)] = float(sc[kk - 1])
    eco(f'\nUmbrales conformales (α={ALPHA_CONFORMAL}): {  {c: round(v, 3) for c, v in q.items()} }')

    # --- estado final: entrenado con los 91 ---
    est = ajustar(X, y, ids, k=k, B=B, seed=SEED)
    est.update({
        'metricas': met,
        'oof': {'ids': ids, 'A': A, 'delta': delta,
                'delta_ale': np.sqrt(va), 'delta_epi': np.sqrt(ve), 'y': y},
        'q_conformal': q, 'alpha_conformal': ALPHA_CONFORMAL,
        'z_firme': Z_FIRME, 'z_apoya': Z_APOYA,
        'acc_tramos': acc_tramos, 'ic_tramos': ic_tramos,
        'n_tramos': {kk: int(v.sum()) for kk, v in tramos.items()},
        'lectura_tramos': {
            'firme': ('A ± 1.96·ΔA no cruza 0.5: el recomendador se moja. En validación '
                      'este tramo no falló ninguno de los 13 casos, pero son 13: el IC95 '
                      'del acierto llega solo hasta 0.75 por abajo.'),
            'apoya': ('A ± ΔA no cruza 0.5: hay una dirección clara pero no cerrada. '
                      'Sirve como voto con peso, no como decisión.'),
            'discutir': ('A ± ΔA cruza 0.5: el recomendador NO distingue. Escribir el número '
                         'en la pizarra como punto de partida y dejar que los demás expertos '
                         'lo muevan; aquí acierta poco más que la clase mayoritaria.'),
        },
        'fuente': 'data/task1/*/structured-prompt.json (bloque A; sin EHR ni embeddings)',
        'generado_por': 'recomendador/recomendador_task1/recomendador_inicial/'
                        'entrenar_recomendador_inicial.py',
    })
    joblib.dump(est, ARTEFACTO)
    eco(f'\nArtefacto escrito : {ARTEFACTO.relative_to(RAIZ)}  '
        f'({ARTEFACTO.stat().st_size / 1024:.0f} KB)')
    return est


def verificar(verbose=True):
    """Recarga el artefacto y comprueba que sirve lo mismo que acaba de entrenarse."""
    def eco(*a):
        if verbose:
            print(*a)

    rec = RecomendadorInicial.cargar()
    e = rec.e
    X, y, ids = cargar_datos()

    # (a) el estado guardado reproduce el vector de características de cada caso
    assert list(e['variables']) == NUCLEO
    assert np.allclose(e['X_raw'], X, equal_nan=True), 'X_raw no coincide con los datos'

    # (b) la herramienta, leyendo el JSON de disco, da lo mismo que _predecir sobre X
    fallos = 0
    for i in [0, 7, 23, 45, 90]:
        sal = rec.recomendar(DATA_T1 / ids[i] / 'structured-prompt.json',
                             excluir_si_entrenado=False)
        r = _predecir(e, X[[i]])
        # la salida viene redondeada a 4 decimales, de ahí la tolerancia
        if not (abs(sal['A'] - float(r['A'][0])) <= 5e-5 and
                abs(sal['delta_A'] - float(r['delta'][0])) <= 5e-5):
            fallos += 1
    assert fallos == 0, 'la lectura desde disco no reproduce la inferencia interna'

    # (c) determinismo: dos llamadas seguidas dan exactamente lo mismo
    a = rec.recomendar(DATA_T1 / ids[3] / 'structured-prompt.json')
    b = rec.recomendar(DATA_T1 / ids[3] / 'structured-prompt.json')
    assert a == b, 'la herramienta no es determinista'

    # (d) la exclusión leave-one-out cambia la respuesta de un caso entrenado (y debe)
    con = rec.recomendar(DATA_T1 / ids[3] / 'structured-prompt.json', excluir_si_entrenado=False)
    assert a['A'] != con['A'], 'la exclusión LOO no está teniendo efecto'

    # (e) corre sobre TODOS los casos, etiquetados o no, sin romperse
    todos = sorted(p for p in DATA_T1.iterdir() if p.is_dir())
    salidas = [rec.recomendar(p / 'structured-prompt.json') for p in todos]
    assert all(0 <= s['A'] <= 1 and s['delta_A'] > 0 for s in salidas)
    assert all(json.dumps(s) for s in salidas), 'la salida no es serializable a JSON'

    eco(f'Verificación OK   : {len(todos)} casos servidos, salida JSON válida, '
        f'inferencia determinista y consistente con el entrenamiento.')
    eco(f'  · exclusión LOO  : A={con["A"]:.3f} (dentro) → {a["A"]:.3f} (fuera) en {ids[3]}')
    eco(f'  · reparto de veredictos sobre los {len(todos)} casos: '
        f'{ {t: sum(s["veredicto_operativo"] == t for s in salidas) for t in ("firme", "apoya", "discutir")} }')
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--caso', help='directorio del caso o ruta a structured-prompt.json')
    ap.add_argument('-B', type=int, default=B_BOOTSTRAP, help='miembros del bagging')
    ap.add_argument('-k', type=int, default=K, help='vecinos')
    args = ap.parse_args()

    if args.caso:
        sal = RecomendadorInicial.cargar().recomendar(args.caso)
        print(json.dumps(sal, indent=2, ensure_ascii=False))
        return

    entrenar(k=args.k, B=args.B)
    print()
    verificar()


if __name__ == '__main__':
    sys.exit(main())
