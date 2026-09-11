# Junta clínica — T3-044 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 55, "psa": 5.9, "dre": null, "active_treatment_prior_to_surgery": null}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 1.0, "group": "bajo", "ln_unknown": 0.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+4 (ISUP grade group 2), pathological stage pT2c. There was no extraprostatic extension; surgical margins were negative; the seminal vesicles were not invaded; lymphovascular invasion was absent; there was no lymph node metastasis."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 3.0, "sec": 4.0, "isup_rp": 2.0, "pt": 2.0, "epe": 0.0, "margins": 0.0, "svi": 0.0, "lvi": 0.0, "ln": 0.0, "tertiary": null, "ln_unknown": 0.0, "pt_ge_t3": 0.0, "tertiary_pattern_5": null, "upgrade_bx_to_rp": null, "capra_s": 1.0, "capra_s_group": 0.0}, "log_risk": -0.3248266223772868, "mode": "deployed", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent one biopsy session. Gleason pattern and ISUP report missing."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": -0.26458093393376375, "mode": "deployed", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 1, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — EXPERT-EXPERIENCE

*case library; the closest labelled precedents and what the reading urologist did with them* · vuelta 1

I recall these other postoperative patients in the same CAPRA-S group. Each outcome belongs to another patient, not this patient. These observations cannot estimate this patient's survival or recurrence date.
Another patient, T3-046: CAPRA-S 1.0; observed censored follow-up without recurrence at 52.4 months. Do not copy this outcome into the current note.
Another patient, T3-019: CAPRA-S 1.0; observed censored follow-up without recurrence at 37.9 months. Do not copy this outcome into the current note.
Another patient, T3-074: CAPRA-S 1.0; observed censored follow-up without recurrence at 62.3 months. Do not copy this outcome into the current note.

## Intervención 6 — EXPERT-GUIDELINE

*EXPERT-GUIDELINE* · vuelta 1

{"authority": "advisory; no vote or numeric horizon", "clinical_eau_group_from_G": "not recorded", "scope": "G is pre-treatment clinical stratification; not a postoperative EAU/NCCN classification.", "postoperative_findings": {"epe": 0.0, "margins": 0.0, "svi": 0.0, "lvi": 0.0, "ln_unknown": 0.0}, "follow_up": "Postoperative PSA and its trajectory are needed; pathology alone does not establish biochemical recurrence.", "reference": "EAU Prostate Cancer: Follow-up, https://uroweb.org/guidelines/prostate-cancer/chapter/followup", "retrieval": "deterministic inventory; no guideline passage was retrieved"}

## Intervención 7 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 8 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+4 (ISUP grade group 2), pathological stage pT2c. There was no extraprostatic extension; surgical margins were negative; the seminal vesicles were not invaded; lymphovascular invasion was absent; there was no lymph node metastasis.", "pathology_report": "The patient underwent one biopsy session. Gleason pattern and ISUP report missing.", "radiology_report": "Prostate volume: 29.71 cc. PSA density: 0.199 ng/mL/cc. PI-RADS: 5. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.84285355.", "previous_notes": null}

## Intervención 9 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": -0.06410884986784986, "mode": "deployed", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 10 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 1.0, "spokesperson": "nested-selected fusion", "rule": "Selection inside outer folds; DEV, VAL and full-cohort results recorded."}

## Intervención 11 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 58.42884390166326, "event": 0, "calibration": {"mode": "deployed", "a": 93.67296967731494, "b": 0.1, "spokesperson": "nested-selected fusion", "percentile": 0.64, "months_map": "90 exp(-0.1 * 12 * (1-percentile))", "event_policy": "unchanged CAPRA event policy", "validation": {"n": 75, "events": 19, "baseline_c_index": 0.7371681415929203, "candidate_c_index": 0.8234513274336284, "paired_ci95": [-0.004138922865375535, 0.20206167181978793], "eligible": true, "adopted": false, "limitations": "Small internal historical cohort; wide paired intervals; not external validation. Model selection is inside each outer fold."}}}, "uncertainty": {"interval_months": [43.821632926247446, 73.03605487707907], "base_half_width": 11.685768780332651, "imputation_half_width": 2.921442195083163, "ln_unknown": false, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 12 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": ["previous_notes"], "ln_unknown": false, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "Nodes were sampled; do not claim missing nodal sampling."}

## Intervención 13 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

Postoperative prognosis depends on the preoperative PSA and the prostatectomy findings. Extraprostatic extension is reported absent. Positive surgical margins is reported absent. Seminal vesicle invasion is reported absent. Lymphovascular invasion is reported absent. Postoperative PSA and its subsequent trajectory are needed to refine this prognosis; a future recurrence date cannot be established from surgical risk factors alone. The fixed estimated horizon is 58.43 months. This represents expected follow-up without an event, not a known recurrence date. The sensitivity range is 43.82–73.04 months; its coverage has not been validated.
