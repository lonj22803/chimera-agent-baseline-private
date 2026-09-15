# Junta clínica — T3-010 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 72, "psa": 12, "dre": "Digital rectal examination was normal. The clinical T-stage derived from digital rectal examination was cT1c.", "active_treatment_prior_to_surgery": null}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 6.0, "group": "alto", "ln_unknown": 0.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+5 with tertiary pattern 3 (ISUP grade group 5), pathological stage pT3a. Extraprostatic extension was present; surgical margins were negative; the seminal vesicles were not invaded; lymphovascular invasion was absent; there was no lymph node metastasis."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 4.0, "sec": 5.0, "isup_rp": 5.0, "pt": 3.0, "epe": 1.0, "margins": 0.0, "svi": 0.0, "lvi": 0.0, "ln": 0.0, "tertiary": 3.0, "ln_unknown": 0.0, "pt_ge_t3": 1.0, "tertiary_pattern_5": 0.0, "upgrade_bx_to_rp": 5.0, "capra_s": 6.0, "capra_s_group": 2.0}, "log_risk": -0.5357315538488331, "mode": "deployed", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent one biopsy session. At biopsy, Gleason 0+0 (ISUP grade group 0, AI model-predicted ISUP 5) was identified; no cribriform pattern, intraductal carcinoma or perineural invasion were identified."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": -0.577878018770356, "mode": "deployed", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 2, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 6 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+5 with tertiary pattern 3 (ISUP grade group 5), pathological stage pT3a. Extraprostatic extension was present; surgical margins were negative; the seminal vesicles were not invaded; lymphovascular invasion was absent; there was no lymph node metastasis.", "pathology_report": "The patient underwent one biopsy session. At biopsy, Gleason 0+0 (ISUP grade group 0, AI model-predicted ISUP 5) was identified; no cribriform pattern, intraductal carcinoma or perineural invasion were identified.", "radiology_report": "Prostate volume: 38.29 cc. PSA density: 0.313 ng/mL/cc. PI-RADS: 4. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.8336016.", "previous_notes": "The patient is not on 5-ARI medication. Relevant comorbidities include Other and vasectomie."}

## Intervención 7 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": -0.289510423856697, "mode": "deployed", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 8 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 6.0, "spokesperson": "nested-selected fusion", "rule": "Selection inside outer folds; DEV, VAL and full-cohort results recorded."}

## Intervención 9 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 87.16559238712779, "event": 0, "calibration": {"mode": "deployed", "a": 93.67296967731494, "b": 0.1, "spokesperson": "nested-selected fusion", "percentile": 0.9733333333333334, "months_map": "90 exp(-0.1 * 12 * (1-percentile))", "event_policy": "unchanged CAPRA event policy", "validation": {"n": 75, "events": 19, "baseline_c_index": 0.7371681415929203, "candidate_c_index": 0.8234513274336284, "paired_ci95": [-0.004138922865375535, 0.20206167181978793], "eligible": true, "adopted": false, "limitations": "Small internal historical cohort; wide paired intervals; not external validation. Model selection is inside each outer fold."}}}, "uncertainty": {"interval_months": [69.73247390970224, 104.59871086455334], "base_half_width": 17.43311847742556, "imputation_half_width": 0.0, "ln_unknown": false, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 10 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": [], "ln_unknown": false, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "Nodes were sampled; do not claim missing nodal sampling."}

## Intervención 11 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The prognosis is influenced by several documented factors. Favorable findings include negative surgical margins (0.0), no seminal vesicle invasion (0.0), absence of lymph node metastasis (0.0), and absence of lymphovascular invasion (0.0). The preoperative PSA was elevated at 12. The surgical pathology showed a Gleason 4+5 with tertiary pattern 3 (ISUP grade group 5) and pathological T3a with extraprostatic extension. Countervailing factors include the high preoperative PSA and the high pathological grade/stage. The biopsy grade (Gleason 0+0, ISUP grade group 0) differed significantly from the prostatectomy specimen (Gleason 4+5, ISUP grade group 5). Missing postoperative PSA or follow-up data significantly widens the uncertainty regarding the trajectory. The current heuristic horizon suggests a time frame of approximately 87 months to recurrence. Information regarding postoperative PSA levels and its subsequent trajectory would be crucial in refining this prognosis. The fixed estimated horizon is 87.17 months. This represents expected follow-up without an event, not a known recurrence date. The sensitivity range is 69.73–104.60 months; its coverage has not been validated.
