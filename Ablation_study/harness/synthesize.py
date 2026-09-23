"""Construye la tabla maestra y define/valida la ablacion conjunta A_min."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
import csv
import json
from pathlib import Path
from statistics import fmean
from typing import Any

from .catalogo import Intervention, load_catalog
from .classify import classify, global_verdict
from .paths import RESULTS, RUNS
from .run_tier_s import _compare
from .sim import score_rows, simulate_variant
from .stats import BOOTSTRAP_RESAMPLES, COMPONENTS
from .validate_arm import _outputs, _prediction_row
from .variants import load_variants

SOURCES: dict[str, tuple[str, ...]] = {
    "N03": ("S-E1",),
    "N04": ("S-COH",),
    "N05": ("S-LIB-off",),
    "N06": ("S-W-noted", "S-PLAN-todo"),
    "N10": ("S-PLAN-nada",),
    "N11": ("S-PSA-off",),
    "N12": ("S-E3",),
    "M1": ("S-M1",),
    "M2": ("S-M2",),
    "M3": ("S-M3",),
    "M4": ("S-M4",),
    "M5": ("S-E1E3",),
    "M6": ("S-A-libvote",),
    "M8": ("S-C-trace",),
    "M9": ("S-W-noted",),
    "M10": ("S-PLAN-todo",),
    "M11": ("S-G-off",),
    "M12": ("S-G-bx",),
    "M13": ("S-DOC-prev", "S-DOC-rad", "S-DOC-lab", "S-DOC-psa"),
}

ARM_BY_ID = {
    "N07": "L1",
    "N08": "L2",
    "N14": "L3",
    "N15": "L5",
    "G1": "L6",
    "G2": "L6",
    "G3": "L7",
    "G6": "L2",
}

AMIN_FLAGS = {
    "N07": "remove_eau",
    "N08": "remove_moderator",
    "G6": "remove_moderator",
    "N09": "disable_image",
    "N14": "remove_verifier",
    "N15": "deterministic_chair",
    "G1": "disable_provenance_guards",
    "G2": "disable_provenance_guards",
    "G3": "disable_process_guard",
}


def _load(name: str) -> Any:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def _combine(verdicts: list[str], level: str) -> str:
    stable = f"NECESARIA_{level}"
    fragile = f"NECESARIA_FRAGIL_{level}"
    spare = {"SOBRA", f"SOBRA_{level}"}
    harmful = f"PERJUDICIAL_{level}"
    if stable in verdicts:
        return stable
    if fragile in verdicts:
        return fragile
    if verdicts and all(verdict in spare for verdict in verdicts):
        return f"SOBRA_{level}"
    if harmful in verdicts:
        return harmful
    return f"INDETERMINADA_{level}"


def _s_variant_evidence() -> dict[str, dict[str, Any]]:
    loo = {
        row["id"]: row
        for row in _load("S_loo.json")["rows"]
        if row["mode"] == "honest"
    }
    robust = {
        row["id"]: row["modes"]["honest"]["same_sign"]
        for row in _load("S_robustez.json")["rows"]
    }
    variants = load_variants()
    baseline_raw = simulate_variant(variants["A0"].spec, "honest")
    baseline_scored = score_rows(baseline_raw)["rows"]
    addback_raw = simulate_variant(variants["S-A-libvote"].spec, "honest")
    loo["S-A-libvote"] = {
        "id": "S-A-libvote",
        "overall": _compare(
            baseline_scored,
            score_rows(addback_raw)["rows"],
            resamples=BOOTSTRAP_RESAMPLES,
        ),
        "changed_cases": [
            row["case_id"]
            for row, other in zip(baseline_raw, addback_raw)
            if row["pred"]["biopsy_decision"] != other["pred"]["biopsy_decision"]
        ],
        "mcnemar_holm_p": 1.0,
    }
    robust["S-A-libvote"] = True

    evidence = {}
    for variant_id, row in loo.items():
        metrics = row["overall"]["metrics"]
        changed = len(row.get("changed_cases") or [])
        rank = metrics["ranking"]
        d_verdict = classify(
            rank["delta"],
            tuple(rank["ci95"]),
            level="D",
            p_value=row.get("mcnemar_holm_p", row["overall"]["mcnemar"]["p_value"]),
            exact_zero=changed == 0 and rank["delta"] == 0,
            same_sign=bool(robust.get(variant_id, True)),
        )
        f_deltas = {name: metrics[name]["delta"] for name in COMPONENTS}
        f_intervals = {name: tuple(metrics[name]["ci95"]) for name in COMPONENTS}
        f_verdict = classify(
            f_deltas,
            f_intervals,
            level="F",
            exact_zero=all(value == 0 for value in f_deltas.values()),
        )
        evidence[variant_id] = {
            "source": variant_id,
            "d": {
                "delta": rank["delta"],
                "ci95": rank["ci95"],
                "p_holm": row.get("mcnemar_holm_p", row["overall"]["mcnemar"]["p_value"]),
                "changed_cases": changed,
                "verdict": d_verdict,
            },
            "f": {"deltas": f_deltas, "ci95": f_intervals, "verdict": f_verdict},
        }
    return evidence


def _l_evidence() -> dict[str, dict[str, Any]]:
    rows = {row["arm"]: row for row in _load("L_efectos.json")["rows"]}
    evidence = {}
    for arm, row in rows.items():
        metrics = row["versus_l0"]["metrics"]
        rank = metrics["ranking"]
        decision_changes = row["changes_vs_l0"]["by_field"]["biopsy_decision"]
        d_verdict = classify(
            rank["delta"],
            tuple(rank["ci95"]),
            level="D",
            p_value=row["mcnemar_holm_p"],
            exact_zero=decision_changes == 0,
        )
        f_deltas = {name: metrics[name]["delta"] for name in COMPONENTS}
        f_intervals = {name: tuple(metrics[name]["ci95"]) for name in COMPONENTS}
        evidence[arm] = {
            "source": arm,
            "d": {
                "delta": rank["delta"],
                "ci95": rank["ci95"],
                "p_holm": row["mcnemar_holm_p"],
                "changed_cases": decision_changes,
                "verdict": d_verdict,
            },
            "f": {
                "deltas": f_deltas,
                "ci95": f_intervals,
                "verdict": classify(
                    f_deltas,
                    f_intervals,
                    level="F",
                    exact_zero=all(value == 0 for value in f_deltas.values()),
                ),
            },
        }
    return evidence


def _costs() -> dict[str, dict[str, float]]:
    out = {}
    for arm in ("L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L0p"):
        rows = [json.loads(line) for line in (RUNS / arm / "summary.jsonl").read_text().splitlines() if line]
        latest = {row["case_id"]: row for row in rows if row.get("ok")}
        out[arm] = {
            "seconds": fmean(float(row.get("seconds") or 0) for row in latest.values()),
            "tokens": fmean(float(row.get("tel_tokens_approx") or 0) for row in latest.values()),
            "llm_calls": fmean(float(row.get("tel_llm_calls") or 0) for row in latest.values()),
        }
    return out


def _representative(items: list[dict[str, Any]], key: str) -> dict[str, Any]:
    if key == "d":
        return max(items, key=lambda item: abs(float(item["d"]["delta"])))
    return max(items, key=lambda item: max(abs(float(value)) for value in item["f"]["deltas"].values()))


def _recommendation(item_id: str, verdict: str, audit: dict[str, dict[str, Any]]) -> str:
    if item_id in {"G1", "G2", "G3"} and audit[item_id]["violations"]:
        return "mantener por integridad aunque el efecto medio sea equivalente"
    if verdict.startswith("NECESARIA") or verdict == "ESTRUCTURAL":
        return "mantener"
    if verdict == "SOBRA":
        return "retirar o simplificar"
    if verdict.startswith("SOBRA_DF"):
        return "no retirar sin medir narrativa"
    if verdict == "PERJUDICIAL":
        return "retirar"
    return "mantener; evidencia insuficiente"


def build_master() -> dict[str, Any]:
    s_evidence = _s_variant_evidence()
    l_evidence = _l_evidence()
    judge = {row["arm"]: row for row in _load("J_efectos.json")["rows"]}
    delta_n = _load("J_efectos.json")["delta_n"]
    audit_rows = {row["arm"]: row for row in _load("N_audit.json")["rows"]}
    audit = {
        "G1": {"violations": audit_rows["L6"]["unsourced_value_cases"]},
        "G2": {"violations": audit_rows["L6"]["unsourced_grade_cases"]},
        "G3": {"violations": audit_rows["L7"]["process_language_cases"]},
    }
    costs = _costs()
    baseline_cost = costs["L0"]
    rows = []
    for item in load_catalog().intervenciones:
        if not item.tier:
            continue
        evidences = [s_evidence[source] for source in SOURCES.get(item.id, ())]
        arm = ARM_BY_ID.get(item.id)
        if arm:
            evidences.append(l_evidence[arm])

        if item.id == "N09":
            d = {"delta": 0.0, "ci95": [0.0, 0.0], "p_holm": 1.0, "changed_cases": 0, "verdict": "SOBRA_D"}
            f = {"deltas": {name: 0.0 for name in COMPONENTS}, "ci95": {name: [0.0, 0.0] for name in COMPONENTS}, "verdict": "SOBRA_F"}
            n = {"delta": 0.0, "ci95": [0.0, 0.0], "verdict": "SOBRA_N", "n": 74}
            sources = ["L0: 0 activaciones"]
        elif item.id == "N13":
            d = {"delta": None, "ci95": None, "p_holm": None, "changed_cases": None, "verdict": "ESTRUCTURAL"}
            f = {"deltas": {}, "ci95": {}, "verdict": "ESTRUCTURAL"}
            n = None
            sources = ["mecanismos M1-M13"]
        else:
            if not evidences:
                raise ValueError(f"Sin evidencia D/F para {item.id}.")
            d_rep = _representative(evidences, "d")
            f_rep = _representative(evidences, "f")
            d = {**d_rep["d"], "verdict": _combine([entry["d"]["verdict"] for entry in evidences], "D")}
            f = {**f_rep["f"], "verdict": _combine([entry["f"]["verdict"] for entry in evidences], "F")}
            n = None
            if arm in judge:
                j = judge[arm]
                n = {"delta": j["delta"], "ci95": j["ci95"], "verdict": j["verdict_n"], "n": j["n"]}
            sources = [entry["source"] for entry in evidences]

        if item.id == "N13":
            verdict = "ESTRUCTURAL"
            measured = []
        else:
            levels = {"D": d["verdict"], "F": f["verdict"]}
            measured = ["D", "F"]
            if n is not None:
                levels["N"] = n["verdict"]
                measured.append("N")
            verdict = global_verdict(levels, measured=tuple(measured))

        cost = None
        if arm:
            cost = {
                "arm": arm,
                "delta_seconds": costs[arm]["seconds"] - baseline_cost["seconds"],
                "delta_tokens": costs[arm]["tokens"] - baseline_cost["tokens"],
                "delta_llm_calls": costs[arm]["llm_calls"] - baseline_cost["llm_calls"],
            }
        confidence = "alta" if verdict in {"SOBRA", "ESTRUCTURAL"} or verdict.startswith("NECESARIA") else "media"
        row = {
            "id": item.id,
            "name": item.nombre,
            "tiers": list(item.tier),
            "hypotheses": list(item.hipotesis),
            "sources": sources,
            "d": d,
            "f": f,
            "n": n,
            "delta_n": delta_n if n is not None else None,
            "cost": cost,
            "verdict": verdict,
            "confidence": confidence,
            "recommendation": _recommendation(item.id, verdict, audit) if item.id in audit or verdict else "",
        }
        rows.append(row)

    payload = {
        "date": date.today().isoformat(),
        "delta_n": delta_n,
        "n_rows": len(rows),
        "indeterminate": [row["id"] for row in rows if row["verdict"] == "INDETERMINADA"],
        "rows": rows,
    }
    (RESULTS / "tabla_maestra.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    flat = []
    for row in rows:
        cost = row["cost"] or {}
        flat.append(
            {
                "id": row["id"],
                "intervention": row["name"],
                "tiers": ",".join(row["tiers"]),
                "sources": ",".join(row["sources"]),
                "verdict_d": row["d"]["verdict"],
                "delta_ranking": row["d"]["delta"],
                "ci_low_ranking": row["d"]["ci95"][0] if row["d"]["ci95"] else None,
                "ci_high_ranking": row["d"]["ci95"][1] if row["d"]["ci95"] else None,
                "verdict_f": row["f"]["verdict"],
                "verdict_n": row["n"]["verdict"] if row["n"] else None,
                "delta_narrative": row["n"]["delta"] if row["n"] else None,
                "cost_seconds_delta": cost.get("delta_seconds"),
                "cost_tokens_delta": cost.get("delta_tokens"),
                "verdict": row["verdict"],
                "confidence": row["confidence"],
                "recommendation": row["recommendation"],
            }
        )
    with (RESULTS / "tabla_maestra.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    return payload


def build_amin(master: dict[str, Any]) -> dict[str, Any]:
    spare = [row["id"] for row in master["rows"] if row["verdict"] == "SOBRA"]
    flags = sorted({AMIN_FLAGS[item] for item in spare if item in AMIN_FLAGS})
    config = {
        "date": date.today().isoformat(),
        "spare_interventions": spare,
        "flags": {name: name in flags for name in sorted(set(AMIN_FLAGS.values()))},
    }
    (RESULTS / "A_min_config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    output_count = len(_outputs(RUNS / "L9"))
    report: dict[str, Any] = {**config, "requires_l9": bool(flags), "outputs": output_count, "accepted": False}
    if not flags:
        report.update({"requires_l9": False, "accepted": True, "arm": "L0", "delta_ranking": 0.0, "ci95": [0.0, 0.0]})
    elif output_count == 91:
        baseline = [_prediction_row(case_id, folder) for case_id, folder in sorted(_outputs(RUNS / "L0").items())]
        variant = [_prediction_row(case_id, folder) for case_id, folder in sorted(_outputs(RUNS / "L9").items())]
        comparison = _compare(score_rows(baseline)["rows"], score_rows(variant)["rows"], resamples=BOOTSTRAP_RESAMPLES)
        rank = comparison["metrics"]["ranking"]
        report.update(
            {
                "accepted": True,
                "arm": "L9",
                "delta_ranking": rank["delta"],
                "ci95": rank["ci95"],
                "changed_decisions": comparison["mcnemar"]["n"],
                "h16": "confirmada" if abs(rank["delta"]) < 0.010 else "refutada",
            }
        )
    (RESULTS / "A_min.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def run() -> tuple[dict[str, Any], dict[str, Any]]:
    master = build_master()
    return master, build_amin(master)


def main() -> int:
    master, amin = run()
    print(json.dumps({"master_rows": master["n_rows"], "amin": amin}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
