# Junta clínica — T3-070 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 73, "psa": 68, "dre": "Digital rectal examination was abnormal on the right. The clinical T-stage derived from digital rectal examination was cT3.", "active_treatment_prior_to_surgery": null}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 12.0, "group": "alto", "ln_unknown": 0.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+5 with tertiary pattern 3 (ISUP grade group 5), pathological stage pT3b. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were invaded; lymphovascular invasion was present; lymph node metastasis was present."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 4.0, "sec": 5.0, "isup_rp": 5.0, "pt": 3.0, "epe": 1.0, "margins": 1.0, "svi": 1.0, "lvi": 1.0, "ln": 1.0, "tertiary": 3.0, "ln_unknown": 0.0, "pt_ge_t3": 1.0, "tertiary_pattern_5": 0.0, "upgrade_bx_to_rp": 2.0, "capra_s": 12.0, "capra_s_group": 2.0}, "log_risk": 1.1690091648458008, "mode": "deployed", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent one biopsy session. At biopsy, Gleason 4+3 (ISUP grade group 3, AI model-predicted ISUP 5) was identified in the right side; perineural invasion was present, with no cribriform pattern or intraductal carcinoma. The reported histological growth pattern was: Acinar adenocarcinoma."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": 1.5226156276800171, "mode": "deployed", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 3, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 6 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+5 with tertiary pattern 3 (ISUP grade group 5), pathological stage pT3b. Extraprostatic extension was present; surgical margins were positive; the seminal vesicles were invaded; lymphovascular invasion was present; lymph node metastasis was present.", "pathology_report": "The patient underwent one biopsy session. At biopsy, Gleason 4+3 (ISUP grade group 3, AI model-predicted ISUP 5) was identified in the right side; perineural invasion was present, with no cribriform pattern or intraductal carcinoma. The reported histological growth pattern was: Acinar adenocarcinoma.", "radiology_report": "Prostate volume: 58.83 cc. PSA density: 1.156 ng/mL/cc. PI-RADS: 5. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.8985173.", "previous_notes": "The patient is not on 5-ARI medication. Relevant comorbidities include Inguinal hernial repair."}

## Intervención 7 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": 0.4917177965560228, "mode": "deployed", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 8 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 12.0, "spokesperson": "CAPRA-S", "rule": "Predeclared CAPRA-S; advisory comparisons do not reselect the spokesperson."}

## Intervención 9 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 28.21375627943447, "event": 1, "calibration": {"mode": "deployed", "a": 93.67296967731494, "b": 0.1}}, "uncertainty": {"interval_months": [22.571005023547578, 33.85650753532136], "base_half_width": 5.642751255886894, "imputation_half_width": 0.0, "ln_unknown": false, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 10 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": [], "ln_unknown": false, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "Nodes were sampled; do not claim missing nodal sampling."}

## Intervención 11 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

Postoperative prognosis depends on the preoperative PSA and the prostatectomy findings. Extraprostatic extension is documented. Positive surgical margins is documented. Seminal vesicle invasion is documented. Lymphovascular invasion is documented. Postoperative PSA and its subsequent trajectory are needed to refine this prognosis; a future recurrence date cannot be established from surgical risk factors alone. The fixed estimated horizon is 28.21 months. This is a predicted recurrence horizon, not evidence of observed recurrence. The sensitivity range is 22.57–33.86 months; its coverage has not been validated.
