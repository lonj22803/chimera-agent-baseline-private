"""Experto clasificador de la Tarea 1, y su traducción al esquema de CHIMERA.

Un experto es la unión de tres cosas:

1. un conjunto de bloques de variables (qué ficheros de entrada lee);
2. un clasificador envuelto en :class:`~chimera_experts.models.UncertaintyExpert`,
   que produce probabilidad **e** incertidumbre descompuesta;
3. una traducción de esa salida al formulario que el reto exige —
   ``biopsy_decision``, ``confidence``, ``variable_weights``, ``reveal_sequence``
   y ``reasoning``.

La traducción no es cosmética. El esquema del reto puntúa el *razonamiento*
contra la traza del urólogo, de modo que los pesos por variable tienen que
salir de la importancia que el modelo realmente asignó, no de una plantilla.
Aquí se derivan por **importancia de permutación** (Breiman 2001, §10;
formalizada por Fisher, Rudin y Dominici, *All Models are Wrong...*, JMLR
2019), medida out-of-fold para que no refleje el sobreajuste del modelo a su
propio conjunto de entrenamiento.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .dataset import BLOCKS, build_matrix, completeness_vector
from .io import Case
from .uncertainty import Verdict

#: Las diez variables que el formulario de razonamiento de la Tarea 1 puntúa.
#: (``chimera_agent_baseline.output.schema.TASK1_VARIABLES``.)
CHIMERA_TASK1_VARIABLES = ["bx", "fh", "age", "dre", "psa", "vol", "psad", "cspca", "pirads", "comorbidity"]

#: Correspondencia entre las variables internas del modelo y las diez del
#: formulario. Una variable del formulario recibe la importancia **sumada** de
#: todas las columnas que la representan: ``psa`` agrupa el valor, su
#: logaritmo, la velocidad y todo lo derivado de la serie temporal, porque para
#: el urólogo todo eso es "el PSA".
FEATURE_TO_CHIMERA: dict[str, str] = {}


def _register(prefixes: dict[str, str]) -> None:
    FEATURE_TO_CHIMERA.update(prefixes)


_register(
    {
        # --- PSA y todo lo derivado de él ---
        "psa": "psa", "log_psa": "psa", "psa_prev": "psa", "psa_ratio_prev": "psa",
        "psa_delta_prev": "psa", "psav": "psa", "psav_positive": "psa",
        "lab_psa": "psa", "lab_free_psa": "psa", "lab_pct_free_psa": "psa",
        "fpsa_lt10": "psa", "fpsa_lt15": "psa",
        # --- volumen prostático ---
        "vol": "vol", "log_vol": "vol",
        # --- densidad de PSA ---
        "psad": "psad", "psad_calc": "psad", "log_psad": "psad",
        # --- imagen ---
        "pirads": "pirads", "pirads_ge4": "pirads", "pirads_ge3": "pirads",
        "cspca": "cspca",
        # --- exploración ---
        "dre_suspicious": "dre",
        # --- biopsia previa ---
        "bx_none": "bx", "bx_negative": "bx", "bx_positive": "bx",
        "enc_prior_pca": "bx", "enc_prior_negative_bx": "bx", "enc_followup": "bx",
        # --- edad ---
        "age": "age",
        # --- historia familiar ---
        "family_history": "fh",
        # --- comorbilidad ---
        "n_comorbidities": "comorbidity", "charlson_like": "comorbidity",
        "comorbidity_reported": "comorbidity", "bmi": "comorbidity", "ipss": "comorbidity",
        "n_meds": "comorbidity", "on_5ari": "comorbidity", "on_alpha_blocker": "comorbidity",
        "lab_haemoglobin": "comorbidity", "lab_wbc": "comorbidity", "lab_platelets": "comorbidity",
        "lab_creatinine": "comorbidity", "lab_egfr": "comorbidity", "lab_testosterone": "comorbidity",
        "lab_alp": "comorbidity", "lab_ldh": "comorbidity", "lab_hba1c": "comorbidity",
        "log_lab_alp": "comorbidity", "log_lab_ldh": "comorbidity", "lab_n_flagged": "comorbidity",
        "lab_n_reported": "comorbidity", "lab_egfr_low": "comorbidity", "lab_anaemia": "comorbidity",
        "lab_hypogonadal": "comorbidity",
    }
)
# Todo lo que empieza por estos prefijos se asigna por regla, no por tabla.
_PREFIX_RULES = [
    ("pmhx_", "comorbidity"),
    ("psa_", "psa"),          # variables de trayectoria del bloque C
    ("proj_", "psa"),
    ("e2_", "psa"),           # salida del Experto 2
    ("rad_lesion", "pirads"),  # tamaño de la lesión: es un descriptor PI-RADS
    ("rad_zone", "pirads"),
    ("rad_loc", "pirads"),
    ("rad_dwi", "pirads"),
    ("rad_adc", "pirads"),
    ("rad_dce", "pirads"),
    ("rad_t2", "pirads"),
    ("rad_", "pirads"),        # resto del informe radiológico
    ("notes_", "bx"),
    ("months_since_mri", "pirads"),
]


def map_feature(name: str) -> str | None:
    """Variable del formulario a la que contribuye una columna del modelo."""
    if name in FEATURE_TO_CHIMERA:
        return FEATURE_TO_CHIMERA[name]
    # El imputador añade columnas indicadoras "missingindicator_<n>": heredan
    # el destino de la columna que señalan.
    base = name.split("missingindicator_")[-1]
    if base in FEATURE_TO_CHIMERA:
        return FEATURE_TO_CHIMERA[base]
    for prefix, target in _PREFIX_RULES:
        if name.startswith(prefix) or base.startswith(prefix):
            return target
    return None


#: Qué sección de ``*-clinical-data.json`` alimenta cada bloque de variables.
#: Es lo que se declara en ``reveal_sequence``: las secciones que el experto
#: leyó de verdad, en el orden en que las consultaría un lector humano.
BLOCK_TO_SECTIONS = {
    "A": [],
    "B": ["laboratory_results"],
    "C": ["psa_trend"],
    "D": ["radiology_report"],
    "E": ["previous_notes", "family_history"],
    "F": [],
}
SECTION_ORDER = ["radiology_report", "psa_trend", "laboratory_results", "previous_notes", "family_history"]


def reveal_sequence_for(blocks: str) -> list[str]:
    """Secciones consultadas, en el orden canónico del formulario."""
    got = set()
    for b in blocks:
        got.update(BLOCK_TO_SECTIONS.get(b, []))
    return [s for s in SECTION_ORDER if s in got]


def weights_from_importance(
    importance: dict[str, float], blocks: str, threshold_quantiles: tuple[float, float, float] = (0.55, 0.80, 0.93)
) -> dict[str, str]:
    """Convierte importancias por variable en el vocabulario del formulario.

    Los cortes son **cuantiles de la propia distribución de importancia**, no
    umbrales absolutos: lo que el formulario pide es un ordenamiento relativo
    ("cuál pesó más en esta decisión"), y un umbral absoluto sobre una
    importancia de permutación —cuya escala depende de la métrica y del número
    de variables— no sería comparable entre modelos.

    Una variable que el experto no puede ver (porque su bloque no está
    activado) se declara ``not_used``, que es la verdad literal.
    """
    visible = set()
    for b in blocks:
        for f in BLOCKS[b][1].__doc__ or "":
            pass
    # Se determina por presencia efectiva en el diccionario de importancias.
    agg = {v: 0.0 for v in CHIMERA_TASK1_VARIABLES}
    for feat, imp in importance.items():
        tgt = map_feature(feat)
        if tgt in agg:
            agg[tgt] += max(float(imp), 0.0)
            visible.add(tgt)

    vals = np.array([agg[v] for v in CHIMERA_TASK1_VARIABLES], dtype=float)
    pos = vals[vals > 0]
    out: dict[str, str] = {}
    if pos.size == 0:
        return {v: "not_used" for v in CHIMERA_TASK1_VARIABLES}
    q1, q2, q3 = (float(np.quantile(pos, q)) for q in threshold_quantiles)
    for v, val in zip(CHIMERA_TASK1_VARIABLES, vals):
        if v not in visible or val <= 0:
            out[v] = "not_used"
        elif val >= q3:
            out[v] = "decisive"
        elif val >= q2:
            out[v] = "important"
        elif val >= q1:
            out[v] = "noted"
        else:
            out[v] = "noted"
    return out


@dataclass
class ExpertReport:
    """Salida completa de un experto para un caso."""

    case_id: str
    expert: str
    blocks: str
    verdict: Verdict
    variable_weights: dict[str, str]
    reveal_sequence: list[str]
    top_features: list[tuple[str, float]]
    reasoning: str

    def to_chimera_decision(self) -> str:
        """El fichero ``prostate-biopsy-decision.json``: ``"yes"`` o ``"no"``."""
        return "yes" if self.verdict.decision == 1 else "no"

    def to_chimera_reasoning(self) -> dict:
        """El fichero ``prostate-biopsy-decision-reasoning.json``."""
        return {
            "confidence": self.verdict.confidence,
            "variable_weights": self.variable_weights,
            "reveal_sequence": self.reveal_sequence,
            "free_text": self.reasoning,
        }

    def to_expert_payload(self) -> dict:
        """Salida ampliada para el deliberador: incluye la incertidumbre cruda.

        Es lo que un LLM posterior necesita para ponderar este voto: no sólo la
        decisión, sino cuánto se sostiene y por qué evidencia.
        """
        lo, hi = self.verdict.interval()
        return {
            "case_id": self.case_id,
            "expert": self.expert,
            "blocks": self.blocks,
            "decision": self.to_chimera_decision(),
            "probability": round(self.verdict.probability, 4),
            "interval_95": [round(lo, 4), round(hi, 4)],
            "uncertainty": {
                "epistemic_model": round(self.verdict.epistemic_model, 4),
                "epistemic_missing": round(self.verdict.epistemic_missing, 4),
                "epistemic_total": round(self.verdict.epistemic_total, 4),
                "aleatoric_entropy": round(self.verdict.aleatoric, 4),
            },
            "evidence_completeness": round(self.verdict.completeness, 4),
            "reliability_tier": self.verdict.ladder,
            "confidence": self.verdict.confidence,
            "variable_weights": self.variable_weights,
            "reveal_sequence": self.reveal_sequence,
            # La importancia de permutación es lo que movió la predicción; los
            # variable_weights de arriba son lo que el urólogo habría marcado.
            # No tienen por qué coincidir, y la divergencia es informativa.
            "top_features": [{"feature": f, "importance": round(v, 5)} for f, v in self.top_features],
            "reasoning": self.reasoning,
        }


class BiopsyExpert:
    """Experto entrenado, listo para inferencia sobre casos nuevos.

    Si se le adjunta un :class:`~chimera_experts.reasoning_model.ReasoningTraceModel`,
    los ``variable_weights`` y el ``reveal_sequence`` que van al fichero
    puntuable salen de ese modelo —que está entrenado contra las trazas reales
    del urólogo— en lugar de la importancia de permutación. La importancia sigue
    viajando en la carga ampliada, porque responde a otra pregunta: qué movió
    realmente la predicción. Véase la nota de ``reasoning_model``.
    """

    def __init__(self, bundle: dict, trace_model=None):
        self.model = bundle["model"]
        self.blocks = bundle["blocks"]
        self.feature_names = bundle["feature_names"]
        self.importance = bundle.get("importance", {})
        self.name = bundle.get("name", "expert")
        self.metrics = bundle.get("metrics", {})
        self.threshold = bundle.get("threshold", 0.5)
        self.trace_model = trace_model
        self._weights = weights_from_importance(self.importance, self.blocks)
        self._reveal = reveal_sequence_for(self.blocks)

    @classmethod
    def load(cls, path, trace_model_path=None) -> "BiopsyExpert":
        import joblib

        tm = None
        if trace_model_path is not None and Path(trace_model_path).exists():
            tm = joblib.load(trace_model_path)["model"]
        return cls(joblib.load(path), trace_model=tm)

    def _matrix(self, cases: list[Case]) -> np.ndarray:
        """Matriz alineada al orden de columnas visto en entrenamiento."""
        rows = []
        for c in cases:
            feat: dict[str, float] = {}
            for b in self.blocks:
                feat.update(BLOCKS[b][1](c))
            rows.append(feat)
        return np.array([[r.get(n, np.nan) for n in self.feature_names] for r in rows], dtype=float)

    def report(self, cases: list[Case]) -> list[ExpertReport]:
        """Un :class:`ExpertReport` por caso."""
        if isinstance(cases, Case):
            cases = [cases]
        X = self._matrix(cases)
        comp = completeness_vector(cases)
        verdicts = self.model.verdicts(X, comp)
        top = sorted(self.importance.items(), key=lambda kv: -kv[1])[:8]
        out = []
        for c, v in zip(cases, verdicts):
            weights, reveal = dict(self._weights), list(self._reveal)
            if self.trace_model is not None:
                trace = self.trace_model.predict_trace(c)
                weights = trace["variable_weights"]
                # El experto sólo puede declarar como consultadas las secciones
                # que sus bloques realmente leen: predecir que consultó el
                # informe radiológico cuando no lo lee sería una alucinación.
                reveal = [s for s in trace["reveal_sequence"] if s in self._reveal] or self._reveal
            out.append(
                ExpertReport(
                    case_id=c.case_id,
                    expert=self.name,
                    blocks=self.blocks,
                    verdict=v,
                    variable_weights=weights,
                    reveal_sequence=reveal,
                    top_features=top,
                    reasoning=self._reasoning(c, v),
                )
            )
        return out

    def _reasoning(self, case: Case, v: Verdict) -> str:
        """Texto libre trazable: sólo cifras que están en la entrada del caso.

        No se generan afirmaciones clínicas que el JSON no sostenga — el reto
        penaliza explícitamente los hallazgos no respaldados o alucinados.
        """
        p = case.prompt or {}
        bits = []
        pirads = p.get("pirads")
        if pirads not in (None, "", "NA"):
            bits.append(f"PI-RADS {pirads}")
        if isinstance(p.get("psa"), (int, float)):
            bits.append(f"PSA {p['psa']:g} ng/mL")
        if isinstance(p.get("psad"), (int, float)):
            bits.append(f"densidad de PSA {p['psad']:g} ng/mL/mL")
        if isinstance(p.get("vol"), (int, float)):
            bits.append(f"volumen prostático {p['vol']:g} mL")
        if p.get("dre"):
            bits.append(f"tacto rectal {p['dre']}")
        if p.get("bx"):
            bits.append(f"biopsia previa {p['bx']}")
        facts = "; ".join(bits) if bits else "sin variables estructuradas disponibles"

        verdict = "se recomienda biopsia" if v.decision == 1 else "no se recomienda biopsia"
        lo, hi = v.interval()
        tier = {
            "firm": "El intervalo epistémico no cruza el umbral de decisión, de modo que el modelo sostiene este veredicto por sí solo.",
            "supports": "El intervalo epistémico se acerca al umbral: el modelo inclina la decisión, pero no la cierra.",
            "discuss": "El intervalo epistémico cruza el umbral: el modelo no distingue este caso y la decisión debe apoyarse en el resto de la evidencia.",
        }[v.ladder]
        miss = ""
        if v.epistemic_missing > 0.01:
            miss = (
                f" Parte de la incertidumbre ({v.epistemic_missing:.3f} de {v.epistemic_total:.3f}) procede de los "
                "valores ausentes, no del modelo."
            )
        return (
            f"Modelo {self.name} sobre {facts}. Probabilidad de recomendación de biopsia "
            f"{v.probability:.2f} (IC 95 % epistémico {lo:.2f}-{hi:.2f}); {verdict}. {tier}{miss}"
        )

    def write_outputs(self, case: Case, out_dir: str | Path) -> dict[str, Path]:
        """Escribe los dos JSON del reto más la carga ampliada del experto."""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        rep = self.report([case])[0]
        paths = {
            "decision": out_dir / "prostate-biopsy-decision.json",
            "reasoning": out_dir / "prostate-biopsy-decision-reasoning.json",
            "expert": out_dir / f"{self.name}-payload.json",
        }
        paths["decision"].write_text(json.dumps(rep.to_chimera_decision()), encoding="utf-8")
        paths["reasoning"].write_text(json.dumps(rep.to_chimera_reasoning(), indent=2, ensure_ascii=False), encoding="utf-8")
        paths["expert"].write_text(json.dumps(rep.to_expert_payload(), indent=2, ensure_ascii=False), encoding="utf-8")
        return paths
