# Junta clínica — T3-056 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 57, "psa": 7.8, "dre": "Digital rectal examination was abnormal on the right. The clinical T-stage derived from digital rectal examination was cT2.", "active_treatment_prior_to_surgery": null}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 9.0, "group": "alto", "ln_unknown": 0.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+5 (ISUP grade group 5), pathological stage pT3b. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were invaded; lymphovascular invasion was present; there was no lymph node metastasis."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 4.0, "sec": 5.0, "isup_rp": 5.0, "pt": 3.0, "epe": 1.0, "margins": 1.0, "svi": 1.0, "lvi": 1.0, "ln": 0.0, "tertiary": null, "ln_unknown": 0.0, "pt_ge_t3": 1.0, "tertiary_pattern_5": null, "upgrade_bx_to_rp": 3.0, "capra_s": 9.0, "capra_s_group": 2.0}, "log_risk": 0.6447679375466652, "mode": "deployed", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent one biopsy session. At biopsy, Gleason 3+4 (ISUP grade group 2, AI model-predicted ISUP 5) was identified in the right base; cribriform pattern, intraductal carcinoma and perineural invasion were present. The reported histological growth pattern was: Acinar adenocarcinoma."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": 0.35927478146521247, "mode": "deployed", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 2, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 6 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+5 (ISUP grade group 5), pathological stage pT3b. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were invaded; lymphovascular invasion was present; there was no lymph node metastasis.", "pathology_report": "The patient underwent one biopsy session. At biopsy, Gleason 3+4 (ISUP grade group 2, AI model-predicted ISUP 5) was identified in the right base; cribriform pattern, intraductal carcinoma and perineural invasion were present. The reported histological growth pattern was: Acinar adenocarcinoma.", "radiology_report": "Prostate volume: 23.44 cc. PSA density: 0.333 ng/mL/cc. PI-RADS: 5. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.8538012.", "previous_notes": "The patient is not on 5-ARI medication. No relevant comorbidities recorded, with a Charlson Comorbidity Index (CCI) of 1."}

## Intervención 7 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": 0.25916632851180316, "mode": "deployed", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 8 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 9.0, "spokesperson": "nested-selected fusion", "rule": "Selection inside outer folds; DEV, VAL and full-cohort results recorded."}

## Intervención 9 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 29.838803290639163, "event": 1, "calibration": {"mode": "deployed", "a": 93.67296967731494, "b": 0.1, "spokesperson": "nested-selected fusion", "percentile": 0.08, "months_map": "90 exp(-0.1 * 12 * (1-percentile))", "event_policy": "unchanged CAPRA event policy", "validation": {"n": 75, "events": 19, "baseline_c_index": 0.7371681415929203, "candidate_c_index": 0.8234513274336284, "paired_ci95": [-0.004138922865375535, 0.20206167181978793], "eligible": true, "adopted": false, "limitations": "Small internal historical cohort; wide paired intervals; not external validation. Model selection is inside each outer fold."}}}, "uncertainty": {"interval_months": [23.87104263251133, 35.80656394876699], "base_half_width": 5.967760658127833, "imputation_half_width": 0.0, "ln_unknown": false, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 10 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": [], "ln_unknown": false, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "Nodes were sampled; do not claim missing nodal sampling."}

## Intervención 11 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The prognosis is influenced by several documented factors. Preoperative PSA was elevated at 7.8. The surgical findings included a high-risk profile: Gleason 4+5 (ISUP grade group 5), positive surgical margins, invasion of the seminal vesicles, and lymphovascular invasion, although no lymph node metastasis was noted. The biopsy revealed a Gleason 3+4 pattern, which differs from the prostatectomy specimen. The absence of lymph node metastasis is a favorable finding.

Countervailing factors include the positive surgical margins and the presence of seminal vesicle invasion. Missing postoperative PSA or follow-up data significantly widens the uncertainty regarding the trajectory of recurrence. The current horizon suggests a potential event within the calculated range. Information regarding postoperative PSA levels and subsequent changes would be crucial in refining this prognosis. The fixed estimated horizon is 29.84 months. This is a predicted recurrence horizon, not evidence of observed recurrence. The sensitivity range is 23.87–35.81 months; its coverage has not been validated.
