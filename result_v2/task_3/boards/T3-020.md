# Junta clínica — T3-020 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 70, "psa": 19, "dre": "Digital rectal examination was abnormal on the right. The clinical T-stage derived from digital rectal examination was cT2.", "active_treatment_prior_to_surgery": null}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 6.0, "group": "alto", "ln_unknown": 1.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+4 (ISUP grade group 2), pathological stage pT3a. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were not invaded; lymphovascular invasion was absent; no lymph nodes were removed."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 3.0, "sec": 4.0, "isup_rp": 2.0, "pt": 3.0, "epe": 1.0, "margins": 1.0, "svi": 0.0, "lvi": 0.0, "ln": null, "tertiary": null, "ln_unknown": 1.0, "pt_ge_t3": 1.0, "tertiary_pattern_5": null, "upgrade_bx_to_rp": 1.0, "capra_s": 6.0, "capra_s_group": 2.0}, "log_risk": -0.24306514192712397, "mode": "deployed", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent 2 biopsy sessions. At the first session, Gleason 3+3 (ISUP grade group 1, AI model-predicted ISUP 2) was identified in the left peripheral zone (apex); no cribriform pattern, intraductal carcinoma or perineural invasion were identified. 21.8 months later, at the second session, Gleason 3+4 (ISUP grade group 2, AI model-predicted ISUP 2) was identified in the left peripheral zone (apex); no cribriform pattern, intraductal carcinoma or perineural invasion were identified. The reported histological growth pattern was: Acinar adenocarcinoma."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": -0.46667865050650614, "mode": "deployed", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 2, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 6 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+4 (ISUP grade group 2), pathological stage pT3a. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were not invaded; lymphovascular invasion was absent; no lymph nodes were removed.", "pathology_report": "The patient underwent 2 biopsy sessions. At the first session, Gleason 3+3 (ISUP grade group 1, AI model-predicted ISUP 2) was identified in the left peripheral zone (apex); no cribriform pattern, intraductal carcinoma or perineural invasion were identified. 21.8 months later, at the second session, Gleason 3+4 (ISUP grade group 2, AI model-predicted ISUP 2) was identified in the left peripheral zone (apex); no cribriform pattern, intraductal carcinoma or perineural invasion were identified. The reported histological growth pattern was: Acinar adenocarcinoma.", "radiology_report": "Prostate volume: 57.89 cc. PSA density: 0.328 ng/mL/cc. PI-RADS: 5. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.75379103.", "previous_notes": "The patient is not on 5-ARI medication. No relevant comorbidities recorded, with a Charlson Comorbidity Index (CCI) of 3."}

## Intervención 7 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": -0.09507328022907292, "mode": "deployed", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 8 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 6.0, "spokesperson": "nested-selected fusion", "rule": "Selection inside outer folds; DEV, VAL and full-cohort results recorded."}

## Intervención 9 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 63.964915253058635, "event": 0, "calibration": {"mode": "deployed", "a": 90.0, "b": 0.1, "spokesperson": "nested-selected fusion", "percentile": 0.7154375529519539, "months_map": "90 exp(-0.1 * 12 * (1 - CDF_normal_train(raw)))", "event_policy": "unchanged CAPRA event policy", "validation": {"n": 75, "events": 19, "baseline_c_index": 0.7371681415929203, "candidate_c_index": 0.8234513274336284, "paired_ci95": [-0.004138922865375535, 0.20206167181978793], "eligible": true, "adopted": false, "limitations": "Small internal historical cohort; wide paired intervals; not external validation. Model selection is inside each outer fold."}, "risk_scale": 12.0, "exportador": "cdf_suave_v1", "sustituye": "percentil por CDF empírica de 75 valores", "meses_cdf_empirica": 67.47854330151371, "nota": "El orden del riesgo se conserva exactamente: la CDF normal es estrictamente creciente. a, b y risk_scale no se reajustan, así que el rango de salida es el de V1."}}, "uncertainty": {"interval_months": [41.57719491448811, 86.35263559162917], "base_half_width": 12.792983050611728, "imputation_half_width": 9.594737287958795, "ln_unknown": true, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 10 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": [], "ln_unknown": true, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "No nodes sampled; pNx is not pN0."}

## Intervención 11 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The patient underwent a robot-assisted radical prostatectomy with a pathological stage of pT3a, positive surgical margins, and no invasion of the seminal vesicles. The Gleason score was 3+4 (ISUP grade group 2). The absence of lymph nodes removed is noted, and lymphovascular invasion was absent. Biopsy findings showed a progression from Gleason 3+3 to 3+4 over 21.8 months. Preoperative PSA was 19.

Two primary factors drive the prognosis: the positive surgical margins and the higher Gleason grade of 3+4. Countervailing findings include the absence of lymph nodes removed and the absence of lymphovascular invasion. The lack of documented postoperative PSA or follow-up significantly widens the uncertainty regarding the trajectory. Furthermore, the nodal status is uncertain as no nodes were removed, and "pNx is not pN0." Information regarding postoperative PSA and its subsequent trajectory is crucial for revising this prognosis. The fixed estimated horizon is 63.96 months. This represents expected follow-up without an event, not a known recurrence date. The sensitivity range is 41.58–86.35 months; its coverage has not been validated.
