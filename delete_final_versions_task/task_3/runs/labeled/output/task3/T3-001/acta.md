# Junta clínica — T3-001 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 73, "psa": 86, "dre": "Digital rectal examination was abnormal on the right. The clinical T-stage derived from digital rectal examination was cT2.", "active_treatment_prior_to_surgery": null}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 11.0, "group": "alto", "ln_unknown": 0.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+3 (ISUP grade group 3), pathological stage pT4b. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were invaded; lymphovascular invasion was absent; lymph node metastasis was present."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 4.0, "sec": 3.0, "isup_rp": 3.0, "pt": 4.0, "epe": 1.0, "margins": 1.0, "svi": 1.0, "lvi": 0.0, "ln": 1.0, "tertiary": null, "ln_unknown": 0.0, "pt_ge_t3": 1.0, "tertiary_pattern_5": null, "upgrade_bx_to_rp": -1.0, "capra_s": 11.0, "capra_s_group": 2.0}, "log_risk": 1.1511014726149489, "mode": "oof", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent one biopsy session. At biopsy, Gleason 4+4 (ISUP grade group 4, AI model-predicted ISUP 5) was identified in the left base; cribriform pattern was present. The reported histological growth pattern was: Adenocarcinoma."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": -0.2292117554613422, "mode": "oof", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 3, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 6 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+3 (ISUP grade group 3), pathological stage pT4b. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were invaded; lymphovascular invasion was absent; lymph node metastasis was present.", "pathology_report": "The patient underwent one biopsy session. At biopsy, Gleason 4+4 (ISUP grade group 4, AI model-predicted ISUP 5) was identified in the left base; cribriform pattern was present. The reported histological growth pattern was: Adenocarcinoma.", "radiology_report": "Prostate volume: 37.29 cc. PSA density: 2.306 ng/mL/cc. PI-RADS: 5. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.9527162.", "previous_notes": "The patient is not on 5-ARI medication. No relevant comorbidities recorded, with a Charlson Comorbidity Index (CCI) of 3."}

## Intervención 7 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": 0.31098877512799905, "mode": "oof", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 8 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 11.0, "spokesperson": "CAPRA-S", "rule": "Predeclared in step 5.3; advisory OOF comparisons do not reselect the spokesperson."}

## Intervención 9 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 31.18102292970517, "event": 1, "calibration": {"held_out_capra": 11.0, "a": 93.67296967731494, "b": 0.1, "threshold": 9.0, "mode": "oof"}}, "uncertainty": {"interval_months": [24.944818343764133, 37.4172275156462], "base_half_width": 6.236204585941034, "imputation_half_width": 0.0, "ln_unknown": false, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 10 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": [], "ln_unknown": false, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "Nodes were sampled; do not claim missing nodal sampling."}

## Intervención 11 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The prognosis is driven by several significant factors, including a high preoperative PSA of 86 and positive surgical margins. Pathological findings are concerning due to the presence of extraprostatic extension and seminal vesicle invasion. The biopsy-to-prostatectomy comparison shows a discrepancy, with the biopsy identifying Gleason 4+4 while the prostatectomy specimen was Gleason 4+3 (ISUP grade group 3). Node metastasis was documented, which contributes to the elevated risk score.

Countervailing findings include the absence of lymphovascular invasion and that no seminal vesicle invasion details were provided beyond simple documentation of invasion. The current data lacks postoperative PSA measurements or follow-up information, which would be crucial for refining prognosis. Future trajectory assessment is highly dependent on subsequent PSA levels and their pattern over time. The fixed estimated horizon is 31.18 months. This is a predicted recurrence horizon, not evidence of observed recurrence. The sensitivity range is 24.94–37.42 months; its coverage has not been validated.
