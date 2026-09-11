# Junta clínica — T3-009 (tarea 3)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

{"age": 69, "psa": 8.7, "dre": "Digital rectal examination was abnormal bilaterally. The clinical T-stage derived from digital rectal examination was cT1c.", "active_treatment_prior_to_surgery": null}

## Intervención 2 — EXPERT-CAPRA

*EXPERT-CAPRA* · vuelta 1

{"score": 5.0, "group": "intermedio", "ln_unknown": 1.0, "published_c_index": 0.77, "reference": "Cooperberg et al. 2011, doi:10.1002/cncr.26169", "source": "surgical_pathology_report and preoperative PSA", "surgical_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+3 with tertiary pattern 5 (ISUP grade group 3), pathological stage pT2. There was no extraprostatic extension; surgical margins were positive; the seminal vesicles were not invaded; lymphovascular invasion was absent; no lymph nodes were removed."}

## Intervención 3 — EXPERT-SURGICAL

*EXPERT-SURGICAL* · vuelta 1

{"findings": {"prim": 4.0, "sec": 3.0, "isup_rp": 3.0, "pt": 2.0, "epe": 0.0, "margins": 1.0, "svi": 0.0, "lvi": 0.0, "ln": null, "tertiary": 5.0, "ln_unknown": 1.0, "pt_ge_t3": 0.0, "tertiary_pattern_5": 1.0, "upgrade_bx_to_rp": 3.0, "capra_s": 5.0, "capra_s_group": 1.0}, "log_risk": -0.12163698416317231, "mode": "deployed", "oof_c_index": 0.772566371681416, "delta_capra_bootstrap_95": [-0.0643882049240864, 0.15001344086021506], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "biopsy_source": "The patient underwent 2 biopsy sessions. At the first session, Gleason 0+0 (ISUP grade group 0, AI model-predicted ISUP 4) was identified; no cribriform pattern, intraductal carcinoma or perineural invasion were identified. 85.6 months later, at the second session, Gleason 3+4 (ISUP grade group 2, AI model-predicted ISUP 3) was identified in the bilateral peripheral zone; perineural invasion was present, with no cribriform pattern or intraductal carcinoma. The reported histological growth pattern was: Acinar."}

## Intervención 4 — EXPERT-DIGITAL

*EXPERT-DIGITAL* · vuelta 1

{"log_risk": -0.39603489434728606, "mode": "deployed", "oof_c_index": 0.7106194690265487, "delta_capra_bootstrap_95": [-0.24444659341054392, 0.19233295964125552], "role": "advisory; does not replace predeclared CAPRA-S spokesperson", "prostatectomy_slides": 1, "limitation": "Frozen vectors; no visual histology interpretation or independent BCR validation."}

## Intervención 5 — EXPERT-EXPERIENCE

*case library; the closest labelled precedents and what the reading urologist did with them* · vuelta 1

I recall these other postoperative patients in the same CAPRA-S group. Each outcome belongs to another patient, not this patient. These observations cannot estimate this patient's survival or recurrence date.
Another patient, T3-073: CAPRA-S 5.0; observed censored follow-up without recurrence at 61.1 months. Do not copy this outcome into the current note.
Another patient, T3-027: CAPRA-S 5.0; observed recurrence at 19.9 months. Do not copy this outcome into the current note.
Another patient, T3-052: CAPRA-S 5.0; observed recurrence at 6.2 months. Do not copy this outcome into the current note.

## Intervención 6 — EXPERT-GUIDELINE

*EXPERT-GUIDELINE* · vuelta 1

{"authority": "advisory; no vote or numeric horizon", "clinical_eau_group_from_G": "not recorded", "scope": "G is pre-treatment clinical stratification; not a postoperative EAU/NCCN classification.", "postoperative_findings": {"epe": 0.0, "margins": 1.0, "svi": 0.0, "lvi": 0.0, "ln_unknown": 1.0}, "follow_up": "Postoperative PSA and its trajectory are needed; pathology alone does not establish biochemical recurrence.", "reference": "EAU Prostate Cancer: Follow-up, https://uroweb.org/guidelines/prostate-cancer/chapter/followup", "retrieval": "deterministic inventory; no guideline passage was retrieved"}

## Intervención 7 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

