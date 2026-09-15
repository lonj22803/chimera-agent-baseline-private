"""El reloj duro de ``common/supervisor.py``, con un trabajador de mentira.

Lo que se comprueba es lo que tumbó la fase Test: que el contenedor termina a
tiempo pase lo que pase dentro de la junta, y que lo que publica es la junta
cuando llega y la sombra cuando no. La sombra es la de verdad, sobre un caso
real del dev; sólo el trabajador es falso, porque el de verdad necesita GPU.
"""
from __future__ import annotations

import json
import os
import textwrap
import time
from pathlib import Path

import pytest

from version_final_reto.common import deadline, supervisor
from version_final_reto.common.chimera_experts.io import CLINICAL_FILENAME, FEATURES_FILENAME
from version_final_reto.common.gc_entry import REPO
from version_final_reto.common.slugs import output_filenames

WORKER = textwrap.dedent('''
    import json, os, subprocess, sys, time
    from pathlib import Path
    mode = os.environ["FAKE_MODE"]
    out = Path(os.environ["CHIMERA_WORKER_OUTPUT"])
    record = Path(os.environ["CHIMERA_DELIVERY_RECORD"])
    names = json.loads(os.environ["FAKE_NAMES"])
    child = subprocess.Popen(["sleep", "1000"])            # un nieto, como EngineCore
    Path(os.environ["FAKE_PIDFILE"]).write_text(str(child.pid))
    if mode == "hang":
        time.sleep(1000)
    for n in names:
        (out / n).write_text(json.dumps("board-" + n) + "\\n")
    record.write_text(json.dumps({"fallback": mode == "fallback", "files": names}))
    if mode == "hang_after":
        time.sleep(1000)
    child.kill()
''')


def _case_input(tmp_path: Path, task: int = 1) -> Path:
    source = REPO / f"data/task{task}/agent_input"
    if not source.is_dir():
        pytest.skip("datos del reto no disponibles")
    folder = next(p for p in sorted(source.iterdir()) if (p / FEATURES_FILENAME).is_file())
    flat = tmp_path / "input"
    flat.mkdir()
    for name in ("structured-prompt.json", CLINICAL_FILENAME[task], FEATURES_FILENAME):
        (flat / name).write_text((folder / name).read_text())
    return flat


def _run(tmp_path, monkeypatch, mode, hard=60.0, grace=30.0):
    entry = tmp_path / "fake_worker.py"
    entry.write_text(WORKER)
    out = tmp_path / "output"
    names = output_filenames(1)
    monkeypatch.setattr(supervisor, "INPUT_PATH", _case_input(tmp_path))
    monkeypatch.setattr(supervisor, "OUTPUT_PATH", out)
    monkeypatch.setattr(supervisor, "EXIT_GRACE_SECONDS", grace)
    monkeypatch.setenv("CHIMERA_HARD_SECONDS", str(hard))
    monkeypatch.setenv("CHIMERA_TMP", str(tmp_path))
    monkeypatch.setenv("FAKE_MODE", mode)
    monkeypatch.setenv("FAKE_NAMES", json.dumps(names))
    monkeypatch.setenv("FAKE_PIDFILE", str(tmp_path / "grandchild.pid"))
    monkeypatch.setenv("PYTHONPATH", f"{REPO}:{REPO / 'src'}")
    start = time.monotonic()
    code = supervisor.main(entry)
    return code, out, names, time.monotonic() - start


def _grandchild_dead(tmp_path: Path) -> bool:
    pid = int((tmp_path / "grandchild.pid").read_text())
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    # Un zombi sin recoger ya no corre: basta con que no esté vivo.
    return Path(f"/proc/{pid}/stat").read_text().split()[2] == "Z"


def test_si_la_junta_entrega_se_publican_sus_bytes(tmp_path, monkeypatch):
    code, out, names, _ = _run(tmp_path, monkeypatch, "ok")
    assert code == 0
    assert sorted(p.name for p in out.iterdir()) == sorted(names)
    for n in names:
        assert json.loads((out / n).read_text()) == "board-" + n


def test_si_la_junta_se_cuelga_corta_a_tiempo_y_publica_la_sombra(tmp_path, monkeypatch):
    code, out, names, elapsed = _run(tmp_path, monkeypatch, "hang", hard=25.0)
    assert code == 0
    assert elapsed < 25.0 + 10.0
    assert sorted(p.name for p in out.iterdir()) == sorted(names)
    decision = json.loads((out / names[0]).read_text())
    assert decision in ("yes", "no")
    assert _grandchild_dead(tmp_path), "el grupo del trabajador sigue vivo"


def test_si_la_junta_cae_al_respaldo_manda_la_sombra(tmp_path, monkeypatch):
    code, out, names, _ = _run(tmp_path, monkeypatch, "fallback")
    assert code == 0
    reasoning = json.loads((out / names[1]).read_text())
    assert isinstance(reasoning, dict) and "variable_weights" in reasoning


def test_si_entrega_y_no_sale_se_publica_la_junta_tras_la_gracia(tmp_path, monkeypatch):
    code, out, names, elapsed = _run(tmp_path, monkeypatch, "hang_after", hard=60.0, grace=2.0)
    assert code == 0
    assert elapsed < 30.0
    for n in names:
        assert json.loads((out / n).read_text()) == "board-" + n
    assert _grandchild_dead(tmp_path)


def test_la_sombra_de_t1_da_la_decision_de_los_expertos(tmp_path):
    """Las dos etapas quedan en disco y la mejor es la de los expertos."""
    from version_final_reto.common import shadow
    flat = _case_input(tmp_path)
    assert shadow.run(flat, tmp_path / "stages") == 0
    stage = shadow.best_stage(tmp_path / "stages")
    assert stage is not None and stage.name == shadow.STAGE_EXPERTS
    assert (tmp_path / "stages" / shadow.STAGE_FALLBACK / "meta.json").is_file()


def test_deadline_cuenta_hacia_el_corte_duro(monkeypatch):
    monkeypatch.delenv("CHIMERA_CASE_BUDGET_SECONDS", raising=False)
    monkeypatch.setenv("CHIMERA_HARD_DEADLINE_EPOCH", str(time.time() + 100))
    deadline.start()
    assert 95 < deadline.remaining() <= 100
    monkeypatch.setenv("CHIMERA_CASE_BUDGET_SECONDS", "0")
    deadline.start()
    assert deadline.remaining() == float("inf")
