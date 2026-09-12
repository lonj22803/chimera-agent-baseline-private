# Junta clínica — T3-002 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 54, "psa": 0.2, "dre": null, "active_treatment_prior_to_surgery": null}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 2.0, "group": "bajo", "ln_unknown": 1.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+3 with tertiary pattern 4 (ISUP grade group 1), pathological stage pT2c. There was no extraprostatic extension; surgical margins were positive; the seminal vesicles were not invaded; lymphovascular invasion was absent; no lymph nodes were removed."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 3.0, "sec": 3.0, "isup_rp": 1.0, "pt": 2.0, "epe": 0.0, "margins": 1.0, "svi": 0.0, "lvi": 0.0, "ln": null, "tertiary": 4.0, "ln_unknown": 1.0, "pt_ge_t3": 0.0, "tertiary_pattern_5": 0.0, "upgrade_bx_to_rp": null, "capra_s": 2.0, "capra_s_group": 0.0}, "log_risk": -0.6424310413937993, "mode": "deployed", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent one biopsy session. Gleason pattern and ISUP report missing."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": -0.17353872765590667, "mode": "deployed", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 3, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 6 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+3 with tertiary pattern 4 (ISUP grade group 1), pathological stage pT2c. There was no extraprostatic extension; surgical margins were positive; the seminal vesicles were not invaded; lymphovascular invasion was absent; no lymph nodes were removed.", "pathology_report": "The patient underwent one biopsy session. Gleason pattern and ISUP report missing.", "radiology_report": "Prostate volume: 25.27 cc. PSA density: 0.008 ng/mL/cc. PI-RADS: 4. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.64653254.", "previous_notes": null}

## Intervención 7 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": -0.10914068888654395, "mode": "deployed", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 8 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 2.0, "spokesperson": "nested-selected fusion", "rule": "Selection inside outer folds; DEV, VAL and full-cohort results recorded."}

## Intervención 9 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 66.1404976112111, "event": 0, "calibration": {"mode": "deployed", "a": 90.0, "b": 0.1, "spokesperson": "nested-selected fusion", "percentile": 0.7433096339997689, "months_map": "90 exp(-0.1 * 12 * (1 - CDF_normal_train(raw)))", "event_policy": "unchanged CAPRA event policy", "validation": {"n": 75, "events": 19, "baseline_c_index": 0.7371681415929203, "candidate_c_index": 0.8234513274336284, "paired_ci95": [-0.004138922865375535, 0.20206167181978793], "eligible": true, "adopted": false, "limitations": "Small internal historical cohort; wide paired intervals; not external validation. Model selection is inside each outer fold."}, "risk_scale": 12.0, "exportador": "cdf_suave_v1", "sustituye": "percentil por CDF empírica de 75 valores", "meses_cdf_empirica": 70.79650749598981, "nota": "El orden del riesgo se conserva exactamente: la CDF normal es estrictamente creciente. a, b y risk_scale no se reajustan, así que el rango de salida es el de V1."}}, "uncertainty": {"interval_months": [39.68429856672666, 92.59669665569555], "base_half_width": 13.228099522242221, "imputation_half_width": 13.228099522242221, "ln_unknown": true, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 10 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": ["previous_notes"], "ln_unknown": true, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "No nodes sampled; pNx is not pN0."}

## Intervención 11 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The prognosis is influenced by several documented factors. The surgical findings included a Gleason 3+3 with tertiary pattern 4 (ISUP grade group 1), no extraprostatic extension, positive surgical margins, and no seminal vesicle invasion. The absence of lymph nodes removed and the lack of lymphovascular invasion are favorable findings. However, the positive surgical margins represent a potential risk factor.

The biopsy-to-prostatectomy difference is noted as the Gleason pattern and ISUP report are missing from the biopsy source, which widens uncertainty regarding the true tumor biology. Missing nodal sampling further increases this uncertainty, as pNx is not equivalent to pN0.

The numeric horizon suggests a follow-up period of approximately 66 months without an event. Information that would revise this prognosis significantly includes the postoperative PSA and its subsequent trajectory. A documented postoperative PSA level and its trend would be crucial in assessing the risk of recurrence. The fixed estimated horizon is 66.14 months. This represents expected follow-up without an event, not a known recurrence date. The sensitivity range is 39.68–92.60 months; its coverage has not been validated.