surgical_pathology_report: What grade, stage, margins, vesicles and nodal sampling are documented?
pathology_report: Does biopsy grade differ from the prostatectomy specimen?
radiology_report: What local extent and imaging limitations are documented?
previous_notes: What treatment and postoperative follow-up are documented?

## Intervención 8 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

{"surgical_pathology_report": "The robot-assisted radical prostatectomy specimen showed Gleason 4+3 with tertiary pattern 5 (ISUP grade group 3), pathological stage pT2. There was no extraprostatic extension; surgical margins were positive; the seminal vesicles were not invaded; lymphovascular invasion was absent; no lymph nodes were removed.", "pathology_report": "The patient underwent 2 biopsy sessions. At the first session, Gleason 0+0 (ISUP grade group 0, AI model-predicted ISUP 4) was identified; no cribriform pattern, intraductal carcinoma or perineural invasion were identified. 85.6 months later, at the second session, Gleason 3+4 (ISUP grade group 2, AI model-predicted ISUP 3) was identified in the bilateral peripheral zone; perineural invasion was present, with no cribriform pattern or intraductal carcinoma. The reported histological growth pattern was: Acinar.", "radiology_report": "Prostate volume: 35.27 cc. PSA density: 0.247 ng/mL/cc. PI-RADS: 4. AI model-predicted probability of clinically significant prostate cancer (0–1): 0.82454866.", "previous_notes": "The patient is not on 5-ARI medication."}

## Intervención 9 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

{"log_risk": -0.2259980600070453, "mode": "deployed", "oof_c_index": 0.831858407079646, "delta_capra_bootstrap_95": [-0.02108114607668001, 0.22708388696961646], "role": "advisory; does not replace predeclared CAPRA-S spokesperson"}

## Intervención 10 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

{"risk": 5.0, "spokesperson": "nested-selected fusion", "rule": "Selection inside outer folds; DEV, VAL and full-cohort results recorded."}

## Intervención 11 — EXPERT-HORIZON

*EXPERT-HORIZON* · vuelta 1

{"horizon": {"months_to_recurrence": 85.78204083697543, "event": 0, "calibration": {"mode": "deployed", "a": 93.67296967731494, "b": 0.1, "spokesperson": "nested-selected fusion", "percentile": 0.96, "months_map": "90 exp(-0.1 * 12 * (1-percentile))", "event_policy": "unchanged CAPRA event policy", "validation": {"n": 75, "events": 19, "baseline_c_index": 0.7371681415929203, "candidate_c_index": 0.8234513274336284, "paired_ci95": [-0.004138922865375535, 0.20206167181978793], "eligible": true, "adopted": false, "limitations": "Small internal historical cohort; wide paired intervals; not external validation. Model selection is inside each outer fold."}}}, "uncertainty": {"interval_months": [55.75832654403403, 115.80575512991683], "base_half_width": 17.156408167395085, "imputation_half_width": 12.867306125546314, "ln_unknown": true, "validated_coverage": false, "meaning": "heuristic sensitivity range, not a calibrated prediction interval"}}

## Intervención 12 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

{"ready": true, "missing_documents": [], "ln_unknown": true, "limitations": "Numerically ready; postoperative PSA trajectory and follow-up may be absent. Sensitivity range is heuristic; no confidence calibration is validated.", "nodal_status": "No nodes sampled; pNx is not pN0."}

## Intervención 13 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

The postoperative pathology revealed a Gleason 4+3 with tertiary pattern 5 (ISUP grade group 3) and pathological stage pT2. A positive surgical margin was documented, which is an adverse finding. Countervailing findings include the absence of extraprostatic extension and no invasion of the seminal vesicles, as noted in the surgical pathology report: "There was no extraprostatic extension; surgical margins were positive; the seminal vesicles were not invaded." The biopsy findings showed a progression from Gleason 0+0 to Gleason 3+4, with perineural invasion noted at the second session. Nodal status is uncertain as no nodes were removed, meaning pNx does not establish node-negative disease, which widens the uncertainty regarding regional disease control. Postoperative PSA is not recorded, so biochemical recurrence cannot be assessed. Information regarding postoperative PSA and its trajectory is crucial for revising the prognosis. The fixed estimated horizon is 85.78 months. This represents expected follow-up without an event, not a known recurrence date. The sensitivity range is 55.76–115.81 months; its coverage has not been validated.
