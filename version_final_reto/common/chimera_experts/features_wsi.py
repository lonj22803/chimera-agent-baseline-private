"""Bloque J — representaciones neuronales de la biopsia y de la RM (tarea 2).

``prostate-modality-level-neural-representations.json`` trae en la tarea 2 dos
modalidades, no una:

* ``MRI image`` — un vector de 1024 dimensiones por caso, salida del modelo de
  detección de cáncer clínicamente significativo;
* ``Biopsy slide`` — entre cero y tres vectores de 960 dimensiones, uno por
  preparación, salida del modelo de *Gleason grading* automático.

El número de preparaciones varía por caso, así que hay que agregar. Se usa el
esquema clásico de *multiple-instance learning*: media (el caso medio), máximo
por dimensión (la preparación más extrema en cada eje) y desviación (la
heterogeneidad entre preparaciones). En cáncer de próstata el máximo es el que
tiene sentido clínico —el manejo lo fija el foco de mayor grado, no el
promedio— y por eso se conserva aparte y no sólo la media.

Ninguna dimensión cruda entra en un modelo: 1984 columnas con 72 casos
etiquetados no es un problema de regularización, es un problema de conteo. El
bloque expone dos cosas: **resúmenes de norma** (baratos, interpretables) y una
proyección PCA ajustada **sobre la cohorte completa sin etiquetas**, que es
legítima porque no mira la ``y``.

Referencias
-----------
* Ilse M., Tomczak J.M., Welling M., *Attention-based Deep Multiple Instance
  Learning*, ICML 2018 — agregación de bolsas de instancias.
* Campanella G. et al., *Clinical-grade computational pathology using weakly
  supervised deep learning on whole slide images*, Nat Med 2019 — el max-pooling
  sobre preparaciones como agregador con sentido clínico.
* Alsentzer E. et al. y la práctica habitual de *linear probing*: si una sonda
  lineal sobre el embedding no bate al escalar ya calibrado, el embedding no
  aporta y hay que decirlo.
"""

from __future__ import annotations

import numpy as np

NAN = float("nan")

MRI_KEY = "MRI image"
BX_KEY = "Biopsy slide"
RP_KEY = "Prostatectomy slide"


def _stack(embeddings: dict, key: str) -> np.ndarray | None:
    vecs = (embeddings or {}).get(key)
    if not vecs:
        return None
    arr = np.asarray(vecs, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    return arr if arr.size else None


def pooled(embeddings: dict, key: str) -> np.ndarray | None:
    """Concatena media, máximo y desviación entre preparaciones."""
    arr = _stack(embeddings, key)
    if arr is None:
        return None
    mean = arr.mean(axis=0)
    mx = arr.max(axis=0)
    sd = arr.std(axis=0) if arr.shape[0] > 1 else np.zeros_like(mean)
    return np.concatenate([mean, mx, sd])


def extract(case) -> dict[str, float]:
    """Resúmenes escalares. No devuelve dimensiones crudas, a propósito."""
    emb = getattr(case, "embeddings", {}) or {}
    feats: dict[str, float] = {}

    for tag, key in (("mri", MRI_KEY), ("bx", BX_KEY)):
        arr = _stack(emb, key)
        if arr is None:
            feats.update({
                f"emb_{tag}_present": 0.0,
                f"emb_{tag}_n": 0.0,
                f"emb_{tag}_norm": NAN,
                f"emb_{tag}_mean": NAN,
                f"emb_{tag}_std": NAN,
                f"emb_{tag}_max": NAN,
                f"emb_{tag}_min": NAN,
                f"emb_{tag}_sparsity": NAN,
                f"emb_{tag}_heterogeneity": NAN,
            })
            continue
        mean = arr.mean(axis=0)
        feats[f"emb_{tag}_present"] = 1.0
        feats[f"emb_{tag}_n"] = float(arr.shape[0])
        feats[f"emb_{tag}_norm"] = float(np.linalg.norm(mean))
        feats[f"emb_{tag}_mean"] = float(mean.mean())
        feats[f"emb_{tag}_std"] = float(mean.std())
        feats[f"emb_{tag}_max"] = float(mean.max())
        feats[f"emb_{tag}_min"] = float(mean.min())
        feats[f"emb_{tag}_sparsity"] = float((mean == 0).mean())
        # Heterogeneidad entre preparaciones: distancia media al centroide.
        # Un caso con preparaciones dispares es un caso con enfermedad desigual.
        feats[f"emb_{tag}_heterogeneity"] = (
            float(np.linalg.norm(arr - mean, axis=1).mean()) if arr.shape[0] > 1 else 0.0
        )
    return feats


class EmbeddingProjector:
    """PCA por modalidad, ajustada sobre la cohorte **sin usar etiquetas**.

    Se ajusta con todos los casos disponibles (etiquetados o no): es una
    transformación no supervisada, así que incluirlos no filtra la ``y``. Los
    casos sin esa modalidad reciben NaN, no ceros — un cero en un espacio PCA es
    el centroide, y hacer pasar "no tengo imagen" por "soy el caso medio" es
    justo el error que la incertidumbre por datos ausentes tiene que capturar.
    """

    def __init__(self, n_components: int = 8, keys: tuple[str, ...] = (MRI_KEY, BX_KEY)):
        self.n_components = int(n_components)
        self.keys = keys
        self._pca: dict[str, object] = {}
        self._dim: dict[str, int] = {}

    def fit(self, cases: list) -> "EmbeddingProjector":
        from sklearn.decomposition import PCA

        for key in self.keys:
            rows = [pooled(c.embeddings, key) for c in cases]
            rows = [r for r in rows if r is not None]
            if len(rows) < self.n_components + 1:
                continue
            M = np.vstack(rows)
            k = min(self.n_components, M.shape[0] - 1, M.shape[1])
            pca = PCA(n_components=k, random_state=0)
            pca.fit(M)
            self._pca[key] = pca
            self._dim[key] = k
        return self

    def transform_case(self, case) -> dict[str, float]:
        out: dict[str, float] = {}
        for key in self.keys:
            tag = "mri" if key == MRI_KEY else "bx"
            k = self._dim.get(key, 0)
            v = pooled(getattr(case, "embeddings", {}) or {}, key)
            if key not in self._pca or v is None:
                out.update({f"pc_{tag}_{i}": NAN for i in range(k)})
                continue
            z = self._pca[key].transform(v.reshape(1, -1))[0]
            out.update({f"pc_{tag}_{i}": float(z[i]) for i in range(k)})
        return out

    @property
    def explained(self) -> dict[str, float]:
        return {k: float(p.explained_variance_ratio_.sum()) for k, p in self._pca.items()}
