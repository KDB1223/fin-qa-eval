"""JSON Schema loading and structural validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from fin_qa_eval.paths import conventions_path, schema_path


class SchemaLoadError(ValueError):
    """The bundled schema or conventions file is unusable."""


def load_schema(path: Path | None = None) -> dict[str, Any]:
    schema_file = path or schema_path()
    try:
        schema = json.loads(schema_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SchemaLoadError(f"cannot read schema {schema_file}: {exc}") from exc
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise SchemaLoadError(f"invalid JSON Schema: {exc.message}") from exc
    return schema


def load_conventions(path: Path | None = None) -> dict[str, Any]:
    conventions_file = path or conventions_path()
    try:
        payload = yaml.safe_load(conventions_file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SchemaLoadError(f"cannot read conventions {conventions_file}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SchemaLoadError("field conventions must be a mapping")
    return payload


def schema_errors(items: list[dict[str, Any]], schema: dict[str, Any]) -> list[str]:
    """Return human-readable JSON Schema violations, one string per error."""

    validator = Draft202012Validator(schema)
    messages: list[str] = []
    for index, item in enumerate(items):
        item_id = item.get("id", "?")
        errors = sorted(validator.iter_errors(item), key=lambda err: list(err.absolute_path))
        for err in errors:
            where = err.json_path or "$"
            messages.append(f"item[{index}] id={item_id} {where}: {err.message}")
    return messages
