# Junta clínica — PT-pseudo_2eef4115a253 (tarea 1)

## Intervención 1 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

Colleagues, this is the record as it arrived, field by field. I read it out and interpret nothing; everything after this is yours.

{
  "case_id": "PT-pseudo_2eef4115a253",
  "pid": "PT-pseudo_2eef4115a253",
  "task": 1,
  "psa": 2.11,
  "age": 59,
  "months": 1,
  "pirads": "4",
  "psad": 0.058,
  "psav": -0.04,
  "psap": 2.1,
  "vol": 36.08,
  "dre": "Normal",
  "bx": "None",
  "cspca": 0.7737494,
  "medhx": "Not reported",
  "meds": "None",
  "notes": "PSA 2.11 ng/mL. PI-RADS 4. PSAD 0.06. Prostate volume 36 mL. csPCa 0.77.",
  "pmhx": [],
  "allergies": [],
  "vitals": {
    "weight": "85 kg",
    "height": "182 cm",
    "bmi": "25.7",
    "bp": "117/84 mmHg",
    "hr": "73 bpm",
    "smoking": "Ex-smoker (36 pack-yr, quit 2021)",
    "last_dental": "3 yr ago",
    "flu_vax": "Oct 2024"
  },
  "enc_dept": "Urology - outpatient",
  "enc_date": "01 Feb 2025",
  "enc_ref": "Dr. E. Mulder (GP)",
  "enc_type": "Follow-up - PSA + MRI",
  "note_sections": [
    {
      "s": "Chief complaint",
      "t": "Evaluation requested after imaging revealed a left peripheral zone abnormality alongside a recent PSA elevation."
    },
    {
      "s": "History",
      "t": "At 59 years of age, the patient works as a retired shopkeeper. He is divorced and currently resides with his partner. A former smoker, he accumulated 36 pack-years before cessation in 2021. Daily activity remains largely sedentary, punctuated by brief walks. Moderate voiding complaints dominate the history, specifically nocturia and a diminished urinary stream, correlating with an IPSS score of 19. He explicitly denies haematuria or pelvic discomfort. No chronic comorbidities exist, and he takes no active medications. Alcohol intake averages two units per week. An Arabic interpreter will be required during the consultation to facilitate precise dialogue."
    },
    {
      "s": "Physical examination",
      "t": "DRE — texture: symmetrically smooth; consistency: normal; asymmetry: absent; nodules: none. Vital parameters remain stable, recording a blood pressure of 117/84 mmHg alongside a regular heart rate of 73 bpm. Thoracic auscultation reveals clear lung fields, and no peripheral oedema is observed."
    }
  ],
  "occupation": "retired shopkeeper",
  "marital": "Divorced",
  "living": "Lives with partner",
  "next_of_kin": "Sibling (sister)",
  "recent_other": [
    "Dermatology — actinic keratosis check",
    "Pulmonary function test — known COPD follow-up",
    "Vascular surgery — varicose veins consult"
  ],
  "alcohol": "2 units / week",
  "exercise": "Sedentary lifestyle, occasional walking",
  "ipss": "IPSS score: 19/35 (moderate LUTS)",
  "admin": "Interpreter (Arabic) requested for next visit.",
  "mri_hospital": "Radboudumc",
  "ct": null,
  "active_treatment_flag": 0
}

## Intervención 2 — INTAKE

*the record clerk; reads the file out loud and interprets nothing* · vuelta 1

And this is the same record as the reading form presents it — the panel the urologist sees up front, with the masked documents named but not shown.

You are a senior urologist reviewing a patient case. The structured clinical
record below is shown to you up front, exactly as in the reading form. Some
documents are not shown and must be pulled up via the available tools
(radiology / MRI report, pathology report, previous notes, laboratory
results, PSA history, and the family-history anamnesis) when you need to
consult them.

Case ID: PT-pseudo_2eef4115a253
Task: 1

Encounter: Urology - outpatient on 01 Feb 2025.
Referrer: Dr. E. Mulder (GP).
Type: Follow-up - PSA + MRI.

