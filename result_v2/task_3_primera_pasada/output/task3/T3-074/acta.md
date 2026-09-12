# Junta clínica — T3-074 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 65, "psa": 5.2, "dre": null, "active_treatment_prior_to_surgery": null}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 1.0, "group": "bajo", "ln_unknown": 1.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+4 (ISUP grade group 2), pathological stage pT2c. There was no extraprostatic extension; surgical margins were negative; the seminal vesicles were not invaded; lymphovascular invasion was absent; no lymph nodes were removed."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 3.0, "sec": 4.0, "isup_rp": 2.0, "pt": 2.0, "epe": 0.0, "margins": 0.0, "svi": 0.0, "lvi": 0.0, "ln": null, "tertiary": null, "ln_unknown": 1.0, "pt_ge_t3": 0.0, "tertiary_pattern_5": null, "upgrade_bx_to_rp": 0.0, "capra_s": 1.0, "capra_s_group": 0.0}, "log_risk": -0.5889627039307891, "mode": "deployed", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent 2 biopsy sessions. At the first session, Gleason 3+4 with tertiary pattern 4 (ISUP grade group 2, AI model-predicted ISUP 3) was identified in the left peripheral zone (mid); cribriform pattern was present, with no intraductal carcinoma. In the same month, at the second session, Gleason 3+3 (ISUP grade group 1, AI model-predicted ISUP 3) was identified in the left peripheral zone; cribriform pattern was present. The reported histological growth pattern was: Adenocarcinoma; Cribriform."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": -0.20634301176158365, "mode": "deployed", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 1, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 6 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+4 (ISUP grade group 2), pathological stage pT2c. There was no extraprostatic extension; surgical margins were negative; the seminal vesicles were not invaded; lymphovascular invasion was absent; no lymph nodes were removed.", "pathology_report": "The patient underwent 2 biopsy sessions. At the first session, Gleason 3+4 with tertiary pattern 4 (ISUP grade group 2, AI model-predicted ISUP 3) was identified in the left peripheral zone (mid); cribriform pattern was present, with no intraductal carcinoma. In the same month, at the second session, Gleason 3+3 (ISUP grade group 1, AI model-predicted ISUP 3) was identified in the left peripheral zone; cribriform pattern was present. The reported histological growth pattern was: Adenocarcinoma; Cribriform.", "radiology_report": "Prostate volume: 34.49 cc. PSA density: 0.151 ng/mL/cc. PI-RADS: 4. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.5618297.", "previous_notes": null}

## Intervención 7 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": -0.16684707616027136, "mode": "deployed", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 8 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 1.0, "spokesperson": "nested-selected fusion", "rule": "Selection inside outer folds; DEV, VAL and full-cohort results recorded."}

## Intervención 9 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 74.37929453435274, "event": 0, "calibration": {"mode": "deployed", "a": 93.67296967731494, "b": 0.1, "spokesperson": "nested-selected fusion", "percentile": 0.8411399445890839, "months_map": "90 exp(-0.1 * 12 * (1 - CDF_normal_train(raw)))", "event_policy": "unchanged CAPRA event policy", "validation": {"n": 75, "events": 19, "baseline_c_index": 0.7371681415929203, "candidate_c_index": 0.8234513274336284, "paired_ci95": [-0.004138922865375535, 0.20206167181978793], "eligible": true, "adopted": false, "limitations": "Small internal historical cohort; wide paired intervals; not external validation. Model selection is inside each outer fold."}, "exportador": "cdf_suave_v1", "sustituye": "percentil por CDF empírica de 75 valores", "meses_cdf_empirica": 74.27761816425141, "nota": "El orden del riesgo se conserva exactamente: la CDF normal es estrictamente creciente. a, b y risk_scale no se reajustan, así que el rango de salida es el de V1."}}, "uncertainty": {"interval_months": [44.62757672061164, 104.13101234809383], "base_half_width": 14.875858906870548, "imputation_half_width": 14.875858906870548, "ln_unknown": true, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 10 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": ["previous_notes"], "ln_unknown": true, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "No nodes sampled; pNx is not pN0."}

## Intervención 11 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The prognosis is influenced by several documented factors. The surgical findings are favorable, showing no extraprostatic extension, negative surgical margins, and no seminal vesicle invasion. The preoperative PSA was 5.2. The biopsy demonstrated Gleason 3+4 in the peripheral zone, with a different Gleason 3+3 finding on the second biopsy, which introduces some histological variability. The absence of lymph nodes removed means nodal status is unknown, which widens the uncertainty regarding potential recurrence.

Countervailing factors include the negative surgical margins and lack of seminal vesicle invasion. Information that would significantly revise this prognosis is the postoperative PSA and its subsequent trajectory. Missing postoperative PSA or follow-up data prevents a definitive assessment of the current status. The uncertainty surrounding nodal sampling, as no nodes were removed, also impacts the certainty of the outcome. The fixed estimated horizon is 74.38 months. This represents expected follow-up without an event, not a known recurrence date. The sensitivity range is 44.63–104.13 months; its coverage has not been validated.
