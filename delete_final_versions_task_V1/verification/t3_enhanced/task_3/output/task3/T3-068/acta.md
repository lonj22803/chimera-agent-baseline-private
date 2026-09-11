# Junta clínica — T3-068 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 71, "psa": 6.6, "dre": null, "active_treatment_prior_to_surgery": null}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 3.0, "group": "intermedio", "ln_unknown": 1.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+4 (ISUP grade group 2), pathological stage pT3a. Extraprostatic extension was present; surgical margins were negative; the seminal vesicles were not invaded; lymphovascular invasion was absent; no lymph nodes were removed."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 3.0, "sec": 4.0, "isup_rp": 2.0, "pt": 3.0, "epe": 1.0, "margins": 0.0, "svi": 0.0, "lvi": 0.0, "ln": null, "tertiary": null, "ln_unknown": 1.0, "pt_ge_t3": 1.0, "tertiary_pattern_5": null, "upgrade_bx_to_rp": null, "capra_s": 3.0, "capra_s_group": 1.0}, "log_risk": -0.35514927620751935, "mode": "deployed", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent one biopsy session. Gleason pattern and ISUP report missing."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": 0.3531096441072678, "mode": "deployed", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 2, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — EXPERT-EXPERIENCE

*case library; the closest labelled precedents and what the reading urologist did with them* · vuelta 1

I recall these other postoperative patients in the same CAPRA-S group. Each outcome belongs to another patient, not this patient. These observations cannot estimate this patient's survival or recurrence date.
Another patient, T3-057: CAPRA-S 3.0; observed recurrence at 36.7 months. Do not copy this outcome into the current note.
Another patient, T3-048: CAPRA-S 3.0; observed censored follow-up without recurrence at 42.3 months. Do not copy this outcome into the current note.
Another patient, T3-050: CAPRA-S 3.0; observed recurrence at 10.9 months. Do not copy this outcome into the current note.

## Intervención 6 — EXPERT-GUIDELINE

*EXPERT-GUIDELINE* · vuelta 1

{"authority": "advisory; no vote or numeric horizon", "clinical_eau_group_from_G": "not recorded", "scope": "G is pre-treatment clinical stratification; not a postoperative EAU/NCCN classification.", "postoperative_findings": {"epe": 1.0, "margins": 0.0, "svi": 0.0, "lvi": 0.0, "ln_unknown": 1.0}, "follow_up": "Postoperative PSA and its trajectory are needed; pathology alone does not establish biochemical recurrence.", "reference": "EAU Prostate Cancer: Follow-up, https://uroweb.org/guidelines/prostate-cancer/chapter/followup", "retrieval": "deterministic inventory; no guideline passage was retrieved"}

## Intervención 7 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 8 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+4 (ISUP grade group 2), pathological stage pT3a. Extraprostatic extension was present; surgical margins were negative; the seminal vesicles were not invaded; lymphovascular invasion was absent; no lymph nodes were removed.", "pathology_report": "The patient underwent one biopsy session. Gleason pattern and ISUP report missing.", "radiology_report": "Prostate volume: 30.37 cc. PSA density: 0.217 ng/mL/cc. PI-RADS: 4. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.6730961.", "previous_notes": null}

## Intervención 9 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": 0.019064769036952384, "mode": "deployed", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 10 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 3.0, "spokesperson": "nested-selected fusion", "rule": "Selection inside outer folds; DEV, VAL and full-cohort results recorded."}

## Intervención 11 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 43.458639527810675, "event": 0, "calibration": {"mode": "deployed", "a": 93.67296967731494, "b": 0.1, "spokesperson": "nested-selected fusion", "percentile": 0.3933333333333333, "months_map": "90 exp(-0.1 * 12 * (1-percentile))", "event_policy": "unchanged CAPRA event policy", "validation": {"n": 75, "events": 19, "baseline_c_index": 0.7371681415929203, "candidate_c_index": 0.8234513274336284, "paired_ci95": [-0.004138922865375535, 0.20206167181978793], "eligible": true, "adopted": false, "limitations": "Small internal historical cohort; wide paired intervals; not external validation. Model selection is inside each outer fold."}}}, "uncertainty": {"interval_months": [26.075183716686404, 60.842095338934946], "base_half_width": 8.691727905562136, "imputation_half_width": 8.691727905562136, "ln_unknown": true, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 12 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": ["previous_notes"], "ln_unknown": true, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "No nodes sampled; pNx is not pN0."}

## Intervención 13 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The postoperative pathology indicates a Gleason 3+4 (ISUP grade group 2) and pathological stage pT3a. Favorable findings include negative surgical margins, absence of seminal vesicle invasion, and absence of lymphovascular invasion. The absence of documented nodal sampling means that the pNx status does not establish node-negative disease, which widens the uncertainty regarding regional spread. The preoperative PSA level is not documented. The primary prognostic factors are the T3a extension and the pNx nodal status. Countervailing findings are the negative surgical margins and the absence of seminal vesicle invasion. Postoperative PSA and its subsequent trajectory are critical missing pieces of information that would revise the prognosis. Missing nodal sampling limits the ability to fully assess the extent of disease. The fixed estimated horizon is 43.46 months. This represents expected follow-up without an event, not a known recurrence date. The sensitivity range is 26.08–60.84 months; its coverage has not been validated.