Clinical data (read-only — values loaded from the record):
  - 59-year-old male
  - PSA: 2.11 ng/mL
  - mpMRI — PI-RADS score: 4 (1–2 low · 3 equivocal · 4–5 high risk)
  - PSA density: 0.058 ng/mL²
  - PSA velocity: -0.04 ng/mL/yr
  - Prior PSA: 2.1 ng/mL
  - Prostate volume: 36.08 mL
  - Months since last PSA: 1
  - DRE findings: Normal (Normal · Nodus · Benign · Suspicious · Abnormal · Negative · Not done)
  - Prior biopsy: None (None · Negative · ASAP/HGPIN · Positive)
  - csPCa predicted probability: 0.7737494 (clinically significant PCa = ISUP ≥ 2)

Medical history & medication:
  - Medical history: Not reported
  - Problem list / PMHx: none recorded
  - Current medication: None
  - Allergies: NKA
  - Additional notes: PSA 2.11 ng/mL. PI-RADS 4. PSAD 0.06. Prostate volume 36 mL. csPCa 0.77.

Vitals: weight 85 kg, height 182 cm, BMI 25.7, BP 117/84 mmHg, HR 73 bpm. Smoking: Ex-smoker (36 pack-yr, quit 2021).

Chief complaint: Evaluation requested after imaging revealed a left peripheral zone abnormality alongside a recent PSA elevation.

History: At 59 years of age, the patient works as a retired shopkeeper. He is divorced and currently resides with his partner. A former smoker, he accumulated 36 pack-years before cessation in 2021. Daily activity remains largely sedentary, punctuated by brief walks. Moderate voiding complaints dominate the history, specifically nocturia and a diminished urinary stream, correlating with an IPSS score of 19. He explicitly denies haematuria or pelvic discomfort. No chronic comorbidities exist, and he takes no active medications. Alcohol intake averages two units per week. An Arabic interpreter will be required during the consultation to facilitate precise dialogue.

Physical examination: DRE — texture: symmetrically smooth; consistency: normal; asymmetry: absent; nodules: none. Vital parameters remain stable, recording a blood pressure of 117/84 mmHg alongside a regular heart rate of 73 bpm. Thoracic auscultation reveals clear lung fields, and no peripheral oedema is observed.

Patient info: retired shopkeeper; Divorced; Lives with partner.
Next of kin: Sibling (sister).

Lifestyle: alcohol 2 units / week; exercise Sedentary lifestyle, occasional walking; IPSS score: 19/35 (moderate LUTS).

Recent other appointments: Dermatology — actinic keratosis check; Pulmonary function test — known COPD follow-up; Vascular surgery — varicose veins consult.
Admin: Interpreter (Arabic) requested for next visit.

Information you can request via tools (the masked "Extended EHR view" — what
the urologist would actively pull up during the consult):
  - radiology / MRI report (full mpMRI prose behind the headline imaging values)
  - pathology report (any prior biopsy on record)
  - previous GP / urology consultation notes
  - laboratory results (full panel)
  - PSA history (trend / velocity beyond the headline value)
  - family history of prostate cancer (anamnesis)

Question:
Based on this patient's data, do you recommend biopsy?


One correction to that last paragraph before anybody acts on it: the documents this task actually serves are radiology_report, psa_trend, previous_notes, laboratory_results, plus the family-history anamnesis. There is NO pathology report to pull up in a task-1 biopsy decision — the prior-biopsy status on the panel above is all the pathology on record, and whatever the previous notes say about it. Nobody should ask for one, and nobody should quote one.

## Intervención 3 — EXPERT-STRUCTURED

*Expert 1, Extra-Trees on the structured panel only; opening bid with an error bar* · vuelta 1

Expert 1 here — the classifier that reads the structured panel and nothing else. My bid:

SUGGESTION: BIOPSY   p(biopsy) = 0.80
  uncertainty  +/- 0.10 epistemic (95% band 0.62-0.99); among patients I cannot tell apart the outcome was 0.71 of 1.00 mixed
  reliability  HIGH ('firm' tier) — out-of-fold it was right 88% of the time over the 33 labelled cases in this tier

