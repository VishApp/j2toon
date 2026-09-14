"""Conversion utilities for emitting TOON from Python data structures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Mapping, Sequence

from ._syntax import format_key, format_string


#: Supported encoding modes for :func:`encode`.
VALID_MODES = ("auto", "table", "nested")


def encode(
    value: Any, *, indent: int = 2, delimiter: str = ",", mode: str = "auto"
) -> str:
    """Convert a JSON-compatible Python value into TOON.

    ``mode`` selects how arrays of objects are rendered:

    * ``"auto"`` (default) – use a table when the items share the same scalar
      fields, otherwise fall back to nested list entries.
    * ``"table"`` – always use a table for arrays of objects; raise
      :class:`ValueError` when an array of objects cannot be represented as a
      table (mixed fields or non-scalar values).
    * ``"nested"`` – never use tables; always emit nested list entries.
    """
    return Encoder(indent=indent, delimiter=delimiter, mode=mode).encode(value)


@dataclass
class Encoder:
    """Stateful encoder that emits TOON text."""

    indent: int = 2
    delimiter: str = ","
    mode: str = "auto"

    def __post_init__(self) -> None:
        if self.indent <= 0:
            raise ValueError("indent must be a positive integer")
        if len(self.delimiter) != 1:
            raise ValueError("delimiter must be a single character")
        if self.mode not in VALID_MODES:
            raise ValueError(
                "mode must be one of: " + ", ".join(VALID_MODES)
            )

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

    def _key(self, name: str) -> str:
        return format_key(name, self.delimiter)

    def _encode_object(
        self, obj: Mapping[str, Any], level: int, name: str | None
    ) -> List[str]:
        lines: List[str] = []
        base_level = level
        if name is not None:
            lines.append(f"{self._indent(level)}{self._key(name)}:")
            base_level += 1
        if not obj:
            return lines
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

        if self.mode != "nested":
            tabular_fields = self._tabular_fields(seq)
            if tabular_fields:
                header_fields = self.delimiter.join(
                    self._key(field) for field in tabular_fields
                )
                header = f"{label}{{{header_fields}}}:"
                lines.append(f"{indent}{header}")
                for row in seq:
                    row_values = [
                        self._format_scalar(row[field]) for field in tabular_fields
                    ]
                    lines.append(
                        f"{self._indent(level + 1)}{self._join_row(row_values)}"
                    )
                return lines
            if self.mode == "table" and self._expects_table(seq):
                raise ValueError(
                    "mode='table' cannot represent array "
                    f"{name or '<root>'!r} as a table because its items do not "
                    "share the same scalar fields; use mode='auto' or "
                    "mode='nested' instead"
                )

        lines.append(f"{indent}{label}:")
        for item in seq:
            lines.extend(self._encode_list_entry(item, level + 1))
        return lines

    def _encode_list_entry(self, value: Any, level: int) -> List[str]:
        indent = self._indent(level)
        if self._is_scalar(value):
            return [f"{indent}- {self._format_scalar(value)}"]
        # Records whose first value is scalar keep the compact "- key: value"
        # form so saved output stays unchanged.
        if isinstance(value, Mapping) and value:
            items = list(value.items())
            first_key, first_value = items[0]
            if self._is_scalar(first_value):
                lines = [
                    f"{indent}- {self._key(first_key)}: "
                    f"{self._format_scalar(first_value)}"
                ]
                # Remaining keys align with the value part of the first key
                # (level + 1).
                for key, val in items[1:]:
                    lines.extend(self._encode_value(val, level + 1, name=key))
                return lines
        # Any other non-scalar (a record whose first value is non-scalar, or a
        # bare nested value) uses a standalone dash followed by a normal object
        # block, which never absorbs sibling keys.
        lines = [f"{indent}-"]
        lines.extend(self._encode_value(value, level + 1, name=None))
        return lines

    def _encode_scalar(self, value: Any, level: int, name: str | None) -> List[str]:
        formatted = self._format_scalar(value)
        indent = self._indent(level)
        if name is None:
            return [f"{indent}{formatted}"]
        return [f"{indent}{self._key(name)}: {formatted}"]

    def _format_scalar(self, value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return repr(value)
        if isinstance(value, str):
            return format_string(value, self.delimiter)
        raise TypeError(f"Unsupported value type: {type(value)!r}")

    def _array_label(self, name: str | None, length: int) -> str:
        if name is not None:
            return f"{self._key(name)}[{length}]"
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
        expected = set(first_fields)
        for item in seq:
            if set(item.keys()) != expected:
                return None
            if not all(self._is_scalar(item[field]) for field in first_fields):
                return None
        return first_fields

    def _expects_table(self, seq: Sequence[Any]) -> bool:
        """Whether ``seq`` looks like records that the caller expects as a table."""
        return bool(seq) and all(isinstance(item, Mapping) for item in seq)

    def _is_scalar(self, value: Any) -> bool:
        return isinstance(value, (str, int, float, bool)) or value is None

    def _join_row(self, values: Iterable[str]) -> str:
        return self.delimiter.join(values)

    def _indent(self, level: int) -> str:
        return " " * (self.indent * level)
