# Junta clínica — T3-047 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 66, "psa": 8.3, "dre": "Digital rectal examination findings: Size: volume 40 cc Symmetry: right side slightly more prominent Consistency: right side firm, left side firm and elastic, palpable nodule on the right peripheral base/mid region. The clinical T-stage derived from digital rectal examination was cT3b.", "active_treatment_prior_to_surgery": "no"}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 8.0, "group": "alto", "ln_unknown": 0.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+4 with tertiary pattern 5 (ISUP grade group 2), pathological stage pT3b. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were invaded; lymphovascular invasion was present; lymph node metastasis was present."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 3.0, "sec": 4.0, "isup_rp": 2.0, "pt": 3.0, "epe": 1.0, "margins": 1.0, "svi": 1.0, "lvi": 1.0, "ln": 1.0, "tertiary": 5.0, "ln_unknown": 0.0, "pt_ge_t3": 1.0, "tertiary_pattern_5": 1.0, "upgrade_bx_to_rp": -1.0, "capra_s": 8.0, "capra_s_group": 2.0}, "log_risk": 1.1389389809384682, "mode": "deployed", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent 2 biopsy sessions. At the first session, Gleason 4+3 (ISUP grade group 3, AI model-predicted ISUP 3) was identified in the left side; cribriform pattern and intraductal carcinoma were present. In the same month, at the second session, Gleason 3+5 (ISUP grade group 4, AI model-predicted ISUP 5) was identified in the right peripheral zone (mid-base); cribriform pattern and intraductal carcinoma were present. The reported histological growth pattern was: Adenocarcinoma; Cribriform and fused elements."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": -0.07271880607942824, "mode": "deployed", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 1, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — EXPERT-EXPERIENCE

*case library; the closest labelled precedents and what the reading urologist did with them* · vuelta 1

I recall these other postoperative patients in the same CAPRA-S group. Each outcome belongs to another patient, not this patient. These observations cannot estimate this patient's survival or recurrence date.
Another patient, T3-064: CAPRA-S 8.0; observed censored follow-up without recurrence at 38.4 months. Do not copy this outcome into the current note.
Another patient, T3-058: CAPRA-S 8.0; observed censored follow-up without recurrence at 35.2 months. Do not copy this outcome into the current note.
Another patient, T3-017: CAPRA-S 8.0; observed recurrence at 11.4 months. Do not copy this outcome into the current note.

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

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+4 with tertiary pattern 5 (ISUP grade group 2), pathological stage pT3b. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were invaded; lymphovascular invasion was present; lymph node metastasis was present.", "pathology_report": "The patient underwent 2 biopsy sessions. At the first session, Gleason 4+3 (ISUP grade group 3, AI model-predicted ISUP 3) was identified in the left side; cribriform pattern and intraductal carcinoma were present. In the same month, at the second session, Gleason 3+5 (ISUP grade group 4, AI model-predicted ISUP 5) was identified in the right peripheral zone (mid-base); cribriform pattern and intraductal carcinoma were present. The reported histological growth pattern was: Adenocarcinoma; Cribriform and fused elements.", "radiology_report": "Prostate volume: 38.54 cc. PSA density: 0.215 ng/mL/cc. PI-RADS: 5. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.86351734.", "previous_notes": "The patient is taking ciprofloxacine. Relevant comorbidities include polyneuropathy of both lower legs."}

## Intervención 9 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": 0.1861714780801664, "mode": "deployed", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 10 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 8.0, "spokesperson": "nested-selected fusion", "rule": "Selection inside outer folds; DEV, VAL and full-cohort results recorded."}

## Intervención 11 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 30.320063961808238, "event": 0, "calibration": {"mode": "deployed", "a": 93.67296967731494, "b": 0.1, "spokesperson": "nested-selected fusion", "percentile": 0.09333333333333334, "months_map": "90 exp(-0.1 * 12 * (1-percentile))", "event_policy": "unchanged CAPRA event policy", "validation": {"n": 75, "events": 19, "baseline_c_index": 0.7371681415929203, "candidate_c_index": 0.8234513274336284, "paired_ci95": [-0.004138922865375535, 0.20206167181978793], "eligible": true, "adopted": false, "limitations": "Small internal historical cohort; wide paired intervals; not external validation. Model selection is inside each outer fold."}}}, "uncertainty": {"interval_months": [24.25605116944659, 36.38407675416988], "base_half_width": 6.064012792361648, "imputation_half_width": 0.0, "ln_unknown": false, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 12 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": [], "ln_unknown": false, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "Nodes were sampled; do not claim missing nodal sampling."}

## Intervención 13 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The postoperative pathology reveals an adverse profile, including positive surgical margins, invasion of the seminal vesicles, lymphovascular invasion, and lymph node metastasis. The preoperative findings included a Gleason 3+4 with tertiary pattern 5 (ISUP grade group 2) and pathological stage pT3b. These findings are concerning. Countervailing factors are not documented in the provided reports. Nodal status is documented as positive for metastasis. The biopsy findings showed high-grade disease, with the second session identifying a Gleason 3+5 (ISUP grade group 4). The report states, "The robot-assisted radical prostatectomy specimen showed Gleason 3+4 with tertiary pattern 5 (ISUP grade group 2), pathological stage pT3b. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were invaded; lymphovascular invasion was present; lymph node metastasis was present." The presence of positive margins, seminal vesicle invasion, and nodal metastasis are significant adverse prognostic indicators. Postoperative PSA is not recorded, meaning biochemical recurrence cannot be assessed. Information regarding postoperative PSA and its trajectory is crucial for revising the prognosis. The fixed estimated horizon is 30.32 months. This represents expected follow-up without an event, not a known recurrence date. The sensitivity range is 24.26–36.38 months; its coverage has not been validated.
