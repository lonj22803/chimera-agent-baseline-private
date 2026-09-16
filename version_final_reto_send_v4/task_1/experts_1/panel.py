"""El panel de expertos entrenados, precalculado una vez y leído por la junta.

Los cuatro expertos de ``task_1/experts_1/model`` son estimadores de
scikit-learn con imputación múltiple: puntuar un caso suelto cuesta ~20 s
(300 pases del imputador), puntuar los 195 en lote cuesta menos de tres
minutos. Así que la junta **no** los llama en vivo: este módulo los pasa por
todos los casos una sola vez, guarda el resultado en ``artifacts/panel_cache.json``
y cada sesión lee de ahí.

Dos modos, que son la misma pizarra con dos versiones del panel:

``deployed``
    Los artefactos tal como se entrenaron (sobre los 91 casos etiquetados).
    Es lo que se empaquetaría para el conjunto de test del reto. Sobre los 91
    casos etiquetados esta versión **ha visto la etiqueta**: la nota que sale
    de ahí es rendimiento dentro de muestra.

``honest``
    Para los 91 casos etiquetados, veredictos **out-of-fold**: la misma receta
    de cada bundle (mismo estimador base, mismos bloques, mismo número de
    miembros e imputaciones) reentrenada en 5 particiones estratificadas, de
    modo que ningún experto ve la etiqueta del caso que puntúa. Sobre un caso
    del test real ``honest`` y ``deployed`` coinciden por construcción: el caso
    no está en el entrenamiento en ninguno de los dos.

La diferencia entre las dos notas es el precio de la memorización, y se
publica junto al resultado.

Por qué el experto de fusión se calcula en dos variantes
--------------------------------------------------------
El Experto 3 lee los bloques A+B+D: el panel, la analítica y el informe
radiológico. En la junta sólo habla **después** del registrador y sólo sobre lo
que el registrador abrió: si el laboratorio no está sobre la mesa, se le pasa
el caso con la analítica en blanco y su imputador la rellena — que es
exactamente para lo que está construido (``epistemic_missing`` crece). Si
tampoco se abrió el informe radiológico, se abstiene. Por eso el caché guarda
la variante completa y la variante sin analítica.
"""

from __future__ import annotations

import json
import logging
import math
import multiprocessing
import os
import sys
import warnings
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

import numpy as np

from version_final_reto.task_1.agent.paths import ARTIFACT, CACHE, DATA
from version_final_reto.common import chimera_experts  # Registers legacy pickle module names before loading.
from version_final_reto.common import serial_predict

warnings.filterwarnings("ignore")
log = logging.getLogger(__name__)

#: Tramo de la escalera -> vocabulario ``confidence`` del reto.
TIER_TO_CONFIDENCE = {"firm": "clear", "supports": "borderline", "discuss": "uncertain"}


# ---------------------------------------------------------------------------
# carga
# ---------------------------------------------------------------------------


def _imports():
    from chimera_experts.expert_classifier import BiopsyExpert  # noqa: PLC0415
    from chimera_experts.io import Case, load_cases  # noqa: PLC0415
    from chimera_experts.psa_projector import PSAProjectorExpert  # noqa: PLC0415
    return BiopsyExpert, Case, load_cases, PSAProjectorExpert


def _strip(case, drop: tuple[str, ...]):
    """Una copia del caso sin las secciones que la junta no abrió."""
    clinical = {k: v for k, v in (case.clinical or {}).items() if k not in drop}
    return replace(case, clinical=clinical)


def _verdict_payload(v, extra: dict | None = None) -> dict[str, Any]:
    lo, hi = v.interval()
    out = {
        "decision": "yes" if v.decision == 1 else "no",
        "p": round(float(v.probability), 4),
        "ci95": [round(float(lo), 4), round(float(hi), 4)],
        "sigma_model": round(float(v.epistemic_model), 4),
        "sigma_missing": round(float(v.epistemic_missing), 4),
        "sigma": round(float(v.epistemic_total), 4),
        "entropy": round(float(v.aleatoric), 4),
        "completeness": round(float(v.completeness), 4),
        "tier": v.ladder,
        "confidence": v.confidence,
    }
    if extra:
        out.update(extra)
    return out