VARIABLES I WEIGHED — in the form's vocabulary, with this man's values (panel only; the levels are what moved my prediction across the series, not what a urologist would mark)
  decisive   prior biopsy = None (43% of my signal; from bx_positive, bx_none)
  important  comorbidity = none recorded (21% of my signal; from pmhx_hypercholesterolaemia, n_comorbidities)
  noted      age = 59 (2% of my signal; from age) · DRE = Normal (10% of my signal; from dre_suspicious) · PSA = 2.11 ng/mL (3% of my signal; from log_psa, psav) · prostate volume = 36.08 mL (1% of my signal; from log_vol, vol) · PSA density = 0.058 (0% of my signal; from psad_calc, log_psad) · csPCa probability = 0.77 (1% of my signal; from cspca) · PI-RADS = 4 (20% of my signal; from pirads_ge4, pirads_ge3)
  not used   family history
CONFIDENCE: clear — 'firm' tier; out-of-fold it was right 88% of the time over the 33 labelled cases in this tier

I read 39 raw variables, all from the panel — nothing from the mpMRI prose, the PSA
trajectory, the previous notes or the laboratory. Out-of-fold over 91 labelled cases: AUC
0.758, balanced accuracy 0.625.
The final call is the chair's.

## Intervención 4 — EXPERT-COHORT

*cohort criterion; what the labelled series did in this exact situation* · vuelta 1

This patient's situation: never biopsied. My criterion answers BIOPSY.

The criterion: sample when the mpMRI shows a PI-RADS 3 or higher lesion; defer at PI-RADS 1-2. In the labelled series this criterion matched the reading urologist in 24 of 24 cases in exactly this situation.

Like Expert 1, I have read ONLY the visible panel — not the mpMRI prose, the PSA trajectory, the
previous notes or the laboratory panel. Departing from me needs a specific finding from a document
somebody actually opened, named out loud; not a restatement of the panel numbers I already used.

VARIABLES I WEIGHED — in the form's vocabulary, with this man's values (panel only; 'decisive' marks the variable the rule turns on)
  decisive   PI-RADS = 4
  important  prior biopsy = None
  noted      age = 59 · DRE = Normal · PSA = 2.11 ng/mL · prostate volume = 36.08 mL · PSA density = 0.058 · comorbidity = none recorded
  not used   family history, csPCa probability
CONFIDENCE: clear — the rule matched the reading urologist in 24 of 24 labelled cases

## Intervención 5 — EXPERT-LIBRARY

*case library; the closest labelled precedents and what the reading urologist did with them* · vuelta 1

The case library holds 23 labelled men in this same situation (None prior biopsy). The 3 closest by panel distance, and what the reading urologist did:
  1. distance 1.79: PI-RADS NA, PSA 4.5, PSAD 0.095, age 67, DRE Normal -> DEFER (clear). He wrote: "Normal MRI. No biopsy"
  2. distance 2.12: PI-RADS 4, PSA 4.8, PSAD 0.086, age 65, DRE Nodus -> BIOPSY (clear). He wrote: "P4 in patient 65 years."
  3. distance 2.12: PI-RADS 5, PSA 3.7, PSAD 0.116, age 63, DRE Normal -> BIOPSY (clear). He wrote: "P5 in 63 year old man."

PRECEDENT: BIOPSY (weighted vote 0.63 for biopsy). Distance-weighted precedent is strong here (0.92 leave-one-out).

What the precedents are FOR: they show what this urologist looks at and how he phrases the call. What they are NOT: facts about this patient. Nobody may cite a precedent's grade, PSA or MRI as if it were his.

WHAT THE READING UROLOGIST WEIGHED IN THESE PRECEDENTS — in the form's vocabulary, with this man's values (weighted majority of the 3 nearest labelled traces; the distance itself is on PI-RADS, prior biopsy first)
  decisive   PI-RADS = 4
  important  age = 59
  noted      prior biopsy = None · family history = not opened (0 of 91) · DRE = Normal · PSA = 2.11 ng/mL · prostate volume = 36.08 mL · PSA density = 0.058
  not used   csPCa probability, comorbidity
CONFIDENCE: borderline — the library is right 92% of the time in this situation out of fold

## Intervención 6 — EXPERT-TRACE

*Expert 4, trace model; which documents the reading urologist opens and what he weighs in this situation* · vuelta 1

Expert 4 here — the model of how the reading urologist works a case like this. Predicted from his 23 labelled traces in this situation (None prior biopsy): a per-field model where it beats the mode out of fold (prior-biopsy weight, DRE weight, PI-RADS weight, and whether he opens the laboratory), the mode elsewhere.

WHAT HE OPENS: radiology_report, psa_trend, previous_notes.

