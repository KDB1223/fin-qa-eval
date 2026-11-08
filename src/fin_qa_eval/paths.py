"""Resolve default dataset paths from the working tree."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    """Directory that contains ``data/`` when running from a checkout.

    Editable installs live in ``src/fin_qa_eval``, so the checkout root is
    two parents up. A ``data`` directory in the current working directory
    wins, which keeps CI and ``pip install -e .`` identical.
    """

    cwd_data = Path.cwd() / "data"
    if cwd_data.is_dir():
        return Path.cwd()
    return Path(__file__).resolve().parents[2]


def data_root() -> Path:
    override = os.environ.get("FIN_QA_EVAL_DATA")
    if override:
        return Path(override)
    return repo_root() / "data"


def gold_path() -> Path:
    override = os.environ.get("FIN_QA_EVAL_GOLD")
    if override:
        return Path(override)
    return data_root() / "samples" / "eval_set.jsonl"


def schema_path() -> Path:
    return data_root() / "schema" / "eval_item.schema.json"


def conventions_path() -> Path:
    return data_root() / "schema" / "field_conventions.yaml"


def bad_samples_path() -> Path:
    return data_root() / "fixtures" / "bad_samples.jsonl"


def demo_predictions_path() -> Path:
    return repo_root() / "examples" / "predictions.jsonl"
