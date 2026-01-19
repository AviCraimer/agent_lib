"""Tests for json_utils module."""

from __future__ import annotations

import pytest

from agent_lib.util.json_utils import JSONSchema


class TestJSONSchema:
    """Tests for JSONSchema class."""

    def test_valid_empty_schema(self) -> None:
        """Empty dict is a valid JSON schema."""
        schema = JSONSchema({})
        assert schema == {}

    def test_valid_object_schema(self) -> None:
        """Standard object schema is valid."""
        schema = JSONSchema({
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
        })
        assert schema["type"] == "object"

    def test_valid_array_schema(self) -> None:
        """Array schema is valid."""
        schema = JSONSchema({
            "type": "array",
            "items": {"type": "string"},
        })
        assert schema["type"] == "array"

    def test_invalid_type_raises(self) -> None:
        """Invalid type value raises TypeError."""
        with pytest.raises(TypeError, match="Invalid JSON Schema"):
            JSONSchema({"type": "not-a-real-type"})

    def test_non_dict_raises(self) -> None:
        """Non-dict input raises TypeError."""
        with pytest.raises(TypeError, match="must be a dict"):
            JSONSchema("not a dict")  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="must be a dict"):
            JSONSchema(["a", "list"])  # type: ignore[arg-type]

    def test_invalid_property_schema_raises(self) -> None:
        """Invalid nested schema raises TypeError."""
        with pytest.raises(TypeError, match="Invalid JSON Schema"):
            JSONSchema({
                "type": "object",
                "properties": {
                    "name": {"type": "invalid-type"},
                },
            })

    def test_schema_is_dict_subclass(self) -> None:
        """JSONSchema instances are dict subclasses."""
        schema = JSONSchema({"type": "string"})
        assert isinstance(schema, dict)

    def test_schema_supports_deepcopy(self) -> None:
        """JSONSchema can be deepcopied."""
        import copy

        original = JSONSchema({
            "type": "object",
            "properties": {"name": {"type": "string"}},
        })
        copied = copy.deepcopy(original)

        assert copied == original
        assert copied is not original
        assert isinstance(copied, JSONSchema)
