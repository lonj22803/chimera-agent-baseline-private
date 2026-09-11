# Junta clínica — T3-059 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 60, "psa": 10, "dre": null, "active_treatment_prior_to_surgery": null}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 3.0, "group": "intermedio", "ln_unknown": 1.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+2 with tertiary pattern 4 (ISUP grade group 1), pathological stage pT3a. There was no extraprostatic extension; surgical margins were positive; the seminal vesicles were not invaded; lymphovascular invasion was present; no lymph nodes were removed."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 3.0, "sec": 2.0, "isup_rp": 1.0, "pt": 3.0, "epe": 0.0, "margins": 1.0, "svi": 0.0, "lvi": 1.0, "ln": null, "tertiary": 4.0, "ln_unknown": 1.0, "pt_ge_t3": 1.0, "tertiary_pattern_5": 0.0, "upgrade_bx_to_rp": -1.0, "capra_s": 3.0, "capra_s_group": 1.0}, "log_risk": -0.41861443435183016, "mode": "deployed", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent one biopsy session. At biopsy, Gleason 3+4 (ISUP grade group 2, AI model-predicted ISUP 2) was identified in the right peripheral zone (apex); no cribriform pattern, intraductal carcinoma or perineural invasion were identified. The reported histological growth pattern was: Adenocarcinoma."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": 0.8121977212824452, "mode": "deployed", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 1, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — EXPERT-EXPERIENCE

*case library; the closest labelled precedents and what the reading urologist did with them* · vuelta 1

I recall these other postoperative patients in the same CAPRA-S group. Each outcome belongs to another patient, not this patient. These observations cannot estimate this patient's survival or recurrence date.
Another patient, T3-067: CAPRA-S 3.0; observed censored follow-up without recurrence at 34.7 months. Do not copy this outcome into the current note.
Another patient, T3-053: CAPRA-S 3.0; observed recurrence at 52 months. Do not copy this outcome into the current note.
Another patient, T3-011: CAPRA-S 3.0; observed censored follow-up without recurrence at 56.4 months. Do not copy this outcome into the current note.

## Intervención 6 — EXPERT-GUIDELINE

*EXPERT-GUIDELINE* · vuelta 1

{"authority": "advisory; no vote or numeric horizon", "clinical_eau_group_from_G": "not recorded", "scope": "G is pre-treatment clinical stratification; not a postoperative EAU/NCCN classification.", "postoperative_findings": {"epe": 0.0, "margins": 1.0, "svi": 0.0, "lvi": 1.0, "ln_unknown": 1.0}, "follow_up": "Postoperative PSA and its trajectory are needed; pathology alone does not establish biochemical recurrence.", "reference": "EAU Prostate Cancer: Follow-up, https://uroweb.org/guidelines/prostate-cancer/chapter/followup", "retrieval": "deterministic inventory; no guideline passage was retrieved"}

## Intervención 7 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 8 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 3+2 with tertiary pattern 4 (ISUP grade group 1), pathological stage pT3a. There was no extraprostatic extension; surgical margins were positive; the seminal vesicles were not invaded; lymphovascular invasion was present; no lymph nodes were removed.", "pathology_report": "The patient underwent one biopsy session. At biopsy, Gleason 3+4 (ISUP grade group 2, AI model-predicted ISUP 2) was identified in the right peripheral zone (apex); no cribriform pattern, intraductal carcinoma or perineural invasion were identified. The reported histological growth pattern was: Adenocarcinoma.", "radiology_report": "Prostate volume: 26.91 cc. PSA density: 0.372 ng/mL/cc. PI-RADS: 5. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.8577571.", "previous_notes": null}

## Intervención 9 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": 0.1011100232830254, "mode": "deployed", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 10 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 3.0, "spokesperson": "nested-selected fusion", "rule": "Selection inside outer folds; DEV, VAL and full-cohort results recorded."}

## Intervención 11 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 33.37508522683761, "event": 0, "calibration": {"mode": "deployed", "a": 93.67296967731494, "b": 0.1, "spokesperson": "nested-selected fusion", "percentile": 0.17333333333333334, "months_map": "90 exp(-0.1 * 12 * (1-percentile))", "event_policy": "unchanged CAPRA event policy", "validation": {"n": 75, "events": 19, "baseline_c_index": 0.7371681415929203, "candidate_c_index": 0.8234513274336284, "paired_ci95": [-0.004138922865375535, 0.20206167181978793], "eligible": true, "adopted": false, "limitations": "Small internal historical cohort; wide paired intervals; not external validation. Model selection is inside each outer fold."}}}, "uncertainty": {"interval_months": [20.02505113610257, 46.725119317572656], "base_half_width": 6.675017045367523, "imputation_half_width": 6.675017045367523, "ln_unknown": true, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 12 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": ["previous_notes"], "ln_unknown": true, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "No nodes sampled; pNx is not pN0."}

## Intervención 13 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The postoperative pathology reveals a Gleason 3+2 with tertiary pattern 4 (ISUP grade group 1) and pathological stage pT3a. A positive surgical margin was documented, which is an adverse finding. Countervailing to this, the seminal vesicles were not invaded, and lymphovascular invasion was present. The biopsy identified Gleason 3+4 (ISUP grade group 2). Nodal status is documented as pNx, meaning no nodes were removed, which widens uncertainty regarding nodal involvement as pNx does not establish pN0. The finding regarding margins is noted as "positive," while the seminal vesicle status is "not invaded." Postoperative PSA is not recorded, making assessment of biochemical recurrence impossible. Information regarding postoperative PSA and its trajectory is crucial for revising the prognosis. Missing nodal sampling limits staging certainty. The fixed estimated horizon is 33.38 months. This represents expected follow-up without an event, not a known recurrence date. The sensitivity range is 20.03–46.73 months; its coverage has not been validated.
