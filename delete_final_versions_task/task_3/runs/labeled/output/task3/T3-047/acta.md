# Junta clínica — T3-047 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 66, "psa": 8.3, "dre": "Digital rectal examination findings: Size: volume 40 cc Symmetry: right side slightly more prominent Consistency: right side firm, left side firm and elastic, palpable nodule on the right peripheral base/mid region. The clinical T-stage derived from digital rectal examination was cT3b.", "active_treatment_prior_to_surgery": "no"}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 8.0, "group": "alto", "ln_unknown": 0.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+4 with tertiary pattern 5 (ISUP grade group 2), pathological stage pT3b. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were invaded; lymphovascular invasion was present; lymph node metastasis was present."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 3.0, "sec": 4.0, "isup_rp": 2.0, "pt": 3.0, "epe": 1.0, "margins": 1.0, "svi": 1.0, "lvi": 1.0, "ln": 1.0, "tertiary": 5.0, "ln_unknown": 0.0, "pt_ge_t3": 1.0, "tertiary_pattern_5": 1.0, "upgrade_bx_to_rp": -1.0, "capra_s": 8.0, "capra_s_group": 2.0}, "log_risk": 0.7522809554394552, "mode": "oof", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent 2 biopsy sessions. At the first session, Gleason 4+3 (ISUP grade group 3, AI model-predicted ISUP 3) was identified in the left side; cribriform pattern and intraductal carcinoma were present. In the same month, at the second session, Gleason 3+5 (ISUP grade group 4, AI model-predicted ISUP 5) was identified in the right peripheral zone (mid-base); cribriform pattern and intraductal carcinoma were present. The reported histological growth pattern was: Adenocarcinoma; Cribriform and fused elements."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": -0.19184082887276604, "mode": "oof", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 1, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 6 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+4 with tertiary pattern 5 (ISUP grade group 2), pathological stage pT3b. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were invaded; lymphovascular invasion was present; lymph node metastasis was present.", "pathology_report": "The patient underwent 2 biopsy sessions. At the first session, Gleason 4+3 (ISUP grade group 3, AI model-predicted ISUP 3) was identified in the left side; cribriform pattern and intraductal carcinoma were present. In the same month, at the second session, Gleason 3+5 (ISUP grade group 4, AI model-predicted ISUP 5) was identified in the right peripheral zone (mid-base); cribriform pattern and intraductal carcinoma were present. The reported histological growth pattern was: Adenocarcinoma; Cribriform and fused elements.", "radiology_report": "Prostate volume: 38.54 cc. PSA density: 0.215 ng/mL/cc. PI-RADS: 5. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.86351734.", "previous_notes": "The patient is taking ciprofloxacine. Relevant comorbidities include polyneuropathy of both lower legs."}

## Intervención 7 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": 0.48311059725898087, "mode": "oof", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 8 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 8.0, "spokesperson": "CAPRA-S", "rule": "Predeclared in step 5.3; advisory OOF comparisons do not reselect the spokesperson."}

## Intervención 9 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 42.089978430891826, "event": 1, "calibration": {"held_out_capra": 8.0, "a": 93.67296967731494, "b": 0.1, "threshold": 7.0, "mode": "oof"}}, "uncertainty": {"interval_months": [33.67198274471346, 50.50797411707019], "base_half_width": 8.417995686178365, "imputation_half_width": 0.0, "ln_unknown": false, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 10 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": [], "ln_unknown": false, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "Nodes were sampled; do not claim missing nodal sampling."}

## Intervención 11 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The prognosis is influenced by several factors, including a preoperative PSA of 8.3 and pathological findings demonstrating pT3b disease with positive surgical margins, seminal vesicle invasion, lymphovascular invasion, and documented lymph node metastasis. The biopsy results showed different Gleason patterns compared to the prostatectomy specimen (Gleason 4+3 vs. 3+4).

The presence of nodal metastasis is a significant prognostic factor. Missing postoperative PSA data prevents assessment of its trajectory, which would be crucial for refining risk stratification. Further information regarding subsequent PSA levels and clinical status would revise this prognosis. The current documentation provides sufficient detail on pathological findings to guide management planning. The fixed estimated horizon is 42.09 months. This is a predicted recurrence horizon, not evidence of observed recurrence. The sensitivity range is 33.67–50.51 months; its coverage has not been validated.