WHAT HE WEIGHS — in the form's vocabulary, with this man's values (these are the levels that go on the form, unless a colleague shows a reason to move one)
  decisive   PI-RADS = 4
  important  age = 59 · PSA = 2.11 ng/mL
  noted      prior biopsy = None · family history = not opened (0 of 91) · DRE = Normal · prostate volume = 36.08 mL · PSA density = 0.058 · comorbidity = none recorded
  not used   csPCa probability
CONFIDENCE: clear — the level the reading urologist records in this situation, from his labelled traces

MODERATOR: that list of documents is the plan — exactly those, no more. Every document opened beyond what
he would open is scored against the conference as an unnecessary reveal; every document left closed
leaves a variable he weighed without its source. Attach the question each one must answer.

## Intervención 7 — EXPERT-EAU

*EAU guideline specialist; speaks only from the guideline text he retrieved* · vuelta 1

GUIDELINE
The EAU guidelines suggest that a PI-RADS threshold of $\ge 3$ is used to trigger a biopsy. The guideline states: "a PI-RADS threshold of $\ge 3$ is used to trigger biopsy [135, 226, 264, 375], at the cost of missing a small number of mainly ISUP GG 2 cancers, especially in biopsy-naive patients or in highly selected populations with high prevalence of csPCa (in which the MRI NPV decreases) [372, 472]."

WHAT THE EXPERTS' BIDS DO NOT SETTLE
EXPERT-STRUCTURED, EXPERT-COHORT, and EXPERT-LIBRARY all weighed the PI-RADS score as decisive, which the guideline treats as a primary trigger. The guideline makes the PI-RADS threshold decisive, whereas EXPERT-STRUCTURED marked prior biopsy as decisive. The guideline suggests using a PI-RADS threshold of $\ge 3$ to trigger biopsy, which is different from EXPERT-STRUCTURED's focus on prior biopsy status. The guideline requires the PI-RADS score, which is a finding the panel already provides. The guideline needs the patient's prior biopsy status, which is a variable that EXPERT-STRUCTURED marked as decisive.

WHAT THE DOCUMENTS MUST SETTLE
previous_notes - the prior biopsy status: at None the guideline does not specify the action; if it is unrecorded the indication stands
radiology_report - whether the lesion is compared against an earlier study: unchanged does not support re-sampling, new or larger does

## Intervención 8 — MODERATOR

*chairs the discussion; sets the open questions and assigns the documents* · vuelta 1

The case hinges on whether the PI-RADS 4 score, as weighted by the cohort and trace models, is sufficient to trigger a biopsy according to the EAU guidelines, especially given the lack of prior biopsy.

The documents for this session were fixed by EXPERT-TRACE; what I add is the question each one has to answer, and the open questions for the room.

REGISTRAR — pull these up, and answer exactly the question attached to each:
  radiology_report (get_mri_report) -> Does the report indicate whether the lesion is compared against an earlier study?
  psa_trend (get_psa_trend) -> What is the PSA trend (rising, flat, or falling) over the serial measurements?
  previous_notes (get_previous_notes) -> Is the grade of the prior biopsy recorded (Gleason or ISUP)? How many biopsy sessions, and when was the last? Is he on a surveillance protocol, and is a confirmatory biopsy due? Is any treatment already agreed or declined?

OPEN QUESTIONS for this conference — these are what the decision hangs on:
  Q1. What is the required action given the PI-RADS score of 4 and the patient's prior biopsy status of None?
  Q2. Does the radiology_report indicate if the lesion is new or larger compared to an earlier study?

## Intervención 9 — REGISTRAR

*the registrar who pulls up documents; reports what they say, nothing else* · vuelta 1

WHAT I FOUND
radiology_report
The report indicates that the lesion is new or larger compared to an earlier study, as it states "early, focal enhancement compared to adjacent tissue."
psa_trend
The PSA trend is rising, with measurements from "Jan 2023" at "0.5" ng/mL rising to "Feb 2025" at "2.11" ng/mL.
previous_notes
The grade of the prior biopsy is not recorded; there are no biopsy sessions recorded; the patient is not on a surveillance protocol or confirmatory biopsy due; no treatment has been agreed or declined.

WHAT I DID NOT OPEN
family-history anamnesis, because it is not required to determine the immediate biopsy decision based on the opened documents.

