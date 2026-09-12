# Junta clínica — T3-033 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 60, "psa": 16.8, "dre": null, "active_treatment_prior_to_surgery": "radiotherapy + cryotherapy"}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 10.0, "group": "alto", "ln_unknown": 0.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+5 (ISUP grade group 5), pathological stage pT4. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were invaded; lymphovascular invasion was present; there was no lymph node metastasis."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 4.0, "sec": 5.0, "isup_rp": 5.0, "pt": 4.0, "epe": 1.0, "margins": 1.0, "svi": 1.0, "lvi": 1.0, "ln": 0.0, "tertiary": null, "ln_unknown": 0.0, "pt_ge_t3": 1.0, "tertiary_pattern_5": null, "upgrade_bx_to_rp": null, "capra_s": 10.0, "capra_s_group": 2.0}, "log_risk": 0.8433489461177106, "mode": "deployed", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent one biopsy session. Gleason pattern and ISUP report missing."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": 0.7587270957000299, "mode": "deployed", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 3, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 6 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+5 (ISUP grade group 5), pathological stage pT4. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were invaded; lymphovascular invasion was present; there was no lymph node metastasis.", "pathology_report": "The patient underwent one biopsy session. Gleason pattern and ISUP report missing.", "radiology_report": "Prostate volume: 19.86 cc. PSA density: 0.846 ng/mL/cc. PI-RADS: 5. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.87284654.", "previous_notes": null}

## Intervención 7 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": 0.32253442732122367, "mode": "deployed", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 8 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 10.0, "spokesperson": "nested-selected fusion", "rule": "Selection inside outer folds; DEV, VAL and full-cohort results recorded."}

## Intervención 9 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 27.99046756496791, "event": 1, "calibration": {"mode": "deployed", "a": 90.0, "b": 0.1, "spokesperson": "nested-selected fusion", "percentile": 0.02671194814366562, "months_map": "90 exp(-0.1 * 12 * (1 - CDF_normal_train(raw)))", "event_policy": "unchanged CAPRA event policy", "validation": {"n": 75, "events": 19, "baseline_c_index": 0.7371681415929203, "candidate_c_index": 0.8234513274336284, "paired_ci95": [-0.004138922865375535, 0.20206167181978793], "eligible": true, "adopted": false, "limitations": "Small internal historical cohort; wide paired intervals; not external validation. Model selection is inside each outer fold."}, "risk_scale": 12.0, "exportador": "cdf_suave_v1", "sustituye": "percentil por CDF empírica de 75 valores", "meses_cdf_empirica": 28.899077388350456, "nota": "El orden del riesgo se conserva exactamente: la CDF normal es estrictamente creciente. a, b y risk_scale no se reajustan, así que el rango de salida es el de V1."}}, "uncertainty": {"interval_months": [20.992850673725933, 34.98808445620989], "base_half_width": 5.598093512993582, "imputation_half_width": 1.3995233782483956, "ln_unknown": false, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 10 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": ["previous_notes"], "ln_unknown": false, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "Nodes were sampled; do not claim missing nodal sampling."}

## Intervención 11 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The prognosis is complicated by several documented factors. The surgical pathology report indicates a high-risk profile with a Gleason 4+5 (ISUP grade group 5), positive surgical margins, and seminal vesicle invasion, which are adverse findings. Counterbalancing this is the absence of lymph node metastasis. The preoperative PSA was significantly elevated at 16.8. The biopsy-to-prostatectomy difference is noted as missing, which widens uncertainty regarding the true extent of the disease.

The primary driver for prognosis is the high pathological grade and positive margins. The absence of lymph node metastasis is a favorable finding. Missing information, specifically postoperative PSA and its subsequent trajectory, significantly limits the ability to refine this assessment. Postoperative PSA levels and their trend are crucial for monitoring disease control. The uncertainty in the prognosis is heightened by the missing biopsy grade and ISUP report. The fixed estimated horizon is 27.99 months. This is a predicted recurrence horizon, not evidence of observed recurrence. The sensitivity range is 20.99–34.99 months; its coverage has not been validated.
