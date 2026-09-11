# Junta clínica — T3-071 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 57, "psa": 190, "dre": null, "active_treatment_prior_to_surgery": null}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 10.0, "group": "alto", "ln_unknown": 0.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+4 with tertiary pattern 5 (ISUP grade group 2), pathological stage pT3b. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were invaded; lymphovascular invasion was present; lymph node metastasis was present."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 3.0, "sec": 4.0, "isup_rp": 2.0, "pt": 3.0, "epe": 1.0, "margins": 1.0, "svi": 1.0, "lvi": 1.0, "ln": 1.0, "tertiary": 5.0, "ln_unknown": 0.0, "pt_ge_t3": 1.0, "tertiary_pattern_5": 1.0, "upgrade_bx_to_rp": -1.0, "capra_s": 10.0, "capra_s_group": 2.0}, "log_risk": 1.4461755466787936, "mode": "deployed", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent one biopsy session. At biopsy, Gleason 4+3 (ISUP grade group 3, AI model-predicted ISUP 4) was identified in the left peripheral zone (apical); cribriform pattern and perineural invasion were present. The reported histological growth pattern was: Adenocarcinoma with mostly moderately to poorly formed tubules that often fuse and regularly form cribriform areas. Also, quite a few well-formed tubules."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": 2.7004770928394866, "mode": "deployed", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 1, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — EXPERT-EXPERIENCE

*case library; the closest labelled precedents and what the reading urologist did with them* · vuelta 1

I recall these other postoperative patients in the same CAPRA-S group. Each outcome belongs to another patient, not this patient. These observations cannot estimate this patient's survival or recurrence date.
Another patient, T3-056: CAPRA-S 9.0; observed censored follow-up without recurrence at 43.1 months. Do not copy this outcome into the current note.
Another patient, T3-017: CAPRA-S 8.0; observed recurrence at 11.4 months. Do not copy this outcome into the current note.
Another patient, T3-058: CAPRA-S 8.0; observed censored follow-up without recurrence at 35.2 months. Do not copy this outcome into the current note.

## Intervención 6 — EXPERT-GUIDELINE

*EXPERT-GUIDELINE* · vuelta 1

{"authority": "advisory; no vote or numeric horizon", "clinical_eau_group_from_G": "not recorded", "scope": "G is pre-treatment clinical stratification; not a postoperative EAU/NCCN classification.", "postoperative_findings": {"epe": 1.0, "margins": 1.0, "svi": 1.0, "lvi": 1.0, "ln_unknown": 0.0}, "follow_up": "Postoperative PSA and its trajectory are needed; pathology alone does not establish biochemical recurrence.", "reference": "EAU Prostate Cancer: Follow-up, https://uroweb.org/guidelines/prostate-cancer/chapter/followup", "retrieval": "deterministic inventory; no guideline passage was retrieved"}

## Intervención 7 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 8 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+4 with tertiary pattern 5 (ISUP grade group 2), pathological stage pT3b. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were invaded; lymphovascular invasion was present; lymph node metastasis was present.", "pathology_report": "The patient underwent one biopsy session. At biopsy, Gleason 4+3 (ISUP grade group 3, AI model-predicted ISUP 4) was identified in the left peripheral zone (apical); cribriform pattern and perineural invasion were present. The reported histological growth pattern was: Adenocarcinoma with mostly moderately to poorly formed tubules that often fuse and regularly form cribriform areas. Also, quite a few well-formed tubules.", "radiology_report": "Prostate volume: 46.38 cc. PSA density: 4.097 ng/mL/cc. PI-RADS: 5. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.9718793.", "previous_notes": null}

## Intervención 9 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": 0.5521184919144757, "mode": "deployed", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 10 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 10.0, "spokesperson": "nested-selected fusion", "rule": "Selection inside outer folds; DEV, VAL and full-cohort results recorded."}

## Intervención 11 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 27.32520866181058, "event": 1, "calibration": {"mode": "deployed", "a": 93.67296967731494, "b": 0.1, "spokesperson": "nested-selected fusion", "percentile": 0.006666666666666667, "months_map": "90 exp(-0.1 * 12 * (1-percentile))", "event_policy": "unchanged CAPRA event policy", "validation": {"n": 75, "events": 19, "baseline_c_index": 0.7371681415929203, "candidate_c_index": 0.8234513274336284, "paired_ci95": [-0.004138922865375535, 0.20206167181978793], "eligible": true, "adopted": false, "limitations": "Small internal historical cohort; wide paired intervals; not external validation. Model selection is inside each outer fold."}}}, "uncertainty": {"interval_months": [20.493906496357937, 34.156510827263226], "base_half_width": 5.465041732362117, "imputation_half_width": 1.3662604330905292, "ln_unknown": false, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 12 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": ["previous_notes"], "ln_unknown": false, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "Nodes were sampled; do not claim missing nodal sampling."}

## Intervención 13 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The postoperative pathology reveals a Gleason 3+4 with tertiary pattern 5 (ISUP grade group 2) and pathological stage pT3b. Adverse findings include positive surgical margins, invasion of the seminal vesicles, lymphovascular invasion, and lymph node metastasis. The biopsy findings showed Gleason 4+3 (ISUP grade group 3) with cribriform pattern and perineural invasion. Countervailing findings are not documented. The nodal status is documented as lymph node metastasis was present. Missing postoperative PSA prevents assessment of biochemical recurrence. The documented pathology indicates a high-risk disease profile. Information regarding postoperative PSA and its trajectory is crucial for revising the prognosis. The current findings suggest a high risk, and the trajectory of postoperative PSA will be a key factor in determining subsequent management. The fixed estimated horizon is 27.33 months. This is a predicted recurrence horizon, not evidence of observed recurrence. The sensitivity range is 20.49–34.16 months; its coverage has not been validated.
