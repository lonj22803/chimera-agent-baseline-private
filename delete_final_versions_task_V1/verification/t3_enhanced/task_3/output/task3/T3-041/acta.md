# Junta clínica — T3-041 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 51, "psa": 8.4, "dre": "Digital rectal examination was abnormal. The clinical T-stage derived from digital rectal examination was cT1c.", "active_treatment_prior_to_surgery": null}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 2.0, "group": "bajo", "ln_unknown": 1.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+4 (ISUP grade group 2), pathological stage pT2. There was no extraprostatic extension; surgical margins were negative; the seminal vesicles were not invaded; lymphovascular invasion was absent; no lymph nodes were removed."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 3.0, "sec": 4.0, "isup_rp": 2.0, "pt": 2.0, "epe": 0.0, "margins": 0.0, "svi": 0.0, "lvi": 0.0, "ln": null, "tertiary": null, "ln_unknown": 1.0, "pt_ge_t3": 0.0, "tertiary_pattern_5": null, "upgrade_bx_to_rp": 2.0, "capra_s": 2.0, "capra_s_group": 0.0}, "log_risk": -0.8601926724176091, "mode": "deployed", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent 2 biopsy sessions. At the first session, Gleason 0+0 (ISUP grade group 0, AI model-predicted ISUP 1) was identified; no cribriform pattern, intraductal carcinoma or perineural invasion were identified. 4.4 months later, at the second session, Gleason 3+4 (ISUP grade group 2, AI model-predicted ISUP 3) was identified in the left peripheral zone (mid); no cribriform pattern, intraductal carcinoma or perineural invasion were identified. The reported histological growth pattern was: Acinar adenocarcinoma."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": -0.6142780589151926, "mode": "deployed", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 2, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — EXPERT-EXPERIENCE

*case library; the closest labelled precedents and what the reading urologist did with them* · vuelta 1

I recall these other postoperative patients in the same CAPRA-S group. Each outcome belongs to another patient, not this patient. These observations cannot estimate this patient's survival or recurrence date.
Another patient, T3-003: CAPRA-S 2.0; observed censored follow-up without recurrence at 31.4 months. Do not copy this outcome into the current note.
Another patient, T3-012: CAPRA-S 2.0; observed censored follow-up without recurrence at 36.3 months. Do not copy this outcome into the current note.
Another patient, T3-046: CAPRA-S 1.0; observed censored follow-up without recurrence at 52.4 months. Do not copy this outcome into the current note.

## Intervención 6 — EXPERT-GUIDELINE

*EXPERT-GUIDELINE* · vuelta 1

{"authority": "advisory; no vote or numeric horizon", "clinical_eau_group_from_G": "not recorded", "scope": "G is pre-treatment clinical stratification; not a postoperative EAU/NCCN classification.", "postoperative_findings": {"epe": 0.0, "margins": 0.0, "svi": 0.0, "lvi": 0.0, "ln_unknown": 1.0}, "follow_up": "Postoperative PSA and its trajectory are needed; pathology alone does not establish biochemical recurrence.", "reference": "EAU Prostate Cancer: Follow-up, https://uroweb.org/guidelines/prostate-cancer/chapter/followup", "retrieval": "deterministic inventory; no guideline passage was retrieved"}

## Intervención 7 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 8 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+4 (ISUP grade group 2), pathological stage pT2. There was no extraprostatic extension; surgical margins were negative; the seminal vesicles were not invaded; lymphovascular invasion was absent; no lymph nodes were removed.", "pathology_report": "The patient underwent 2 biopsy sessions. At the first session, Gleason 0+0 (ISUP grade group 0, AI model-predicted ISUP 1) was identified; no cribriform pattern, intraductal carcinoma or perineural invasion were identified. 4.4 months later, at the second session, Gleason 3+4 (ISUP grade group 2, AI model-predicted ISUP 3) was identified in the left peripheral zone (mid); no cribriform pattern, intraductal carcinoma or perineural invasion were identified. The reported histological growth pattern was: Acinar adenocarcinoma.", "radiology_report": "Prostate volume: 45.02 cc. PSA density: 0.187 ng/mL/cc. PI-RADS: 4. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.7531718.", "previous_notes": "The patient is not on 5-ARI medication. Relevant comorbidities include Lower abdominal surgery, with a Charlson Comorbidity Index (CCI) of 1."}

## Intervención 9 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": -0.33609083862995287, "mode": "deployed", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 10 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 2.0, "spokesperson": "nested-selected fusion", "rule": "Selection inside outer folds; DEV, VAL and full-cohort results recorded."}

## Intervención 11 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 88.57145880497566, "event": 0, "calibration": {"mode": "deployed", "a": 93.67296967731494, "b": 0.1, "spokesperson": "nested-selected fusion", "percentile": 0.9866666666666667, "months_map": "90 exp(-0.1 * 12 * (1-percentile))", "event_policy": "unchanged CAPRA event policy", "validation": {"n": 75, "events": 19, "baseline_c_index": 0.7371681415929203, "candidate_c_index": 0.8234513274336284, "paired_ci95": [-0.004138922865375535, 0.20206167181978793], "eligible": true, "adopted": false, "limitations": "Small internal historical cohort; wide paired intervals; not external validation. Model selection is inside each outer fold."}}}, "uncertainty": {"interval_months": [57.57144822323418, 119.57146938671715], "base_half_width": 17.714291760995135, "imputation_half_width": 13.285718820746348, "ln_unknown": true, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 12 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": [], "ln_unknown": true, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "No nodes sampled; pNx is not pN0."}

## Intervención 13 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The postoperative pathology is reassuring, showing a Gleason 3+4 (ISUP grade group 2) with no extraprostatic extension and negative surgical margins. The seminal vesicles were not invaded, and lymphovascular invasion was absent. A countervailing finding is the lack of nodal sampling, as the status is documented as pNx, which does not establish node-negative disease. Biopsy findings included a Gleason 0+0 and a subsequent Gleason 3+4 in the left peripheral zone. Postoperative PSA is not recorded, meaning biochemical recurrence cannot be assessed. Missing nodal sampling widens the uncertainty regarding the true extent of disease. Information regarding postoperative PSA and its subsequent trajectory is crucial for revising the prognosis. The fixed estimated horizon is 88.57 months. This represents expected follow-up without an event, not a known recurrence date. The sensitivity range is 57.57–119.57 months; its coverage has not been validated.
