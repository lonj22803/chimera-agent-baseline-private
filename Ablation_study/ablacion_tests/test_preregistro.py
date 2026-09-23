from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "Ablation_study" / "PREREGISTRO.md"
FULL_HASH = ROOT / "Ablation_study" / "results" / "preregistro.sha256"
PREFIX_HASH = ROOT / "Ablation_study" / "results" / "preregistro_pre_desviaciones.sha256"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_preregistro_is_frozen_outside_desviaciones() -> None:
    text = PREREG.read_text(encoding="utf-8")
    full_expected = FULL_HASH.read_text(encoding="utf-8").split()[0]
    if _digest(text.encode("utf-8")) == full_expected:
        return

    marker = "\n## Desviaciones\n"
    assert marker in text
    prefix = text.split(marker, 1)[0] + marker
    prefix_expected = PREFIX_HASH.read_text(encoding="utf-8").split()[0]
    assert _digest(prefix.encode("utf-8")) == prefix_expected
