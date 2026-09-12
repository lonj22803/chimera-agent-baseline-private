# Junta clínica — T3-017 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 62, "psa": 160, "dre": "Digital rectal examination was abnormal bilaterally. The clinical T-stage derived from digital rectal examination was cT3a.", "active_treatment_prior_to_surgery": null}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 8.0, "group": "alto", "ln_unknown": 0.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+3 with tertiary pattern 5 (ISUP grade group 3), pathological stage pT4. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were not invaded; lymphovascular invasion was present; there was no lymph node metastasis."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 4.0, "sec": 3.0, "isup_rp": 3.0, "pt": 4.0, "epe": 1.0, "margins": 1.0, "svi": 0.0, "lvi": 1.0, "ln": 0.0, "tertiary": 5.0, "ln_unknown": 0.0, "pt_ge_t3": 1.0, "tertiary_pattern_5": 1.0, "upgrade_bx_to_rp": 1.0, "capra_s": 8.0, "capra_s_group": 2.0}, "log_risk": 0.8583899672044835, "mode": "deployed", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent one biopsy session. At biopsy, Gleason 3+4 (ISUP grade group 2, AI model-predicted ISUP 5) was identified in the left transition zone (mid); no cribriform pattern was identified. The reported histological growth pattern was: Separate tubules and an excess of abortive tubules with some fusion."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": 2.0156792802639685, "mode": "deployed", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 3, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 6 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+3 with tertiary pattern 5 (ISUP grade group 3), pathological stage pT4. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were not invaded; lymphovascular invasion was present; there was no lymph node metastasis.", "pathology_report": "The patient underwent one biopsy session. At biopsy, Gleason 3+4 (ISUP grade group 2, AI model-predicted ISUP 5) was identified in the left transition zone (mid); no cribriform pattern was identified. The reported histological growth pattern was: Separate tubules and an excess of abortive tubules with some fusion.", "radiology_report": "Prostate volume: 60.71 cc. PSA density: 2.635 ng/mL/cc. PI-RADS: 5. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.95889634.", "previous_notes": "The patient is not on 5-ARI medication. Relevant comorbidities include Scrotal/inguinal surgery."}

## Intervención 7 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": 0.50770204940522, "mode": "deployed", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 8 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 8.0, "spokesperson": "nested-selected fusion", "rule": "Selection inside outer folds; DEV, VAL and full-cohort results recorded."}

## Intervención 9 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 27.145940620992334, "event": 0, "calibration": {"mode": "deployed", "a": 90.0, "b": 0.1, "spokesperson": "nested-selected fusion", "percentile": 0.0011815401239522183, "months_map": "90 exp(-0.1 * 12 * (1 - CDF_normal_train(raw)))", "event_policy": "unchanged CAPRA event policy", "validation": {"n": 75, "events": 19, "baseline_c_index": 0.7371681415929203, "candidate_c_index": 0.8234513274336284, "paired_ci95": [-0.004138922865375535, 0.20206167181978793], "eligible": true, "adopted": false, "limitations": "Small internal historical cohort; wide paired intervals; not external validation. Model selection is inside each outer fold."}, "risk_scale": 12.0, "exportador": "cdf_suave_v1", "sustituye": "percentil por CDF empírica de 75 valores", "meses_cdf_empirica": 27.988946666633524, "nota": "El orden del riesgo se conserva exactamente: la CDF normal es estrictamente creciente. a, b y risk_scale no se reajustan, así que el rango de salida es el de V1."}}, "uncertainty": {"interval_months": [21.716752496793866, 32.5751287451908], "base_half_width": 5.429188124198467, "imputation_half_width": 0.0, "ln_unknown": false, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 10 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": [], "ln_unknown": false, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "Nodes were sampled; do not claim missing nodal sampling."}

## Intervención 11 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The patient underwent a robot-assisted radical prostatectomy for clinically significant prostate cancer, with a preoperative PSA of 160. The surgical pathology revealed a Gleason 4+3 with tertiary pattern 5 (ISUP grade group 3) and pathological stage pT4, with extraprostatic extension and positive surgical margins. The seminal vesicles were not invaded, and lymphovascular invasion was present, but there was no lymph node metastasis documented. Biopsy findings showed a Gleason 3+4 (ISUP grade group 2).

Two primary factors drive the prognosis: the high pathological stage (pT4) and positive surgical margins. Countervailing findings include the absence of lymph node metastasis and the non-invasion of the seminal vesicles. The difference between the biopsy grade (Gleason 3+4) and the final resection grade (Gleason 4+3) is noted. Missing postoperative PSA or follow-up data currently widens the uncertainty regarding the subsequent trajectory. Information regarding postoperative PSA and its subsequent trajectory is crucial for refining the prognosis. The fixed estimated horizon is 27.15 months. This represents expected follow-up without an event, not a known recurrence date. The sensitivity range is 21.72–32.58 months; its coverage has not been validated.
