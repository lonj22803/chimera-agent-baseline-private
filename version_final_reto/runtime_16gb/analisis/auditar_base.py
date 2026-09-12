"""Auditoría descriptiva para diseñar V2; no entrena ni cambia la inferencia.

Desde la raíz: PYTHONPATH=src:. .venv/bin/python \
  version_final_reto.runtime_16gb/analisis/auditar_base.py
El evaluador se importa sin llamar a ningún juez ni servicio externo.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "delete_final_versions_task_V1"
OLD = ROOT / "delete_final_versions_task"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-repo", type=Path, default=ROOT.parent / "CHIMERA-agent-eval")
    args = parser.parse_args()
    os.environ["USE_RATIONALE_JUDGE"] = "0"
    sys.path.insert(0, str(args.eval_repo / "evaluation"))
    import evaluate as ev
    from delete_final_versions_task_V1.common.chimera_experts.features_pathology import extract

    evaluator = args.eval_repo / "evaluation/evaluate.py"
    mapping = args.eval_repo / "evaluation/ground_truth/section_variable_mapping.json"
    ev.SECTION_MAPPING_FILE = mapping
    ev._SECTION_VAR_MAPPING = None
    tracked = [evaluator, mapping, V1 / "verification/scores_v1_no_judge.json",
               V1 / "experiments/results/survival_total.json",
               OLD / "resultados/task_2/summary.jsonl",
               V1 / "common/chimera_experts/features_pathology.py",
               V1 / "task_2/agent/protocol.py", V1 / "task_3/agent/protocol.py"]
    result = {"scope": "Auditoría descriptiva de artefactos existentes; ninguna mejora V2 medida",
              "repo_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "evaluator_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.eval_repo, text=True).strip(),
              "cohorts": {}, "sources": {}}
    fingerprints = defaultdict(list)
    input_hashes, label_hashes = [], []
    for task in (1, 2, 3):
        data = ROOT / f"data/task{task}"
        inputs = sorted((data / "agent_input").glob("*/structured-prompt.json"))
        gt = ev.load_ground_truth_records(data / "ground_truth", f"task{task}")
        classes = Counter()
        contradictory = 0
        for record in gt:
            key = (record.get("biopsy_decision") if task == 1 else
                   record.get("treatment_recommendation", {}).get("primary") if task == 2 else
                   str(record.get("event")))
            classes[key] += 1
        for prompt in inputs:
            input_hashes.append((str(prompt.relative_to(ROOT)), sha(prompt)))
            for clinical in prompt.parent.glob("*-clinical-data.json"):
                input_hashes.append((str(clinical.relative_to(ROOT)), sha(clinical)))
                c = read(clinical)
                if task == 2:
                    features = extract(c)
                    contradictory += int(features["path_traj_stable"] == 1 and features["path_traj_progress"] == 1)
            emb = prompt.parent / "prostate-modality-level-neural-representations.json"
            if emb.exists():
                input_hashes.append((str(emb.relative_to(ROOT)), sha(emb)))
                vectors = read(emb).get("MRI image")
                if vectors:
                    digest = hashlib.sha256(json.dumps(vectors, separators=(",", ":")).encode()).hexdigest()
                    fingerprints[digest].append((task, prompt.parent.name))
        result["cohorts"][str(task)] = {"inputs": len(inputs), "labelled": len(gt), "classes": dict(classes)}
        if task == 2:
            result["cohorts"][str(task)]["both_stable_and_progression_flags"] = contradictory
            result["cohorts"][str(task)]["labelled_with_empty_reveal_sequence"] = sum(not r.get("reveal_sequence") for r in gt)
        label_hashes.extend((str(p.relative_to(ROOT)), sha(p)) for p in sorted((data / "ground_truth").glob("*/*.json")))
    result["identical_mri_vectors"] = {
        "groups_with_multiple_records": sum(len(v) > 1 for v in fingerprints.values()),
        "groups_spanning_tasks": sum(len({t for t, _ in v}) > 1 for v in fingerprints.values()),
        "task_combinations": dict(Counter("+".join(map(str, sorted({t for t, _ in v}))) for v in fingerprints.values() if len(v) > 1)),
        "interpretation": "Igualdad de vectores es pista para agrupar, no identidad clínica demostrada; sin IDs publicados."}
    result["data_manifest"] = {
        "inputs_sha256": hashlib.sha256(json.dumps(sorted(input_hashes)).encode()).hexdigest(),
        "labels_sha256": hashlib.sha256(json.dumps(sorted(label_hashes)).encode()).hexdigest(),
        "input_files": len(input_hashes), "label_files": len(label_hashes)}

    # Resultado histórico, separado de la estimación anidada T3.
    frozen = read(V1 / "verification/scores_v1_no_judge.json")
    survival = read(V1 / "experiments/results/survival_total.json")
    c = survival["candidate_c_index"]
    result["baseline"] = {
        "no_judge_artifact": {t: v["ranking_score"] for t, v in frozen.items()},
        "t3_nested_c_index": c, "t3_nested_ci95_delta_vs_capra": survival["paired_ci95"],
        "t3_nested_time_score": survival["time_score"],
        "mixed_no_judge_overall": (2*frozen["task1"]["ranking_score"] + 2*frozen["task2"]["ranking_score"] + c)/5,
        "warning": "El agregado sustituye sólo T3; T1/T2 conservan selección histórica y no son un ensayo externo."}
    pairs = {}
    for task in (1, 2, 3):
        p = V1 / f"experiments/results/paired_judge_task{task}.json"
        tracked.append(p)
        pairs[task] = read(p)
    result["baseline"]["paired_judge"] = [
        {"pass": i+1,
         "t1": pairs[1]["passes"][i]["aggregates"]["candidate"]["ranking_score"],
         "t2": pairs[2]["passes"][i]["aggregates"]["candidate"]["ranking_score"],
         "mixed_overall": (sum(2*pairs[t]["passes"][i]["aggregates"]["candidate"]["ranking_score"] for t in (1, 2))+c)/5}
        for i in (0, 1)]

    # Sólo cambia la declaración de las consultas ya registradas en la misma corrida.
    # Reutilizar el score de prosa aísla el efecto aritmético; NO es una nueva evaluación del juez.
    summaries = [json.loads(s) for s in (OLD / "resultados/task_2/summary.jsonl").read_text().splitlines() if s.strip()]
    labels = {r["case_id"]: r for r in ev.load_ground_truth_records(ROOT / "data/task2/ground_truth", "task2")}
    rationale = {r["case_id"]: r["rationale_score"] for r in pairs[2]["passes"][0]["rows"]["baseline"]}
    modes = {"no_judge": None, "frozen_rationale": lambda g, p: (rationale[g["case_id"]], "score histórico congelado")}
    replay = {"n": len(summaries), "mismatched_reveals": sum(set(r["reveal_sequence"]) != set(r["revealed"]) for r in summaries),
              "source": "Corrida original resultados/task_2; V1 conserva la política de reveal vacío en protocol.trace",
              "interpretation": "Corrección contable sobre decisiones y lecturas congeladas, no política nueva ni evaluación de generalización"}
    for name, judge in modes.items():
        base, honest = [], []
        for r in summaries:
            pred = {"case_id": r["case_id"], "treatment_recommendation": {"primary": r["decision"]},
                    "confidence": r["confidence"], "variable_weights": r["variable_weights"],
                    "reveal_sequence": r["reveal_sequence"], "free_text": r["free_text"]}
            base.append(ev.evaluate_case(labels[r["case_id"]], pred, None, judge))
            honest.append(ev.evaluate_case(labels[r["case_id"]], {**pred, "reveal_sequence": r["revealed"]}, None, judge))
        a, b = ev.compute_aggregate_metrics(base), ev.compute_aggregate_metrics(honest)
        expected = (frozen["task2"]["ranking_score"] if judge is None else
                    pairs[2]["passes"][0]["aggregates"]["baseline"]["ranking_score"])
        assert abs(a["ranking_score"]-expected) < 1e-10, (a["ranking_score"], expected)
        keys = ("ranking_score", "mean_tool_score", "mean_section_grounding_score", "decision_accuracy")
        replay[name] = {"declared": {k: a[k] for k in keys}, "actual_reads": {k: b[k] for k in keys},
                        "overall_delta": 2*(b["ranking_score"]-a["ranking_score"])/5}
    result["t2_reveal_replay"] = replay

    texts = ["No histological progression. ISUP grade group 1.",
             "Timepoint 2: Gleason 3+3, ISUP grade group 1. Timepoint 1: Gleason 3+4, ISUP grade group 2."]
    keys = ["path_traj_stable", "path_traj_progress", "path_isup_first", "path_isup_last", "path_isup_delta"]
    result["synthetic_extractor_probes"] = [{"input": t, "observed": {k: extract({"pathology_report": t})[k] for k in keys}} for t in texts]
    result["synthetic_extractor_probes_note"] = "Pruebas de mecanismo, sin etiquetas clínicas; no cuantifican mejora de decisión."

    selected = read(V1 / "task_3/experts_3/train/artifacts/spokesperson_candidate.json")
    raw = selected["train_raw"]
    result["t3_percentile_export"] = {
        "reference_n": len(raw), "reference_unique": len(set(raw)),
        "formula": "F_train(raw)=(n_ref<raw + 0.5*n_ref==raw)/n_ref",
        "unseen_scalar_bins_upper_bound": len(set(raw))+1,
        "interpretation": "La CDF empírica congelada es desplegable por paciente, pero es escalonada: distintos riesgos nuevos pueden empatar."}

    for path in tracked:
        try:
            key = str(path.relative_to(ROOT))
        except ValueError:
            key = str(path)
        result["sources"][key] = sha(path)
    destination = Path(__file__).with_name("auditoria_base.json")
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    print(json.dumps({k: v for k, v in result.items() if k != "sources"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
