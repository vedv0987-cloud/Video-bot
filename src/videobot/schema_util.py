"""JSON Schema loading and error formatting."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

import jsonschema


@lru_cache(maxsize=None)
def load_schema(name: str) -> dict[str, Any]:
    """Load a bundled schema by stem, e.g. `scene-spec`."""
    text = resources.files("videobot.schema").joinpath(f"{name}.schema.json").read_text("utf-8")
    return json.loads(text)


def schema_errors(instance: Any, schema: dict[str, Any]) -> list[str]:
    """All schema violations, deepest path first, as readable strings.

    Returning every error rather than raising on the first keeps the feedback
    loop short when a spec is wrong in several places.
    """
    validator = jsonschema.Draft202012Validator(schema)
    messages = []
    for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path)):
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        messages.append(f"{location}: {error.message}")
    return messages
