# Junta clínica — T3-009 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 69, "psa": 8.7, "dre": "Digital rectal examination was abnormal bilaterally. The clinical T-stage derived from digital rectal examination was cT1c.", "active_treatment_prior_to_surgery": null}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 5.0, "group": "intermedio", "ln_unknown": 1.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+3 with tertiary pattern 5 (ISUP grade group 3), pathological stage pT2. There was no extraprostatic extension; surgical margins were positive; the seminal vesicles were not invaded; lymphovascular invasion was absent; no lymph nodes were removed."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 4.0, "sec": 3.0, "isup_rp": 3.0, "pt": 2.0, "epe": 0.0, "margins": 1.0, "svi": 0.0, "lvi": 0.0, "ln": null, "tertiary": 5.0, "ln_unknown": 1.0, "pt_ge_t3": 0.0, "tertiary_pattern_5": 1.0, "upgrade_bx_to_rp": 3.0, "capra_s": 5.0, "capra_s_group": 1.0}, "log_risk": -0.25411491109625495, "mode": "oof", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent 2 biopsy sessions. At the first session, Gleason 0+0 (ISUP grade group 0, AI model-predicted ISUP 4) was identified; no cribriform pattern, intraductal carcinoma or perineural invasion were identified. 85.6 months later, at the second session, Gleason 3+4 (ISUP grade group 2, AI model-predicted ISUP 3) was identified in the bilateral peripheral zone; perineural invasion was present, with no cribriform pattern or intraductal carcinoma. The reported histological growth pattern was: Acinar."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": -0.12804050553874252, "mode": "oof", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 1, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 6 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+3 with tertiary pattern 5 (ISUP grade group 3), pathological stage pT2. There was no extraprostatic extension; surgical margins were positive; the seminal vesicles were not invaded; lymphovascular invasion was absent; no lymph nodes were removed.", "pathology_report": "The patient underwent 2 biopsy sessions. At the first session, Gleason 0+0 (ISUP grade group 0, AI model-predicted ISUP 4) was identified; no cribriform pattern, intraductal carcinoma or perineural invasion were identified. 85.6 months later, at the second session, Gleason 3+4 (ISUP grade group 2, AI model-predicted ISUP 3) was identified in the bilateral peripheral zone; perineural invasion was present, with no cribriform pattern or intraductal carcinoma. The reported histological growth pattern was: Acinar.", "radiology_report": "Prostate volume: 35.27 cc. PSA density: 0.247 ng/mL/cc. PI-RADS: 4. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.82454866.", "previous_notes": "The patient is not on 5-ARI medication."}

## Intervención 7 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": -0.7642243528684693, "mode": "oof", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 8 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 5.0, "spokesperson": "CAPRA-S", "rule": "Predeclared in step 5.3; advisory OOF comparisons do not reselect the spokesperson."}

## Intervención 9 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 56.815528095623336, "event": 0, "calibration": {"held_out_capra": 5.0, "a": 93.67296967731494, "b": 0.1, "threshold": 9.0, "mode": "oof"}}, "uncertainty": {"interval_months": [36.93009326215517, 76.7009629290915], "base_half_width": 11.363105619124667, "imputation_half_width": 8.5223292143435, "ln_unknown": true, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 10 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": [], "ln_unknown": true, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "No nodes sampled; pNx is not pN0."}

## Intervención 11 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The prognosis is influenced by several factors, including a preoperative PSA of 8.7 and an ISUP grade group 3 Gleason pattern on prostatectomy. Countervailing findings include the absence of extraprostatic extension and no seminal vesicle invasion documented in the surgical pathology report. The positive surgical margins are concerning for local recurrence risk. Notably, there is no nodal status reported as nodes were not removed, which widens uncertainty regarding nodal involvement. Furthermore, the biopsy history shows a discrepancy, with the second biopsy identifying Gleason 3+4 compared to the prostatectomy grade of Gleason 4+3. The trajectory of postoperative PSA and subsequent follow-up data would significantly revise this prognosis. The fixed estimated horizon is 56.82 months. This represents expected follow-up without an event, not a known recurrence date. The sensitivity range is 36.93–76.70 months; its coverage has not been validated.