def _oof_verdicts(expert, cases, y, seed: int = 20260907, n_splits: int = 5) -> dict[str, dict]:
    """Veredictos out-of-fold con la receta exacta del bundle.

    Se clona el ``UncertaintyExpert`` guardado (mismo estimador base, mismo
    número de miembros e imputaciones) y se reajusta en cada partición sobre la
    matriz que el propio experto construye. Sale un veredicto por caso que
    ningún miembro del ensemble ha visto en entrenamiento.
    """
    from sklearn.base import clone  # noqa: PLC0415
    from sklearn.model_selection import StratifiedKFold  # noqa: PLC0415
    from chimera_experts.dataset import completeness_vector  # noqa: PLC0415

    X = expert._matrix(cases)  # noqa: SLF001 — es la API interna del propio experto
    comp = completeness_vector(cases)
    out: dict[str, dict] = {}
    cv = StratifiedKFold(n_splits, shuffle=True, random_state=seed)
    for k, (tr, te) in enumerate(cv.split(X, y), 1):
        member = clone(expert.model).fit(X[tr], y[tr])
        for i, v in zip(te, member.verdicts(X[te], comp[te])):
            out[cases[i].case_id] = _verdict_payload(v, {"fold": k})
        log.info("  fold %d/%d listo (%s)", k, n_splits, expert.name)
    return out


def _fold_ladder_stats(oof: dict[str, dict], labels: dict[str, str]) -> dict[str, dict]:
    """Acierto por tramo, medido sobre las predicciones out-of-fold."""
    stats: dict[str, dict] = {}
    for tier in ("firm", "supports", "discuss"):
        ids = [c for c, v in oof.items() if v["tier"] == tier]
        hits = sum(1 for c in ids if oof[c]["decision"] == labels[c])
        stats[tier] = {"n": len(ids), "hits": hits, "acc": round(hits / len(ids), 4) if ids else None}
    return stats


def _trace_loo(trace_model, cases) -> dict[str, dict]:
    """Traza predicha leave-one-out con el modelo de razonamiento del Experto 4."""
    from copy import deepcopy  # noqa: PLC0415

    out: dict[str, dict] = {}
    labelled = [c for c in cases if c.reasoning]
    for i, c in enumerate(labelled):
        m = deepcopy(trace_model)
        m.models_, m.section_models_, m.kept_ = {}, {}, []
        m.constants_, m.section_rates_, m.metrics_ = {}, {}, {}
        m.fit([x for j, x in enumerate(labelled) if j != i])
        out[c.case_id] = m.predict_trace(_strip(c, ("family_history",)))
        if (i + 1) % 20 == 0:
            log.info("  traza LOO %d/%d", i + 1, len(labelled))
    return out


