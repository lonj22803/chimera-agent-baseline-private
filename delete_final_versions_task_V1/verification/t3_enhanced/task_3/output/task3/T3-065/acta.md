# Junta clínica — T3-065 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 68, "psa": 11.7, "dre": "Digital rectal examination was abnormal bilaterally. The clinical T-stage derived from digital rectal examination was cT1c.", "active_treatment_prior_to_surgery": null}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 3.0, "group": "intermedio", "ln_unknown": 1.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+3 with tertiary pattern 4 (ISUP grade group 1), pathological stage pT3a. Extraprostatic extension was present; surgical margins were negative; the seminal vesicles were not invaded; lymphovascular invasion was absent; no lymph nodes were removed."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 3.0, "sec": 3.0, "isup_rp": 1.0, "pt": 3.0, "epe": 1.0, "margins": 0.0, "svi": 0.0, "lvi": 0.0, "ln": null, "tertiary": 4.0, "ln_unknown": 1.0, "pt_ge_t3": 1.0, "tertiary_pattern_5": 0.0, "upgrade_bx_to_rp": 0.0, "capra_s": 3.0, "capra_s_group": 1.0}, "log_risk": -0.8452355393815869, "mode": "deployed", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent 2 biopsy sessions. At the first session, Gleason 3+3 (ISUP grade group 1, AI model-predicted ISUP 3) was identified; cribriform pattern was present, with no intraductal carcinoma or perineural invasion. 42.9 months later, at the second session, Gleason 3+3 (ISUP grade group 1, AI model-predicted ISUP 3) was identified in the right peripheral zone (mid); perineural invasion was present, with no cribriform pattern. The reported histological growth pattern was: Organoid arranged glandular tubules; Tubules."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": -0.29793421822501825, "mode": "deployed", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 3, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — EXPERT-EXPERIENCE

*case library; the closest labelled precedents and what the reading urologist did with them* · vuelta 1

I recall these other postoperative patients in the same CAPRA-S group. Each outcome belongs to another patient, not this patient. These observations cannot estimate this patient's survival or recurrence date.
Another patient, T3-006: CAPRA-S 3.0; observed censored follow-up without recurrence at 5 months. Do not copy this outcome into the current note.
Another patient, T3-048: CAPRA-S 3.0; observed censored follow-up without recurrence at 42.3 months. Do not copy this outcome into the current note.
Another patient, T3-067: CAPRA-S 3.0; observed censored follow-up without recurrence at 34.7 months. Do not copy this outcome into the current note.

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

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+3 with tertiary pattern 4 (ISUP grade group 1), pathological stage pT3a. Extraprostatic extension was present; surgical margins were negative; the seminal vesicles were not invaded; lymphovascular invasion was absent; no lymph nodes were removed.", "pathology_report": "The patient underwent 2 biopsy sessions. At the first session, Gleason 3+3 (ISUP grade group 1, AI model-predicted ISUP 3) was identified; cribriform pattern was present, with no intraductal carcinoma or perineural invasion. 42.9 months later, at the second session, Gleason 3+3 (ISUP grade group 1, AI model-predicted ISUP 3) was identified in the right peripheral zone (mid); perineural invasion was present, with no cribriform pattern. The reported histological growth pattern was: Organoid arranged glandular tubules; Tubules.", "radiology_report": "Prostate volume: 41.58 cc. PSA density: 0.281 ng/mL/cc. PI-RADS: 4. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.6642831.", "previous_notes": "The patient is not on 5-ARI medication."}

## Intervención 9 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": -0.05524009730613777, "mode": "deployed", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 10 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 3.0, "spokesperson": "nested-selected fusion", "rule": "Selection inside outer folds; DEV, VAL and full-cohort results recorded."}

## Intervención 11 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 54.80654769656071, "event": 0, "calibration": {"mode": "deployed", "a": 93.67296967731494, "b": 0.1, "spokesperson": "nested-selected fusion", "percentile": 0.5866666666666667, "months_map": "90 exp(-0.1 * 12 * (1-percentile))", "event_policy": "unchanged CAPRA event policy", "validation": {"n": 75, "events": 19, "baseline_c_index": 0.7371681415929203, "candidate_c_index": 0.8234513274336284, "paired_ci95": [-0.004138922865375535, 0.20206167181978793], "eligible": true, "adopted": false, "limitations": "Small internal historical cohort; wide paired intervals; not external validation. Model selection is inside each outer fold."}}}, "uncertainty": {"interval_months": [35.62425600276446, 73.98883939035696], "base_half_width": 10.961309539312143, "imputation_half_width": 8.220982154484107, "ln_unknown": true, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 12 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": [], "ln_unknown": true, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "No nodes sampled; pNx is not pN0."}

## Intervención 13 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The postoperative pathology reveals a Gleason 3+3 with tertiary pattern 4 (ISUP grade group 1) and pathological stage pT3a. A reassuring finding is that surgical margins were negative, and the seminal vesicles were not invaded, as documented by the surgical pathology report: "surgical margins were negative; the seminal vesicles were not invaded." Conversely, the biopsy findings documented perineural invasion in the right peripheral zone, which is an adverse finding. Nodal status is documented as pNx, meaning no nodes were removed, which widens uncertainty regarding nodal involvement as pNx does not establish pN0. The absence of a recorded postoperative PSA means biochemical recurrence cannot be assessed. Information regarding postoperative PSA and its trajectory is crucial for revising the prognosis. The documented negative margins and non-invasion of seminal vesicles are reassuring factors against the finding of perineural invasion. Missing nodal sampling limits staging and contributes to uncertainty. The fixed estimated horizon is 54.81 months. This represents expected follow-up without an event, not a known recurrence date. The sensitivity range is 35.62–73.99 months; its coverage has not been validated.
