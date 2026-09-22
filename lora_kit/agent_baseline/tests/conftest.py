"""Shared fixtures.

The suite is self-contained: it synthesises the ``task<N>/agent_input/<case>/``
tree from the field names documented in the README, so it runs anywhere without
the challenge dataset (which is under a data-use agreement and gitignored).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

CASE_IDS = {1: "PT-test-0001", 2: "T2-001", 3: "T3-001"}

CLINICAL_FILENAMES = {
    1: "prostate-biopsy-decision-clinical-data.json",
    2: "prostate-treatment-decision-clinical-data.json",
    3: "prostate-time-to-recurrence-or-last-follow-up-clinical-data.json",
}

FEATURES_FILENAME = "prostate-modality-level-neural-representations.json"


def _structured_prompt(task: int) -> dict:
    """A structured prompt with the documented field set for *task*."""
    if task == 3:
        return {
            "case_id": CASE_IDS[3],
            "task": 3,
            "age": 64,
            "psa": 8.2,
            "dre": "Suspicious nodule right lobe",
            "active_treatment_prior_to_surgery": "no",
        }

    payload = {
        "case_id": CASE_IDS[task],
        "task": task,
        "age": 67,
        "psa": 12.4,
        "months": 9,
        "pirads": 4,
        "psad": 0.21,
        "psav": 1.8,
        "psap": 9.9,
        "vol": 59,
        "cspca": 0.44,
        "dre": "Firm left lobe",
        "bx": "no prior biopsy",
        "medhx": "Hypertension",
        "meds": "Amlodipine 5 mg",
        "notes": "Referred by GP for elevated PSA.",
        "pmhx": "Appendectomy 1998",
        "allergies": "None known",
        "vitals": {"weight": 84, "height": 178, "bmi": 26.5, "bp": "138/85", "hr": 72, "smoking": "former"},
        "enc_dept": "Urology",
        "enc_date": "2026-02-11",
        "enc_ref": "GP",
        "enc_type": "outpatient",
        "note_sections": [{"s": "Chief complaint", "t": "Elevated PSA on screening."}],
        "occupation": "Teacher",
        "marital": "married",
        "living": "with partner",
        "next_of_kin": "spouse",
        "alcohol": "occasional",
        "exercise": "moderate",
        "ipss": 11,
        "recent_other": "none",
        "admin": "none",
    }
    if task == 2:
        payload |= {"ct": "cT2a", "bx_isup": 1, "bx_gl_prim": 3, "bx_gl_sec": 3, "bx_gl_tert": None}
    return payload


def _clinical_data(task: int) -> dict:
    """The masked EHR sections the MCP tools serve for *task*."""
    common = {
        "radiology_report": "mpMRI: PI-RADS 4 lesion, left peripheral zone, 11 mm.",
        "previous_notes": ["2025-08-02 Urology: PSA 9.1, surveillance discussed."],
        "family_history": "Father diagnosed with prostate cancer at 71.",
    }
    if task == 1:
        return common | {
            "laboratory_results": [{"test": "PSA", "value": 12.4, "unit": "ng/mL"}],
            "psa_trend": [{"date": "2024-03-01", "psa": 7.2}, {"date": "2026-02-01", "psa": 12.4}],
        }
    if task == 2:
        return common | {
            "pathology_report": "Biopsy: ISUP 1 (3+3) in 2 of 12 cores.",
            "laboratory_results": [{"test": "PSA", "value": 12.4, "unit": "ng/mL"}],
            "psa_trend": [{"date": "2024-03-01", "psa": 7.2}, {"date": "2026-02-01", "psa": 12.4}],
        }
    return common | {
        "pathology_report": "Biopsy: ISUP 2 (3+4).",
        "surgical_pathology_report": "RP: pT3a, negative margins, ISUP 2.",
    }


def _features(task: int) -> dict:
    """Frozen foundation-model embeddings, shaped as the README documents."""
    mri = [[0.1] * 1024]
    biopsy = [[0.2] * 960] if task in (2, 3) else []
    prostatectomy = [[0.3] * 960] if task == 3 else []
    return {
        "case_id": CASE_IDS[task],
        "MRI image": mri,
        "Biopsy slide": biopsy,
        "Prostatectomy slide": prostatectomy,
    }


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def templates_dir(repo_root: Path) -> Path:
    return repo_root / "templates" / "prompts"


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    """A full ``task<N>/agent_input/<case>/`` tree for all three tasks."""
    for task in (1, 2, 3):
        case_dir = tmp_path / f"task{task}" / "agent_input" / CASE_IDS[task]
        case_dir.mkdir(parents=True)
        (case_dir / "structured-prompt.json").write_text(json.dumps(_structured_prompt(task)))
        (case_dir / CLINICAL_FILENAMES[task]).write_text(json.dumps(_clinical_data(task)))
        (case_dir / FEATURES_FILENAME).write_text(json.dumps(_features(task)))
    return tmp_path


@pytest.fixture
def agent_input(data_root: Path):
    """``task -> agent_input dir`` for the synthesised tree."""
    return {task: data_root / f"task{task}" / "agent_input" for task in (1, 2, 3)}