def build_cache(data_root: Path = DATA, out: Path = CACHE, with_oof: bool = True) -> dict[str, Any]:
    """Pasa los cuatro expertos por todos los casos y guarda el panel."""
    BiopsyExpert, Case, load_cases, PSAProjectorExpert = _imports()  # noqa: N806
    import joblib  # noqa: PLC0415

    cases = load_cases(data_root, task=1)
    labelled = [c for c in cases if c.has_label]
    labels = {c.case_id: ("yes" if str(c.label).lower() == "yes" else "no") for c in labelled}
    y = np.array([1 if labels[c.case_id] == "yes" else 0 for c in labelled])
    log.info("%d casos, %d etiquetados", len(cases), len(labelled))

    trace_bundle = joblib.load(ARTIFACT["trace"])
    trace_model = trace_bundle["model"]
    e1 = BiopsyExpert.load(ARTIFACT["structured"])
    e3 = BiopsyExpert.load(ARTIFACT["fusion"])
    projector = PSAProjectorExpert.load(ARTIFACT["psa"])

    panel: dict[str, Any] = {
        "experts": {
            "structured": {"name": e1.name, "blocks": e1.blocks, "metrics": _clean(e1.metrics),
                           "ladder": _clean(joblib.load(ARTIFACT["structured"]).get("ladder")),
                           "n_features": len(e1.feature_names),
                           "top_features": sorted(e1.importance.items(), key=lambda kv: -kv[1])[:8]},
            "fusion": {"name": e3.name, "blocks": e3.blocks, "metrics": _clean(e3.metrics),
                       "ladder": _clean(joblib.load(ARTIFACT["fusion"]).get("ladder")),
                       "n_features": len(e3.feature_names),
                       "top_features": sorted(e3.importance.items(), key=lambda kv: -kv[1])[:8]},
            "psa": {"champion": getattr(projector, "champion", None)},
            "trace": {"kept": list(getattr(trace_model, "kept_", [])),
                      "metrics": _clean(getattr(trace_model, "metrics_", {}))},
        },
        "cases": {},
    }

    # -- dentro de muestra, en lote ------------------------------------------
    log.info("Experto 1 (A) en lote")
    r1 = e1.report(cases)
    log.info("Experto 3 (A+B+D) en lote, variante completa")
    r3_full = e3.report(cases)
    log.info("Experto 3 (A+B+D) en lote, sin analítica")
    r3_nolab = e3.report([_strip(c, ("laboratory_results",)) for c in cases])
    log.info("Experto 2 (proyección de PSA) y Experto 4 (traza)")
    for c, a, b, d in zip(cases, r1, r3_full, r3_nolab):
        proj = projector.project(c, 6.0).to_dict()
        proj = {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in proj.items()}
        panel["cases"][c.case_id] = {
            "labelled": c.has_label,
            "label": labels.get(c.case_id),
            "available_sources": c.available_sources,
            "deployed": {
                "structured": _verdict_payload(a.verdict),
                "fusion_full": _verdict_payload(b.verdict),
                "fusion_nolab": _verdict_payload(d.verdict),
                "trace": trace_model.predict_trace(_strip(c, ("family_history",))),
            },
            "psa_projection": proj,
        }

    # -- out-of-fold, para el modo honesto ----------------------------------
    if with_oof:
        log.info("Out-of-fold: Experto 1")
        o1 = _oof_verdicts(e1, labelled, y)
        log.info("Out-of-fold: Experto 3 completo")
        o3 = _oof_verdicts(e3, labelled, y)
        log.info("Out-of-fold: Experto 3 sin analítica")
        o3n = _oof_verdicts(e3, [_strip(c, ("laboratory_results",)) for c in labelled], y)
        log.info("Out-of-fold: traza (LOO)")
        ot = _trace_loo(trace_model, labelled)
        for c in labelled:
            panel["cases"][c.case_id]["honest"] = {
                "structured": o1[c.case_id], "fusion_full": o3[c.case_id],
                "fusion_nolab": o3n[c.case_id], "trace": ot[c.case_id],
            }
        panel["oof_ladder"] = {
            "structured": _fold_ladder_stats(o1, labels),
            "fusion_full": _fold_ladder_stats(o3, labels),
            "fusion_nolab": _fold_ladder_stats(o3n, labels),
        }
        for name, o in (("structured", o1), ("fusion_full", o3), ("fusion_nolab", o3n)):
            acc = np.mean([o[c]["decision"] == labels[c] for c in o])
            panel["oof_ladder"][name]["acc_all"] = round(float(acc), 4)
            log.info("OOF %-13s acierto %.3f  tramos %s", name, acc, panel["oof_ladder"][name])

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(panel, indent=1, ensure_ascii=False, default=_json_default))
    log.info("Panel guardado en %s", out)
    return panel


def _clean(obj):
    return json.loads(json.dumps(obj, default=_json_default))


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        v = float(o)
        return None if math.isnan(v) else v
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, float) and math.isnan(o):
        return None
    return str(o)


