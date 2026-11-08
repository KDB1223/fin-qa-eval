"""JSONL loading for eval items and predictions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LoadError(ValueError):
    """A dataset file could not be parsed."""


def load_jsonl(path: Path | str) -> list[dict[str, Any]]:
    """Load a JSONL file.

    Blank lines and lines whose first non-space character is ``#`` are
    comments. Each remaining line must be a JSON object.
    """

    file_path = Path(path)
    if not file_path.is_file():
        raise LoadError(f"file not found: {file_path}")
    items: list[dict[str, Any]] = []
    text = file_path.read_text(encoding="utf-8")
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LoadError(f"{file_path}:{lineno}: {exc}") from exc
        if not isinstance(payload, dict):
            raise LoadError(f"{file_path}:{lineno}: expected a JSON object")
        items.append(payload)
    return items
