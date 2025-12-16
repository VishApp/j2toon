"""Conversion utilities for emitting TOON from Python data structures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Mapping, Sequence


def encode(value: Any, *, indent: int = 2, delimiter: str = ",") -> str:
    """Convert a JSON-compatible Python value into TOON."""
    return Encoder(indent=indent, delimiter=delimiter).encode(value)


@dataclass
class Encoder:
    """Stateful encoder that emits TOON text."""

    indent: int = 2
    delimiter: str = ","

    def __post_init__(self) -> None:
        if self.indent <= 0:
            raise ValueError("indent must be a positive integer")
        if len(self.delimiter) != 1:
            raise ValueError("delimiter must be a single character")
        # Cache common indent strings for performance (up to level 20)
        self._indent_cache: dict[int, str] = {}
        # Precompute special characters set for string formatting
        self._special_chars = set('\t\r\n"')
        self._special_chars.add(self.delimiter)

    def encode(self, value: Any) -> str:
        lines = self._encode_value(value, level=0, name=None)
        return "\n".join(lines).rstrip()

    # ---- private helpers -------------------------------------------------
    def _encode_value(self, value: Any, level: int, name: str | None) -> List[str]:
        if isinstance(value, Mapping):
            return self._encode_object(value, level, name)
        if isinstance(value, (list, tuple)):
            return self._encode_array(list(value), level, name)
        return self._encode_scalar(value, level, name)

    def _encode_object(
        self, obj: Mapping[str, Any], level: int, name: str | None
    ) -> List[str]:
        lines: List[str] = []
        base_level = level
        if name is not None:
            lines.append(f"{self._indent(level)}{name}:")
            base_level += 1
        if not obj:
            return lines or [f"{self._indent(level)}{name}:" ] if name else lines
        # Pre-allocate list capacity estimate for better performance
        for key, val in obj.items():
            lines.extend(self._encode_value(val, base_level, name=key))
        return lines

    def _encode_array(
        self, seq: Sequence[Any], level: int, name: str | None
    ) -> List[str]:
        lines: List[str] = []
        seq_len = len(seq)
        label = self._array_label(name, seq_len)
        indent = self._indent(level)

        if self._can_inline_primitive_array(seq):
            body = self._join_row(self._format_scalar(v) for v in seq)
            suffix = f" {body}" if body else ""
            lines.append(f"{indent}{label}:{suffix}")
            return lines

        tabular_fields = self._tabular_fields(seq)
        if tabular_fields:
            header = f"{label}{{{self.delimiter.join(tabular_fields)}}}:"
            lines.append(f"{indent}{header}")
            row_indent = self._indent(level + 1)
            for row in seq:
                row_values = [self._format_scalar(row[field]) for field in tabular_fields]
                lines.append(f"{row_indent}{self._join_row(row_values)}")
            return lines

        lines.append(f"{indent}{label}:")
        for item in seq:
            lines.extend(self._encode_list_entry(item, level + 1))
        return lines

    def _encode_list_entry(self, value: Any, level: int) -> List[str]:
        indent = self._indent(level)
        if self._is_scalar(value):
            return [f"{indent}- {self._format_scalar(value)}"]
        # For objects, put the first key on the same line as the dash
        if isinstance(value, Mapping) and value:
            items_iter = iter(value.items())
            first_key, first_value = next(items_iter)
            # Build remaining dict more efficiently
            remaining = dict(items_iter)
            lines = []
            # Encode first key-value pair on the same line as the dash
            if self._is_scalar(first_value):
                lines.append(f"{indent}- {first_key}: {self._format_scalar(first_value)}")
            else:
                lines.append(f"{indent}- {first_key}:")
                lines.extend(self._encode_value(first_value, level + 1, name=None))
            # Encode remaining key-value pairs - they should be indented to align
            # with the value part of the first key (level + 1)
            for key, val in remaining.items():
                lines.extend(self._encode_value(val, level + 1, name=key))
            return lines
        # For non-object, non-scalar values (like arrays), use the old format
        lines = [f"{indent}-"]
        lines.extend(self._encode_value(value, level + 1, name=None))
        return lines

    def _encode_scalar(self, value: Any, level: int, name: str | None) -> List[str]:
        formatted = self._format_scalar(value)
        indent = self._indent(level)
        if name is None:
            return [f"{indent}{formatted}"]
        return [f"{indent}{name}: {formatted}"]

    def _format_scalar(self, value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return repr(value)
        if isinstance(value, str):
            return self._format_string(value)
        raise TypeError(f"Unsupported value type: {type(value)!r}")

    def _format_string(self, value: str) -> str:
        if value == "":
            return '""'
        # Optimize: single strip() call and reuse result
        stripped = value.strip()
        stripped_len = len(stripped)
        # Check if string is purely numeric (to distinguish from actual numbers)
        is_numeric = (
            stripped_len > 0
            and stripped.replace(".", "", 1).replace("-", "", 1).isdigit()
        )
        # Fast path: check common cases first
        needs_quote = (
            stripped_len != len(value)  # Has leading/trailing whitespace
            or value.startswith("- ")  # Starts with dash-space
            or ":" in value  # Contains colon
            or is_numeric  # Looks numeric
            or any(ch in self._special_chars for ch in value)  # Has special chars
        )
        if needs_quote:
            # Optimize escaping: build string efficiently
            # Use list join instead of multiple replace operations
            result_chars = []
            for char in value:
                if char == "\\":
                    result_chars.append("\\\\")
                elif char == '"':
                    result_chars.append('\\"')
                elif char == "\n":
                    result_chars.append("\\n")
                elif char == "\r":
                    result_chars.append("\\r")
                elif char == "\t":
                    result_chars.append("\\t")
                else:
                    result_chars.append(char)
            return f'"{"".join(result_chars)}"'
        return value

    def _array_label(self, name: str | None, length: int) -> str:
        if name:
            return f"{name}[{length}]"
        return f"[{length}]"

    def _can_inline_primitive_array(self, seq: Sequence[Any]) -> bool:
        return bool(seq) and all(self._is_scalar(item) for item in seq)

    def _tabular_fields(self, seq: Sequence[Any]) -> List[str] | None:
        if not seq:
            return None
        first_item = seq[0]
        if not isinstance(first_item, Mapping):
            return None
        first_fields = list(first_item.keys())
        if not first_fields:
            return None
        # Convert to tuple for faster comparison
        first_fields_tuple = tuple(first_fields)
        # Check remaining items more efficiently
        for item in seq[1:]:
            if not isinstance(item, Mapping):
                return None
            # Fast path: check keys match first
            if tuple(item.keys()) != first_fields_tuple:
                return None
            # Then check all values are scalar
            if not all(self._is_scalar(item[field]) for field in first_fields):
                return None
        return first_fields

    def _is_scalar(self, value: Any) -> bool:
        return isinstance(value, (str, int, float, bool)) or value is None

    def _join_row(self, values: Iterable[str]) -> str:
        return self.delimiter.join(values)

    def _indent(self, level: int) -> str:
        # Cache common indent levels for performance
        if level in self._indent_cache:
            return self._indent_cache[level]
        indent_str = " " * (self.indent * level)
        # Cache up to level 20 to avoid unbounded memory growth
        if level <= 20:
            self._indent_cache[level] = indent_str
        return indent_str