def _structured_worker(case, artifact: str, conn) -> None:
    try:
        BiopsyExpert, _, _, _ = _imports()  # noqa: N806
        expert = BiopsyExpert.load(Path(artifact))
        serial_predict.serialize_bundles({"structured": expert})
        verdict = expert.report([case])[0]
        conn.send({"ok": True, "payload": _verdict_payload(verdict.verdict)})
    except Exception as exc:  # noqa: BLE001 - el padre decide la ruta segura
        conn.send({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
    finally:
        conn.close()


def _start_structured_process(case):
    if os.environ.get("CHIMERA_EXPERTOS_PARALELOS", "1") == "0":
        return None, None
    try:
        ctx = multiprocessing.get_context("forkserver")
        parent, child = ctx.Pipe(duplex=False)
        proc = ctx.Process(target=_structured_worker, args=(case, str(ARTIFACT["structured"]), child))
        proc.start()
        child.close()
        return proc, parent
    except Exception as exc:  # noqa: BLE001 - brazo de control implícito
        log.warning("No se pudo lanzar structured en paralelo: %s", exc)
        return None, None


# ---------------------------------------------------------------------------
# lectura
# ---------------------------------------------------------------------------


class _DeferredVerdicts(dict):
    """Los veredictos desplegados, con ``fusion_nolab`` aplazado.

    De los 141 s que cuesta puntuar un caso en vivo, ``fusion_nolab`` son 73:
    quitar la analítica mete NaN donde no los había y dispara las diez
    imputaciones. Y de las dos variantes de fusión **sólo se lee una**:
    ``experts_1/fusion.render`` elige ``fusion_full`` si el registrador abrió la
    analítica y ``fusion_nolab`` si no. En los 195 casos de la corrida de
    cobertura la abrió en el 42%, así que cuatro de cada diez casos pagaban 73 s
    por un número que nadie mira.

    Lo que **no** se cambia es el orden: ``fusion_full`` se calcula siempre y
    antes, porque los dos comparten el mismo experto y su imputador sortea con
    un ``RandomState`` que avanza en cada pasada. Calcular ``fusion_nolab``
    saltándose la otra le daría los sorteos de la primera y el número cambiaría.
    Así, cuando de verdad hace falta, sale exactamente el mismo que en la V1.
    """

    def __init__(self, values: dict[str, Any], deferred: Callable[[], Any]) -> None:
        super().__init__(values)
        self._deferred = deferred

    def __missing__(self, key: str):
        if key != "fusion_nolab" or self._deferred is None:
            raise KeyError(key)
        log.info("Se pide fusion_nolab: se puntúa ahora la variante sin analítica")
        value = self[key] = self._deferred()
        return value

    def materialise(self) -> dict[str, Any]:
        """Todas las variantes como ``dict`` normal; para serializar el caché."""
        self["fusion_nolab"]
        return dict(self)


class Panel:
    """El panel precalculado, indexado por caso y por modo."""

    def __init__(self, path: Path = CACHE) -> None:
        self.path = Path(path)
        self.data = json.loads(self.path.read_text())
        self.experts = self.data["experts"]
        self.cases = self.data["cases"]
        self.oof_ladder = self.data.get("oof_ladder", {})

    def has(self, case_id: str) -> bool:
        return case_id in self.cases

    # -- puntuación en vivo: el caso que el caché no tiene ------------------

    #: Atributo de **clase** a propósito: el hilo de ``warmup`` carga los
    #: artefactos en su propio ``Panel``, y el que construye la junta después se
    #: los encuentra aquí en vez de volver a desunpicklar 77 MB.
    _live: dict[str, Any] | None = None

    def _load_live(self) -> dict[str, Any]:
        """Carga perezosa de los cuatro artefactos, sólo si hace falta."""
        if self._live is None:
            import joblib  # noqa: PLC0415
            BiopsyExpert, _, _, PSAProjectorExpert = _imports()  # noqa: N806
            live = {
                "structured": BiopsyExpert.load(ARTIFACT["structured"]),
                "fusion": BiopsyExpert.load(ARTIFACT["fusion"]),
                "psa": PSAProjectorExpert.load(ARTIFACT["psa"]),
                "trace": joblib.load(ARTIFACT["trace"])["model"],
            }
            # Entrenados con n_jobs=-1; puntuando una fila eso es sólo coste de pool.
            serial_predict.serialize_bundles(live)
            Panel._live = self._live = live
            log.info("Artefactos de los expertos cargados para puntuar en vivo")
        return self._live

    def ensure(self, case_id: str, case_files: dict[str, dict]) -> bool:
        """Puntúa en vivo un caso que no está en el caché y lo añade.

        Es la ruta del reto: en Grand Challenge cada caso llega en su propio
        contenedor y nunca está precalculado. Cuesta ~30 s (las 300 pasadas
        del imputador, por tres variantes) y produce exactamente lo que el
        caché guarda para un caso desplegado. Devuelve ``True`` si tuvo que
        calcular algo.
        """
        if case_id in self.cases:
            return False
        from chimera_experts.io import Case  # noqa: PLC0415

        live = self._load_live()
        prompt = case_files.get("prompt") or {}
        clinical = case_files.get("clinical") or {}
        emb = {k: v for k, v in (case_files.get("features") or {}).items() if isinstance(v, list)}
        case = Case(case_id=case_id, task=1, prompt=prompt, clinical=clinical, embeddings=emb)
        t0 = __import__("time").time()
        structured_proc, structured_conn = _start_structured_process(case)
        b = live["fusion"].report([case])[0]
        structured_payload = None
        if structured_proc is not None and structured_conn is not None:
            try:
                if structured_conn.poll(0):
                    msg = structured_conn.recv()
                    if msg.get("ok"):
                        structured_payload = msg["payload"]
                    else:
                        log.warning("Structured paralelo falló: %s", msg.get("error"))
            except (EOFError, OSError) as exc:
                log.warning("Structured paralelo no respondió: %s", exc)
            finally:
                if structured_payload is None and structured_proc.is_alive():
                    structured_proc.terminate()
                structured_proc.join(timeout=1)
                if structured_proc.is_alive():
                    structured_proc.kill()
                    structured_proc.join(timeout=1)
                structured_conn.close()
        if structured_payload is None:
            a = live["structured"].report([case])[0]
            structured_payload = _verdict_payload(a.verdict)

        def _nolab():
            d = live["fusion"].report([_strip(case, ("laboratory_results",))])[0]
            return _verdict_payload(d.verdict)

        proj = live["psa"].project(case, 6.0).to_dict()
        proj = {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in proj.items()}
        self.cases[case_id] = {
            "labelled": False, "label": None, "available_sources": case.available_sources,
            "deployed": _DeferredVerdicts({
                "structured": structured_payload,
                "fusion_full": _verdict_payload(b.verdict),
                "trace": live["trace"].predict_trace(_strip(case, ("family_history",))),
            }, _nolab),
            "psa_projection": proj, "live": True,
        }
        log.info("Caso %s puntuado en vivo por los expertos en %.1f s", case_id, __import__("time").time() - t0)
        return True

    def verdicts(self, case_id: str, mode: str) -> dict[str, Any]:
        """``{"structured", "fusion_full", "fusion_nolab", "trace"}`` para el modo pedido.

        En ``honest`` un caso sin etiqueta no tiene versión out-of-fold — no la
        necesita: nunca estuvo en el entrenamiento — y se devuelve la desplegada.
        """
        entry = self.cases[case_id]
        if mode == "honest" and "honest" in entry:
            return entry["honest"]
        return entry["deployed"]

    def projection(self, case_id: str) -> dict[str, Any]:
        return self.cases[case_id]["psa_projection"]

    def ladder(self, expert: str, mode: str) -> dict[str, dict]:
        """Acierto por tramo: out-of-fold en ambos modos (es lo único que mide algo)."""
        if expert in self.oof_ladder:
            return self.oof_ladder[expert]
        rows = self.experts.get(expert, {}).get("ladder") or []
        return {r["rung"]: {"n": r["n"], "acc": r["accuracy"]} for r in rows}


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Precalcula el panel de expertos")
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(CACHE))
    ap.add_argument("--no-oof", action="store_true")
    a = ap.parse_args()
    build_cache(Path(a.data), Path(a.out), with_oof=not a.no_oof)
