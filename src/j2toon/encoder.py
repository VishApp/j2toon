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
        for key, val in obj.items():
            lines.extend(self._encode_value(val, base_level, name=key))
        return lines

    def _encode_array(
        self, seq: Sequence[Any], level: int, name: str | None
    ) -> List[str]:
        lines: List[str] = []
        label = self._array_label(name, len(seq))
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
            for row in seq:
                row_values = [self._format_scalar(row[field]) for field in tabular_fields]
                lines.append(
                    f"{self._indent(level + 1)}{self._join_row(row_values)}"
                )
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
            first_key = next(iter(value.keys()))
            first_value = value[first_key]
            remaining = {k: v for k, v in value.items() if k != first_key}
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
        special = set('\t\r\n"')
        special.add(self.delimiter)
        # Check if string is purely numeric (to distinguish from actual numbers)
        is_numeric = value.strip() and value.strip().replace(".", "", 1).replace("-", "", 1).isdigit()
        needs_quote = (
            value.strip() != value
            or any(ch in special for ch in value)
            or ":" in value
            or value.startswith("- ")
            or is_numeric
        )
        if needs_quote:
            # Escape backslashes first, then quotes, then control characters
            escaped = (
                value.replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t")
            )
            return f'"{escaped}"'
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
        if not all(isinstance(item, Mapping) for item in seq):
            return None
        first_fields = list(seq[0].keys())
        if not first_fields:
            return None
        for item in seq:
            if list(item.keys()) != first_fields:
                return None
            if not all(self._is_scalar(item[field]) for field in first_fields):
                return None
        return first_fields

    def _is_scalar(self, value: Any) -> bool:
        return isinstance(value, (str, int, float, bool)) or value is None

    def _join_row(self, values: Iterable[str]) -> str:
        return self.delimiter.join(values)

    def _indent(self, level: int) -> str:
        return " " * (self.indent * level)