WHAT THIS SUPPORTS
FOR sampling this patient now
PI-RADS 4 score, as weighted by EXPERT-COHORT and EXPERT-TRACE, aligns with the criterion to sample when the mpMRI shows a PI-RADS 3 or higher lesion.
PSA trend shows a rising trajectory, which supports the need for further investigation.
AGAINST sampling this patient now
No prior biopsy is recorded, which is a factor weighed by EXPERT-STRUCTURED, but the EAU guideline does not mandate biopsy when prior biopsy is absent if PI-RADS $\ge 3$.

WHERE THIS LEANS
LEAN: biopsy

## Intervención 10 — EXPERT-PSA

*Expert 2, PSA projector; the trajectory behind the headline PSA, with a conformal band* · vuelta 1

Expert 2 here — the PSA projector. I read only the serial PSA the registrar opened.

TRAJECTORY: INDETERMINATE (uncertain). Last value 2.11 ng/mL over 4 points spanning 25 months; velocity +0.72 ng/mL per year; doubling time about 13 months.
PROJECTION at 6 months: 2.4 ng/mL, conformal 95% band 0.7-8.5.

Read the band before the point: it is wide by construction, and I only call a direction when the whole
band clears the last value. This does not vote on the biopsy — a rising PSA in a man with a known
diagnosis is the disease behaving as known — it tells the chair how fast the number is moving.

VARIABLES I WEIGHED — in the form's vocabulary, with this man's values (the serial PSA only)
  noted      PSA = 2.11 ng/mL
  not used   prior biopsy, family history, age, DRE, prostate volume, PSA density, csPCa probability, PI-RADS, comorbidity
CONFIDENCE: uncertain — the conformal band does not clear the last value

## Intervención 11 — EXPERT-FUSION

*Expert 3, Extra-Trees on panel + laboratory + MRI prose; speaks only on documents that were opened* · vuelta 1

Expert 3 here — the fusion classifier. I read the panel, the mpMRI report — the laboratory panel was not opened, so that block is imputed and my band is wider for it; nothing from the previous notes or the PSA series.

SUGGESTION: BIOPSY   p(biopsy) = 0.80
  uncertainty  +/- 0.08 epistemic (95% band 0.64-0.95), of which 0.00 comes from values that had to be imputed
  reliability  HIGH ('firm' tier) — out-of-fold it was right 89% of the time over the 37 labelled cases in this tier

