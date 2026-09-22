"""Frozen foundation-model embeddings.

The baseline does not consume these, but any solution that scores Task 3 will.
The store must stay tolerant of missing modalities: that absence is the point of
the challenge, not a broken case.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chimera_agent_baseline.features import FeatureStore

from .conftest import CASE_IDS, FEATURES_FILENAME

MRI = "MRI image"
BIOPSY = "Biopsy slide"
PROSTATECTOMY = "Prostatectomy slide"


@pytest.mark.parametrize("task", [1, 2, 3])
def test_store_indexes_by_case_id(agent_input, task: int) -> None:
    store = FeatureStore(agent_input[task])

    assert store.list_case_ids() == [CASE_IDS[task]]


@pytest.mark.parametrize(
    ("task", "origin", "dim"),
    [(1, MRI, 1024), (2, MRI, 1024), (2, BIOPSY, 960), (3, PROSTATECTOMY, 960)],
)
def test_origins_have_the_documented_dimensionality(agent_input, task: int, origin: str, dim: int) -> None:
    store = FeatureStore(agent_input[task])

    vectors = store.get_origin(CASE_IDS[task], origin)

    assert vectors and all(len(v) == dim for v in vectors)


def test_every_origin_is_a_list_even_when_single(agent_input) -> None:
    """MRI ships one vector, but as a one-element list, so loading is uniform."""
    store = FeatureStore(agent_input[1])

    assert isinstance(store.get_origin(CASE_IDS[1], MRI), list)


def test_absent_origin_returns_empty_not_none(agent_input) -> None:
    """Task 1 has no slides. A predictor must see [] and carry on."""
    store = FeatureStore(agent_input[1])

    assert store.get_origin(CASE_IDS[1], PROSTATECTOMY) == []


def test_unknown_case_returns_empty_mapping(agent_input) -> None:
    store = FeatureStore(agent_input[1])

    assert store.get(CASE_IDS[1] + "-nope") == {}


def test_case_without_a_features_file_is_simply_absent(data_root: Path) -> None:
    """4 of the 195 real task-1 cases ship no embeddings at all."""
    bare = data_root / "task1" / "agent_input" / "PT-no-features"
    bare.mkdir()
    (bare / "structured-prompt.json").write_text(json.dumps({"case_id": "PT-no-features"}))

    store = FeatureStore(data_root / "task1" / "agent_input")

    assert "PT-no-features" not in store.list_case_ids()
    assert store.get("PT-no-features") == {}


def test_malformed_features_file_is_skipped_not_fatal(data_root: Path) -> None:
    broken = data_root / "task1" / "agent_input" / "PT-broken"
    broken.mkdir()
    (broken / FEATURES_FILENAME).write_text("{not json")

    store = FeatureStore(data_root / "task1" / "agent_input")

    assert "PT-broken" not in store.list_case_ids()


def test_missing_directory_is_survivable(tmp_path: Path) -> None:
    assert FeatureStore(tmp_path / "nope").list_case_ids() == []
