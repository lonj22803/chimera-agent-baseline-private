"""Simulador parametrizable para las ablaciones Tier S de la Tarea 1."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
from typing import Any

from version_final_reto.task_1.agent import protocol as P
from version_final_reto.task_1.agent.decide import documented_grade, enforce_grounding
from version_final_reto.task_1.experts_1 import cohort as cohort_expert
from version_final_reto.task_1.experts_1 import trace as trace_expert
from version_final_reto.task_1.experts_1.experience import ProfessionalExperience
from version_final_reto.task_1.experts_1.panel import CACHE, Panel

from .paths import DATA, EVAL_REPO

os.environ.setdefault("USE_RATIONALE_JUDGE", "0")

DOCUMENTS = (
    "previous_notes",
    "radiology_report",
    "laboratory_results",
    "psa_trend",
)
PLAN_POLICIES = frozenset({"trace", "bucket", "all", "none"})
GROUNDING_POLICIES = frozenset({"default", "off", "strict_bx"})
WEIGHTS_POLICIES = frozenset({"model+mode", "mode", "model", "noted"})
CONFIDENCE_POLICIES = frozenset({"agreement", "trace", "clear"})
FORM_WEIGHTS_POLICIES = frozenset({"trace", "board"})


@dataclass(frozen=True)
class VariantSpec:
    """Todos los puntos de gancho Tier S, sin estado mutable compartido."""

    id: str = "A0"
    cohort_none: bool = True
    cohort_negative: bool = True
    cohort_positive_psa: bool = True
    cohort_positive_age: bool = True
    cohort_positive_pirads: bool = True
    grade_ge2: bool = True
    grade_gg1: bool = True
    structured: bool = True
    fusion: bool = True
    library: bool = True
    psa: bool = True
    plan: str = "trace"
    closed_documents: tuple[str, ...] = ()
    weights_policy: str = "model+mode"
    confidence_policy: str = "agreement"
    grounding: str = "default"
    form_weights: str = "trace"
    library_weight: float = 0.0
    threshold: float = 0.45
    fusion_mult: float = 1.5
    tiers: tuple[tuple[str, float], ...] = (
        ("firm", 3.0),
        ("supports", 2.0),
        ("discuss", 1.0),
    )

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("VariantSpec.id no puede estar vacio.")
        if self.plan not in PLAN_POLICIES:
            raise ValueError(f"Politica de plan desconocida: {self.plan}.")
        if self.grounding not in GROUNDING_POLICIES:
            raise ValueError(f"Politica de grounding desconocida: {self.grounding}.")
        if self.weights_policy not in WEIGHTS_POLICIES:
            raise ValueError(f"Politica de pesos desconocida: {self.weights_policy}.")
        if self.confidence_policy not in CONFIDENCE_POLICIES:
            raise ValueError(f"Politica de confianza desconocida: {self.confidence_policy}.")
        if self.form_weights not in FORM_WEIGHTS_POLICIES:
            raise ValueError(f"Politica de formulario desconocida: {self.form_weights}.")
        unknown_documents = set(self.closed_documents) - set(DOCUMENTS)
        if unknown_documents:
            raise ValueError(f"Documentos desconocidos: {sorted(unknown_documents)}.")
        tier_names = [name for name, _ in self.tiers]
        if set(tier_names) != {"firm", "supports", "discuss"} or len(tier_names) != 3:
            raise ValueError("tiers debe definir firm, supports y discuss una sola vez.")
        if any(weight < 0 for _, weight in self.tiers):
            raise ValueError("Los pesos de tramo no pueden ser negativos.")
        if not 0 <= self.threshold <= 1:
            raise ValueError("threshold debe estar entre 0 y 1.")


A0 = VariantSpec()


def _corpus(clinical: dict[str, Any], opened: list[str]) -> str:
    parts = []
    for section in opened:
        value = clinical.get(section)
        if value is not None:
            parts.append(json.dumps(value, ensure_ascii=False))
    return "\n".join(parts)


def _cohort_for(spec: VariantSpec, payload: dict[str, Any]) -> dict[str, Any]:
    _, cohort = cohort_expert.render(payload)
    bx = str(payload.get("bx") or "None")
    enabled = True
    if bx == "None":
        enabled = spec.cohort_none
    elif bx == "Negative":
        enabled = spec.cohort_negative
    elif bx == "Positive":
        enabled = {
            "psa_ge_20": spec.cohort_positive_psa,
            "age_ge_78": spec.cohort_positive_age,
            "pirads_le_2": spec.cohort_positive_pirads,
        }.get(cohort.get("fired"), True)
    if not enabled:
        cohort = {**cohort, "verdict": None}
    weights, confidence, _ = cohort_expert.variables_for(cohort)
    return {**cohort, "variable_weights": weights, "confidence": confidence}


def _trace_for(
    spec: VariantSpec,
    panel: Panel,
    case_id: str,
    mode: str,
    library_result: dict[str, Any] | None,
    bucket_mode: dict[str, Any] | None,
) -> dict[str, Any]:
    policy = spec.weights_policy
    trace = trace_expert.predict(panel, case_id, mode, library_result, bucket_mode, weights_policy=policy)
    if policy == "noted":
        trace = {**trace, "variable_weights": {name: "noted" for name in trace_expert.VARIABLES}}

    if spec.plan == "bucket":
        rates = (bucket_mode or {}).get("section_rates") or {}
        reveal = [
            section
            for section in trace_expert.SECTION_ORDER
            if section not in trace_expert.NEVER and rates.get(section, 0) >= 0.5
        ]
    elif spec.plan == "all":
        reveal = list(DOCUMENTS)
    elif spec.plan == "none":
        reveal = []
    else:
        reveal = list(trace["reveal_sequence"])
    closed = set(spec.closed_documents)
    return {**trace, "reveal_sequence": [section for section in reveal if section not in closed]}


def _grade_for(spec: VariantSpec, clinical: dict[str, Any], opened: list[str]) -> dict[str, Any]:
    grade = documented_grade(_corpus(clinical, opened))
    gg = grade.get("gg")
    if (gg == 1 and not spec.grade_gg1) or (isinstance(gg, int) and gg >= 2 and not spec.grade_ge2):
        return {**grade, "gg": None}
    return grade


def _params(spec: VariantSpec) -> dict[str, Any]:
    confidence_policy = "trace" if spec.confidence_policy in {"trace", "clear"} else "agreement"
    return {
        **P.PARAMS,
        "tier_weight": dict(spec.tiers),
        "fusion_mult": spec.fusion_mult,
        "library_weight": spec.library_weight,
        "threshold": spec.threshold,
        "grade_rule": spec.grade_ge2 or spec.grade_gg1,
        "confidence_policy": confidence_policy,
        "form_weights": spec.form_weights,
    }


def _apply_grounding(
    spec: VariantSpec, prediction: dict[str, Any], opened: list[str]
) -> dict[str, Any]:
    if spec.grounding == "off":
        return prediction
    grounded, _ = enforce_grounding(prediction, opened)
    if spec.grounding == "strict_bx":
        weights = dict(grounded["variable_weights"])
        weights["bx"] = "not_used"
        grounded = {**grounded, "variable_weights": weights}
    return grounded


def simulate_variant(
    spec: VariantSpec,
    mode: str,
    *,
    panel: Panel | None = None,
    all_cases: bool = False,
    only: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Simula una variante usando las mismas funciones y datos que la V4."""
    if mode not in {"deployed", "honest"}:
        raise ValueError("mode debe ser 'deployed' u 'honest'.")
    panel = panel or Panel(Path(CACHE))
    library = ProfessionalExperience(DATA, exclude_self=True, k=3) if spec.library else None
    case_root = DATA / ("agent_input" if all_cases else "ground_truth")
    rows: list[dict[str, Any]] = []

    for directory in sorted(path for path in case_root.iterdir() if path.is_dir()):
        case_id = directory.name
        if only and case_id not in only:
            continue
        input_root = DATA / "agent_input" / case_id
        payload = json.loads((input_root / "structured-prompt.json").read_text())
        clinical = json.loads(
            (input_root / "prostate-biopsy-decision-clinical-data.json").read_text()
        )
        cohort = _cohort_for(spec, payload)

        library_result = library.recall(case_id, payload) if library is not None else None
        bucket_mode = (
            library.bucket_mode(str(payload.get("bx") or "None"), exclude=case_id)
            if library is not None
            else None
        )
        trace = _trace_for(spec, panel, case_id, mode, library_result, bucket_mode)
        opened = list(trace["reveal_sequence"])

        verdicts = panel.verdicts(case_id, mode)
        structured = (
            {**verdicts["structured"], "available": True}
            if spec.structured
            else {"available": False}
        )
        if spec.fusion and "radiology_report" in opened:
            variant = "fusion_full" if "laboratory_results" in opened else "fusion_nolab"
            fusion = {**verdicts[variant], "available": True, "variant": variant}
        else:
            fusion = {"available": False}

        structured["variable_weights"] = panel.experts["structured"].get("form_weights") or {}
        if fusion.get("available"):
            fusion["variable_weights"] = dict(panel.experts["fusion"].get("form_weights") or {})
            if "laboratory_results" not in opened:
                fusion["variable_weights"]["dre"] = "not_used"

        psa_view = (
            {"variable_weights": {"psa": "noted"}}
            if spec.psa and "psa_trend" in opened
            else {}
        )
        # M11 vive en dos capas: ``variable_view`` aterriza antes de devolver
        # el formulario y ``enforce_grounding`` vuelve a comprobarlo al final.
        # Para apagarla por completo se presenta a la primera capa un conjunto
        # de fuentes exhaustivo, sin alterar los documentos realmente abiertos.
        protocol_opened = (
            list(trace_expert.SECTION_ORDER) if spec.grounding == "off" else opened
        )
        result = P.consolidate(
            payload,
            cohort,
            structured,
            fusion,
            library_result,
            trace,
            _grade_for(spec, clinical, opened),
            protocol_opened,
            params=_params(spec),
            psa=psa_view,
        )
        confidence = "clear" if spec.confidence_policy == "clear" else result["confidence"]
        prediction = {
            "biopsy_decision": result["decision"],
            "confidence": confidence,
            "variable_weights": dict(result["variable_weights"]),
            "reveal_sequence": opened,
            "free_text": "simulated",
            "case_id": case_id,
        }
        prediction = _apply_grounding(spec, prediction, opened)
        rows.append(
            {
                "case_id": case_id,
                "pred": prediction,
                "rule": result["rule"],
                "who": result["who"],
                "bx": payload.get("bx"),
            }
        )
    return rows