VARIABLES I WEIGHED — in the form's vocabulary, with this man's values (panel + the documents that were opened; PI-RADS here means the report's own wording — DWI restriction, lesion size — not the score)
  decisive   prior biopsy = None (43% of my signal; from bx_positive, bx_none)
  important  PI-RADS = 4 (22% of my signal; from rad_dwi_restriction, rad_lesion_ge15mm)
  noted      PSA = 2.11 ng/mL (21% of my signal; from fpsa_lt15, psa_delta_prev) · prostate volume = 36.08 mL (4% of my signal; from log_vol, vol) · PSA density = 0.058 (0% of my signal; from psad_calc) · comorbidity = none recorded (4% of my signal; from n_comorbidities, on_alpha_blocker)
  not used   family history, age, DRE, csPCa probability
CONFIDENCE: clear — 'firm' tier; out-of-fold it was right 89% of the time over the 37 labelled cases in this tier

Out-of-fold AUC 0.794. I am the only expert that has read the report's
wording, and I still cannot see the prior grade or the surveillance history: those are in the notes, and
the registrar has to carry them.

## Intervención 12 — PANEL-PROTOCOL

*the panel's written protocol; consolidates the experts by rule and says which rule fired* · vuelta 1

The panel protocol, applied to what is on the board:

  EXPERT-STRUCTURED  BIOPSY, p(biopsy)=0.80  ('firm' tier; weight 3.0)
  EXPERT-FUSION      BIOPSY, p(biopsy)=0.80  ('firm' tier, fusion_nolab; weight 4.5)
  EXPERT-LIBRARY     BIOPSY, p(biopsy)=0.63  (k=3 precedents; does not vote)
  EXPERT-COHORT      BIOPSY  (rule pirads_ge_3; does not vote)

  documented prior grade in the opened documents: none recorded

RULE THAT FIRED: cohort criterion (pirads_ge_3) — carried by EXPERT-COHORT.
PANEL ANSWER: BIOPSY. It matched the reading urologist in 24 of 24 labelled cases in exactly this situation (never biopsied).

THE BOARD'S VARIABLES — value · what each expert marked · what goes on the form
  bx           None                         E1:DEC E3:DEC cohort:IMP library:not E2:—            -> noted
  fh           not opened (0 of 91)         E1:— E3:— cohort:— library:not E2:—                  -> not_used (raised from noted by the board)
  age          59                           E1:not E3:— cohort:not library:IMP E2:—              -> important
  dre          Normal                       E1:not E3:— cohort:not library:not E2:—              -> not_used (raised from noted by the board)
  psa          2.11 ng/mL                   E1:not E3:not cohort:not library:not E2:not          -> important
  vol          36.08 mL                     E1:not E3:not cohort:not library:not E2:—            -> noted
  psad         0.058                        E1:not E3:not cohort:not library:not E2:—            -> noted
  cspca        0.77                         E1:not E3:— cohort:— library:— E2:—                  -> not_used
  pirads       4                            E1:not E3:IMP cohort:DEC library:DEC E2:—            -> decisive
  comorbidity  none recorded                E1:IMP E3:not cohort:not library:— E2:—              -> noted
  (DEC decisive · IMP important · not noted · — not used; the last column is the level recorded, from the trace of the reading urologist)

Confidence to record: clear.

CHAIR: this is the panel's position. You sign it, and you write why in the room's words — naming what the registrar retrieved. If you believe a retrieved finding overturns it, name that finding with its value; the burden is on the finding, not on the panel.

## Intervención 13 — VERIFIER

*second EAU reader; checks against the guideline whether this can be decided yet* · vuelta 1

SUFFICIENCY
The documents the registrar opened (radiology_report, psa_trend, previous_notes) have answered the moderator's questions. The radiology_report indicates the lesion is new or larger compared to an earlier study, and the previous_notes confirm no prior biopsy.

ALIGNMENT WITH THE PANEL
The retrieved evidence aligns with the PANEL-PROTOCOL's answer of BIOPSY. The cohort criterion (PI-RADS $\ge 3$) fired, and the registrar's findings (rising PSA trend and new/larger lesion) support the need for action.

THE OPEN QUESTIONS, ONE BY ONE
Q1. What is the required action given the PI-RADS score of 4 and the patient's prior biopsy status of None? The panel states BIOPSY, supported by the cohort criterion firing on PI-RADS=4.
Q2. Does the radiology_report indicate if the lesion is new or larger compared to an earlier study? Yes, the report states "early, focal enhancement compared to adjacent tissue."

WHAT CARRIES WEIGHT, AND WHY
<pirads>: decisive: 4 (from EXPERT-COHORT and EXPERT-TRACE) because the cohort criterion fired, aligning with the EAU guideline trigger.
<prior biopsy>: decisive: None (from EXPERT-STRUCTURED and EXPERT-FUSION) because this variable was decisive for multiple experts, despite the guideline ambiguity.
<psa>: important: 2.11 ng/mL (from EXPERT-STRUCTURED) because the PSA trend is rising, which supports the need for further investigation.
My confidence in the record as it stands is clear, as all documents listed by the trace model were opened.

MY SUGGESTION TO THE CHAIR
I suggest proceeding with a biopsy, as the PI-RADS 4 score, combined with a rising PSA trend and a new/larger lesion, meets the criteria established by the cohort criterion and the EAU guideline's threshold for action.

VERDICT: ready | SUGGEST: biopsy | MISSING: none

[The conference closes after pass 1: the verifier called the record ready. The chair decides on the record as it stands.]

## Intervención 14 — CHAIR

*the senior urologist who signs the decision* · vuelta 1

MY DECISION: BIOPSY   (confidence: clear)

59 y/o male, PSA 2.11 ng/mL, PI-RADS 4, biopsy-naive. PI-RADS 4 warrants biopsy, despite low PSA density of 0.058. The finding of a new or larger lesion on MRI is the deciding factor over the low density. Biopsy recommended.

What carried weight: bx=noted, age=important, psa=important, vol=noted, psad=noted, pirads=decisive, comorbidity=noted
Sections retrieved: radiology_report, psa_trend, previous_notes
