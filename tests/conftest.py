from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def gold_path(repo_root: Path) -> Path:
    return repo_root / "data" / "samples" / "eval_set.jsonl"


@pytest.fixture(scope="session")
def bad_path(repo_root: Path) -> Path:
    return repo_root / "data" / "fixtures" / "bad_samples.jsonl"


@pytest.fixture(scope="session")
def pred_path(repo_root: Path) -> Path:
    return repo_root / "examples" / "predictions.jsonl"