def _evaluator():
    evaluation = EVAL_REPO / "evaluation"
    if str(evaluation) not in sys.path:
        sys.path.insert(0, str(evaluation))
    import evaluate  # noqa: PLC0415

    return evaluate


def _binary(value: Any) -> int:
    return int(value is True or str(value).strip().lower() == "yes")


def score_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Puntua filas etiquetadas con el evaluador oficial y conserva su traza."""
    evaluator = _evaluator()
    ground_truth = {
        evaluator.get_case_id(record): record
        for record in evaluator.load_ground_truth_records(DATA / "ground_truth", "task1")
    }
    source_by_case = {row["case_id"]: row for row in rows}
    evaluated = [
        evaluator.evaluate_case(ground_truth[case_id], source_by_case[case_id]["pred"], None, None)
        for case_id in sorted(source_by_case)
        if case_id in ground_truth
    ]
    aggregate = evaluator.compute_aggregate_metrics(evaluated)
    components = {}
    component_names = (
        "confidence_score",
        "variable_weight_score",
        "important_decisive_factor_score",
        "tool_score",
        "section_grounding_score",
    )
    for name in component_names:
        values = [row[name] for row in evaluated if row.get(name) is not None]
        components[name] = sum(values) / len(values) if values else None

    scored_rows = []
    by_bucket: dict[str, list[int]] = {}
    for evaluated_row in evaluated:
        source = source_by_case[evaluated_row["case_id"]]
        bucket = str(source["bx"])
        by_bucket.setdefault(bucket, [0, 0])
        by_bucket[bucket][0] += int(evaluated_row["decision_score"] == 1.0)
        by_bucket[bucket][1] += 1
        scored_rows.append(
            {
                "case_id": source["case_id"],
                "decision_score": evaluated_row["decision_score"],
                "case_score": evaluated_row["case_score"],
                **{name: evaluated_row[name] for name in component_names},
                "rule": source["rule"],
                "who": source["who"],
                "bx": source["bx"],
                "pred": _binary(source["pred"]["biopsy_decision"]),
                "gt": _binary(evaluated_row["gt_decision"]),
            }
        )

    return {
        "ranking": aggregate["ranking_score"],
        "mean_case": aggregate["mean_case_score"],
        "f1_yes": aggregate["decision_f1_yes"],
        "gate": aggregate["decision_accuracy"],
        "components": components,
        "by_bucket": {key: f"{hits}/{total}" for key, (hits, total) in by_bucket.items()},
        "rows": scored_rows,
    }
