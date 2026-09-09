# Junta clínica — T3-059 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 60, "psa": 10, "dre": null, "active_treatment_prior_to_surgery": null}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 3.0, "group": "intermedio", "ln_unknown": 1.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+2 with tertiary pattern 4 (ISUP grade group 1), pathological stage pT3a. There was no extraprostatic extension; surgical margins were positive; the seminal vesicles were not invaded; lymphovascular invasion was present; no lymph nodes were removed."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 3.0, "sec": 2.0, "isup_rp": 1.0, "pt": 3.0, "epe": 0.0, "margins": 1.0, "svi": 0.0, "lvi": 1.0, "ln": null, "tertiary": 4.0, "ln_unknown": 1.0, "pt_ge_t3": 1.0, "tertiary_pattern_5": 0.0, "upgrade_bx_to_rp": -1.0, "capra_s": 3.0, "capra_s_group": 1.0}, "log_risk": -0.058762992118432465, "mode": "oof", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent one biopsy session. At biopsy, Gleason 3+4 (ISUP grade group 2, AI model-predicted ISUP 2) was identified in the right peripheral zone (apex); no cribriform pattern, intraductal carcinoma or perineural invasion were identified. The reported histological growth pattern was: Adenocarcinoma."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": 0.137980397193882, "mode": "oof", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 1, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 6 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+2 with tertiary pattern 4 (ISUP grade group 1), pathological stage pT3a. There was no extraprostatic extension; surgical margins were positive; the seminal vesicles were not invaded; lymphovascular invasion was present; no lymph nodes were removed.", "pathology_report": "The patient underwent one biopsy session. At biopsy, Gleason 3+4 (ISUP grade group 2, AI model-predicted ISUP 2) was identified in the right peripheral zone (apex); no cribriform pattern, intraductal carcinoma or perineural invasion were identified. The reported histological growth pattern was: Adenocarcinoma.", "radiology_report": "Prostate volume: 26.91 cc. PSA density: 0.372 ng/mL/cc. PI-RADS: 5. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.8577571.", "previous_notes": null}

## Intervención 7 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": 0.136885444286665, "mode": "oof", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 8 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 3.0, "spokesperson": "CAPRA-S", "rule": "Predeclared in step 5.3; advisory OOF comparisons do not reselect the spokesperson."}

## Intervención 9 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 69.39464272232097, "event": 0, "calibration": {"held_out_capra": 3.0, "a": 93.67296967731494, "b": 0.1, "threshold": 9.0, "mode": "oof"}}, "uncertainty": {"interval_months": [41.63678563339258, 97.15249981124936], "base_half_width": 13.878928544464195, "imputation_half_width": 13.878928544464195, "ln_unknown": true, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 10 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": ["previous_notes"], "ln_unknown": true, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "No nodes sampled; pNx is not pN0."}

## Intervención 11 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The prognosis is influenced by several factors, including a preoperative PSA of 10 and positive surgical margins. The pathological findings show Gleason 3+2 with tertiary pattern 4 (ISUP grade group 1) and the presence of lymphovascular invasion. A significant countervailing finding is that no lymph nodes were removed, meaning nodal status is unknown, which widens uncertainty regarding risk stratification. Furthermore, there is a discrepancy between biopsy and prostatectomy findings; the biopsy showed Gleason 3+4 (ISUP grade group 2), while the prostatectomy specimen was lower grade. The absence of seminal vesicle invasion is favorable. Prognostic assessment would be significantly revised by postoperative PSA levels and their subsequent trajectory over time. The fixed estimated horizon is 69.39 months. This represents expected follow-up without an event, not a known recurrence date. The sensitivity range is 41.64–97.15 months; its coverage has not been validated.
