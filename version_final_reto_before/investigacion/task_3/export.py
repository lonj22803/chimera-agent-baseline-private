"""Exportador de meses por curva de supervivencia (E05/E07 adoptados).

Sustituye **sólo** el último paso de T3: pasar de la puntuación del portavoz a
meses. No toca el portavoz, ni los expertos, ni la política de evento.

Por qué se cambia: la CDF empírica de V1 es monótona **no estricta**. Con 75
valores de referencia hay a lo sumo 76 intervalos de salida, y el c-index
oficial se calcula sobre los meses exportados. Medido en `e06_e07`: la CDF
colapsa 75 casos en ~43 valores distintos (32 empates); la curva los elimina y
gana **+0,0188 de `time_score`** perdiendo 0,0031 de c-index — dentro de la
tolerancia de 0,01 que fija el PLAN §7.4.

No es una mejora de ranking y no se vende como tal: el ranking de T3 es el
c-index, y ahí el cambio es plano.

Los parámetros se congelan con los mismos 75 casos con los que V1 congeló su
CDF, así que la sustitución es pieza a pieza y no cambia qué datos se han visto.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ARTEFACTO = Path(__file__).resolve().parent.parent / "artifacts" / "exportador_curva_t3.json"
SUAVE = Path(__file__).resolve().parent.parent / "artifacts" / "exportador_suave_t3.json"


def km_basal(t, e) -> list[tuple[float, float]]:
    """Kaplan–Meier del entrenamiento. Sin dependencias externas."""
    orden = np.argsort(t)
    t, e = np.asarray(t, float)[orden], np.asarray(e, int)[orden]
    n = len(t)
    pasos, S = [], 1.0
    for i, ti in enumerate(t):
        if e[i] != 1:
            continue
        en_riesgo = n - i
        if en_riesgo > 0:
            S *= (1 - 1 / en_riesgo)
            pasos.append((float(ti), float(S)))
    return pasos


def meses_desde_curva(pasos, lp: float, horizonte: float) -> float:
    """Mediana si la curva cruza 0,5; si no, RMST al horizonte de train.

    El PLAN §7.3 lo fija así, y obliga a decir qué es cada cosa: la mediana es un
    tiempo de supervivencia estimado; el RMST es **tiempo medio restringido sin
    evento**, no una fecha individual de recurrencia.
    """
    if not pasos:
        return float(horizonte)
    hr = float(np.exp(lp))
    prev_t, prev_S, area = 0.0, 1.0, 0.0
    for ti, S0 in pasos:
        S = S0 ** hr
        if prev_S >= 0.5 > S:
            frac = (prev_S - 0.5) / (prev_S - S) if prev_S > S else 0.0
            return float(prev_t + frac * (ti - prev_t))
        area += prev_S * (min(ti, horizonte) - prev_t)
        prev_t, prev_S = ti, S
        if prev_t >= horizonte:
            break
    area += prev_S * max(0.0, horizonte - prev_t)
    return float(area)


class ExportadorSuave:
    """Sustituye la CDF **empírica** por una suave; nada más.

    El empate es el problema, no el mapa. La CDF empírica de 75 valores tiene a
    lo sumo 76 escalones, así que dos riesgos distintos pueden salir con los
    mismos meses; medido en las salidas desplegadas: **12 empates en 75 casos**.
    El c-index oficial se calcula sobre los meses exportados, de modo que cada
    empate tira medio par.

    Qué **no** se cambia, a propósito:

    - `a`, `b` y `risk_scale` siguen siendo los de V1, así que el rango de salida
      es el mismo. Elegir un rango nuevo porque puntúa mejor en estos 75 casos
      sería ajuste dentro de muestra, que el PLAN §10.5 prohíbe expresamente.
    - El orden no se toca: la CDF normal es estrictamente creciente, luego
      conserva exactamente la ordenación del riesgo.

    Es calculable **por paciente**: sólo necesita la media y la desviación del
    train congeladas. Un mapa por rangos daría más ganancia (+0,023 de
    `time_score` medidos) pero exigiría conocer toda la cohorte, y el contenedor
    atiende un paciente por arranque (PLAN §13).
    """

    def __init__(self, ruta: Path | None = None):
        d = json.loads(Path(ruta or SUAVE).read_text())
        self.media = float(d["media_train"])
        self.sigma = float(d["sigma_train"]) or 1.0
        self.a = float(d["a"]); self.b = float(d["b"])
        self.escala_riesgo = float(d["risk_scale"])
        self.version = d["version"]

    def percentil(self, raw: float) -> float:
        """CDF normal ajustada al train. Estrictamente creciente: cero empates."""
        from math import erf, sqrt
        z = (float(raw) - self.media) / self.sigma
        return 0.5 * (1.0 + erf(z / sqrt(2.0)))

    def meses(self, raw: float) -> float:
        pct = self.percentil(raw)
        return float(self.a * np.exp(-self.b * self.escala_riesgo * (1.0 - pct)))


def congelar_suave(destino: Path | None = None) -> dict:
    """Media y desviación del `train_raw` del portavoz; `a`, `b` y escala intactos."""
    destino = Path(destino or SUAVE)
    raiz = Path(__file__).resolve().parents[3]
    port = json.loads(
        (raiz / "version_final_reto/task_3/experts_3/train/artifacts"
              / "spokesperson_candidate.json").read_text())
    raws = np.asarray(port["train_raw"], float)
    d = {"version": "cdf_suave_v1",
         "sustituye": "percentil por CDF empírica de 75 valores (hasta 76 escalones)",
         "por": "CDF normal ajustada al train, estrictamente creciente",
         "media_train": float(raws.mean()), "sigma_train": float(raws.std()),
         "a": float(port["a"]), "b": float(port["b"]),
         "risk_scale": float(port["risk_scale"]),
         "n_train": len(raws),
         "aviso": ("a, b y risk_scale NO se reajustan: el rango de salida es el de V1. "
                   "Sólo desaparecen los empates.")}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(d, indent=2, ensure_ascii=False))
    return d


class ExportadorCurva:
    """Carga el artefacto congelado y exporta meses. Sin estado del caso."""

    def __init__(self, ruta: Path = ARTEFACTO):
        d = json.loads(Path(ruta).read_text())
        self.pasos = [tuple(x) for x in d["km_pasos"]]
        self.centro = float(d["centro_train"])
        self.escala = float(d["escala_train"]) or 1.0
        self.horizonte = float(d["horizonte_meses"])
        self.version = d["version"]

    def meses(self, raw: float) -> float:
        """`raw` es la puntuación del portavoz, con la orientación de V1.

        En el mapa de V1 un `raw` MAYOR da percentil mayor y por tanto MÁS meses,
        así que esa puntuación **no** es un riesgo creciente. El signo va tomado
        de ahí, no supuesto: suponerlo al revés da el orden exactamente
        invertido (c-index 0,122 frente a 0,878; medido).
        """
        z = (float(raw) - self.centro) / self.escala
        return meses_desde_curva(self.pasos, -z, self.horizonte)


def congelar(destino: Path = ARTEFACTO) -> dict:
    """Ajusta y congela el artefacto con los mismos 75 casos que usó la CDF de V1."""
    raiz = Path(__file__).resolve().parents[3]
    portavoz = json.loads(
        (raiz / "version_final_reto/task_3/experts_3/train/artifacts"
              / "spokesperson_candidate.json").read_text())
    ids, raws = portavoz["case_ids"], portavoz["train_raw"]
    t, e = [], []
    for c in ids:
        g = json.loads((raiz / f"data/task3/ground_truth/{c}"
                        / "prostate-time-to-recurrence-or-last-follow-up.json").read_text())
        t.append(float(g["months_to_recurrence"])); e.append(int(g["event"]))
    d = {
        "version": "curva_v1",
        "origen": "spokesperson_candidate.json (train_raw) + ground truth de los 75 casos T3",
        "n_train": len(ids), "n_eventos": int(sum(e)),
        "km_pasos": km_basal(t, e),
        "centro_train": float(np.median(raws)),
        "escala_train": float(np.std(raws)),
        "horizonte_meses": float(np.percentile(t, 90)),
        "sustituye": "90 * exp(-0.1 * 12 * (1 - percentil))",
        "aviso": ("Ajustado con los mismos 75 casos que la CDF de V1: la sustitución es "
                  "pieza a pieza y no cambia qué datos se han visto. Sigue siendo dentro "
                  "de muestra, igual que lo era la CDF."),
    }
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(d, indent=2, ensure_ascii=False))
    return d


if __name__ == "__main__":
    print(json.dumps(congelar_suave(), indent=2, ensure_ascii=False))
    d = congelar()
    print(json.dumps({k: v for k, v in d.items() if k != "km_pasos"}, indent=2, ensure_ascii=False))
    print(f"pasos KM: {len(d['km_pasos'])}")
