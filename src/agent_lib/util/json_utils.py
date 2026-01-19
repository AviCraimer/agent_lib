from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Any, TypeGuard

import jsonschema


type JSONPyPrimitive = str | int | float | bool | None
"""Python primitives that convert to JSON without special treatment."""

type JSONPyDict = dict[str, JSONPyValue]

type JSONPyList = list[JSONPyValue]

type JSONPyValue = JSONPyPrimitive | JSONPyDict | JSONPyList


def _is_py_json(val: Any) -> bool:
    """Check if a value is JSON-compatible (internal helper)."""
    if val is None or isinstance(val, (str, int, float, bool)):
        return True
    if isinstance(val, dict):
        return all(isinstance(k, str) and _is_py_json(v) for k, v in val.items())
    if isinstance(val, list):
        return all(_is_py_json(item) for item in val)
    return False


class JSONSchema(dict[str, JSONPyValue]):
    """A validated JSON Schema dictionary.

    Validates against the JSON Schema meta-schema to ensure the schema is well-formed.
    """

    def __new__(cls, data: Any) -> JSONSchema:
        if not isinstance(data, dict):
            raise TypeError("JSONSchema must be a dict")
        try:
            jsonschema.Draft202012Validator.check_schema(data)
        except jsonschema.SchemaError as e:
            raise TypeError(f"Invalid JSON Schema: {e.message}") from e
        return super().__new__(cls, data)

    def __reduce__(self) -> tuple[type[JSONSchema], tuple[dict[str, Any]]]:
        """Support pickling and deepcopy."""
        return (JSONSchema, (dict(self),))


class json:
    """Typed wrapper around the standard json module."""

    JSONPyPrimitive = JSONPyPrimitive
    JSONPyValue = JSONPyValue
    JSONDecodeError = _json.JSONDecodeError

    @staticmethod
    def load(path: str | Path) -> dict[str, Any]:
        """Load JSON from a file path.

        Args:
            path: Path to the JSON file (string or Path object)

        Returns:
            The parsed JSON as a dictionary
        """
        return _json.loads(Path(path).read_text())

    @staticmethod
    def to_string(json_val: JSONPyValue) -> str:
        """Convert a Python value to a JSON string.

        Args:
            json_val: A JSON-compatible Python value

        Returns:
            The JSON string representation
        """
        return _json.dumps(json_val)

    @staticmethod
    def parse(json_str: str) -> JSONPyValue:
        """Parse a JSON string into a Python value.

        Args:
            json_str: A valid JSON string

        Returns:
            The parsed Python value
        """
        return _json.loads(json_str)  # type: ignore[return-value]

    @staticmethod
    def is_py_json(val: Any) -> TypeGuard[JSONPyValue]:
        """Check if a value is a valid JSON-compatible Python value.

        Args:
            val: Any Python value

        Returns:
            True if the value can be serialized to JSON
        """
        return _is_py_json(val)

    @staticmethod
    def load_schema(path: str | Path) -> JSONSchema:
        """Load a JSON schema from a file path.

        Args:
            path: Path to the JSON schema file (string or Path object)

        Returns:
            The parsed JSON schema

        Raises:
            TypeError: If the file does not contain a valid JSON schema (dict)
        """
        data = _json.loads(Path(path).read_text())
        return JSONSchema(data)
