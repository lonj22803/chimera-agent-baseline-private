# Junta clínica — T3-062 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 69, "psa": 10, "dre": "Digital rectal examination was abnormal bilaterally. The clinical T-stage derived from digital rectal examination was cT1c.", "active_treatment_prior_to_surgery": null}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 9.0, "group": "alto", "ln_unknown": 0.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+3 with tertiary pattern 5 (ISUP grade group 3), pathological stage pT3b. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were invaded; lymphovascular invasion was absent; lymph node metastasis was present."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 4.0, "sec": 3.0, "isup_rp": 3.0, "pt": 3.0, "epe": 1.0, "margins": 1.0, "svi": 1.0, "lvi": 0.0, "ln": 1.0, "tertiary": 5.0, "ln_unknown": 0.0, "pt_ge_t3": 1.0, "tertiary_pattern_5": 1.0, "upgrade_bx_to_rp": 1.0, "capra_s": 9.0, "capra_s_group": 2.0}, "log_risk": 0.8061497049136634, "mode": "deployed", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent one biopsy session. At biopsy, Gleason 3+4 (ISUP grade group 2, AI model-predicted ISUP 4) was identified in the left base (base); cribriform pattern was present, with no intraductal carcinoma. The reported histological growth pattern was: Acinar adenocarcinoma."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": -0.4077089756545469, "mode": "deployed", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 1, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 6 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+3 with tertiary pattern 5 (ISUP grade group 3), pathological stage pT3b. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were invaded; lymphovascular invasion was absent; lymph node metastasis was present.", "pathology_report": "The patient underwent one biopsy session. At biopsy, Gleason 3+4 (ISUP grade group 2, AI model-predicted ISUP 4) was identified in the left base (base); cribriform pattern was present, with no intraductal carcinoma. The reported histological growth pattern was: Acinar adenocarcinoma.", "radiology_report": "Prostate volume: 28.64 cc. PSA density: 0.349 ng/mL/cc. PI-RADS: 5. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.83261764.", "previous_notes": null}

## Intervención 7 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": 0.05273700441008913, "mode": "deployed", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 8 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 9.0, "spokesperson": "nested-selected fusion", "rule": "Selection inside outer folds; DEV, VAL and full-cohort results recorded."}

## Intervención 9 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 42.56773542013936, "event": 1, "calibration": {"mode": "deployed", "a": 90.0, "b": 0.1, "spokesperson": "nested-selected fusion", "percentile": 0.37607242623395276, "months_map": "90 exp(-0.1 * 12 * (1 - CDF_normal_train(raw)))", "event_policy": "unchanged CAPRA event policy", "validation": {"n": 75, "events": 19, "baseline_c_index": 0.7371681415929203, "candidate_c_index": 0.8234513274336284, "paired_ci95": [-0.004138922865375535, 0.20206167181978793], "eligible": true, "adopted": false, "limitations": "Small internal historical cohort; wide paired intervals; not external validation. Model selection is inside each outer fold."}, "risk_scale": 12.0, "exportador": "cdf_suave_v1", "sustituye": "percentil por CDF empírica de 75 valores", "meses_cdf_empirica": 39.79772183519088, "nota": "El orden del riesgo se conserva exactamente: la CDF normal es estrictamente creciente. a, b y risk_scale no se reajustan, así que el rango de salida es el de V1."}}, "uncertainty": {"interval_months": [31.925801565104518, 53.20966927517419], "base_half_width": 8.513547084027872, "imputation_half_width": 2.128386771006968, "ln_unknown": false, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 10 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": ["previous_notes"], "ln_unknown": false, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "Nodes were sampled; do not claim missing nodal sampling."}

## Intervención 11 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The patient underwent a robot-assisted radical prostatectomy for clinically significant prostate cancer, presenting with a preoperative PSA of 10. The surgical pathology revealed a Gleason 4+3 with tertiary pattern 5 (ISUP grade group 3), pathological stage pT3b, positive surgical margins, invasion of the seminal vesicles, and lymph node metastasis. Biopsy findings showed Gleason 3+4. These factors—high preoperative PSA, high pathological grade, positive margins, seminal vesicle invasion, and documented lymph node metastasis—are significant drivers of prognosis. Countervailing findings include the absence of lymphovascular invasion and the absence of documented recurrence. Missing previous notes limit the assessment of prior treatment effects. The prognosis is guided by the risk assessment, which suggests a horizon for recurrence. Information that would revise this prognosis, particularly the postoperative PSA and its subsequent trajectory, would be crucial for further evaluation. The fixed estimated horizon is 42.57 months. This is a predicted recurrence horizon, not evidence of observed recurrence. The sensitivity range is 31.93–53.21 months; its coverage has not been validated.
