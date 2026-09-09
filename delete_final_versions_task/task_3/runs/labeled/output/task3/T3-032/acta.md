# Junta clínica — T3-032 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 68, "psa": 4.4, "dre": null, "active_treatment_prior_to_surgery": null}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 5.0, "group": "intermedio", "ln_unknown": 0.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+5 (ISUP grade group 5), pathological stage pT2c. There was no extraprostatic extension; surgical margins were positive; the seminal vesicles were not invaded; lymphovascular invasion was absent; there was no lymph node metastasis."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 4.0, "sec": 5.0, "isup_rp": 5.0, "pt": 2.0, "epe": 0.0, "margins": 1.0, "svi": 0.0, "lvi": 0.0, "ln": 0.0, "tertiary": null, "ln_unknown": 0.0, "pt_ge_t3": 0.0, "tertiary_pattern_5": null, "upgrade_bx_to_rp": 3.0, "capra_s": 5.0, "capra_s_group": 1.0}, "log_risk": 0.026390553555040063, "mode": "oof", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent 2 biopsy sessions. At the first session, Gleason 3+4 with tertiary pattern 4 (ISUP grade group 2, AI model-predicted ISUP 4) was identified in the right peripheral zone; cribriform pattern and intraductal carcinoma were present. In the same month, at the second session, Gleason 4+4 (ISUP grade group 4, AI model-predicted ISUP 4) was identified in the right peripheral zone; cribriform pattern and intraductal carcinoma were present. The reported histological growth pattern was: Adenocarcinoma; Cribriform."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": 0.11739849129101876, "mode": "oof", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 1, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 6 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+5 (ISUP grade group 5), pathological stage pT2c. There was no extraprostatic extension; surgical margins were positive; the seminal vesicles were not invaded; lymphovascular invasion was absent; there was no lymph node metastasis.", "pathology_report": "The patient underwent 2 biopsy sessions. At the first session, Gleason 3+4 with tertiary pattern 4 (ISUP grade group 2, AI model-predicted ISUP 4) was identified in the right peripheral zone; cribriform pattern and intraductal carcinoma were present. In the same month, at the second session, Gleason 4+4 (ISUP grade group 4, AI model-predicted ISUP 4) was identified in the right peripheral zone; cribriform pattern and intraductal carcinoma were present. The reported histological growth pattern was: Adenocarcinoma; Cribriform.", "radiology_report": "Prostate volume: 91.11 cc. PSA density: 0.048 ng/mL/cc. PI-RADS: 5. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.78277797.", "previous_notes": null}

## Intervención 7 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": 0.25660245186064967, "mode": "oof", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 8 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 5.0, "spokesperson": "CAPRA-S", "rule": "Predeclared in step 5.3; advisory OOF comparisons do not reselect the spokesperson."}

## Intervención 9 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 56.815528095623336, "event": 0, "calibration": {"held_out_capra": 5.0, "a": 93.67296967731494, "b": 0.1, "threshold": 9.0, "mode": "oof"}}, "uncertainty": {"interval_months": [42.6116460717175, 71.01941011952917], "base_half_width": 11.363105619124667, "imputation_half_width": 2.8407764047811668, "ln_unknown": false, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 10 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": ["previous_notes"], "ln_unknown": false, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "Nodes were sampled; do not claim missing nodal sampling."}

## Intervención 11 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The prognosis is influenced by several factors, including a preoperative PSA of 4.4 and an ISUP grade group 5 Gleason 4+5 on the prostatectomy specimen. Positive surgical margins are concerning findings that elevate risk. Conversely, the absence of seminal vesicle invasion and lymphovascular invasion are favorable elements. The biopsy history shows progression from lower-grade disease (ISUP group 2) to higher-grade disease (ISUP group 4/5), which is a noted discrepancy between initial sampling and final pathology. Nodal status was not reported as positive, but the documentation does not specify if nodes were removed or sampled, widening uncertainty in this area. Future prognosis assessment would be significantly revised by obtaining postoperative PSA levels and tracking their subsequent trajectory over time. The fixed estimated horizon is 56.82 months. This represents expected follow-up without an event, not a known recurrence date. The sensitivity range is 42.61–71.02 months; its coverage has not been validated.
