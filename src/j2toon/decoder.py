"""TOON decoder that converts TOON text back into Python data structures."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Sequence, Tuple

ARRAY_HEADER_RE = re.compile(
    r"^(?:(?P<name>[^[]+))?\[(?P<count>\d+)(?P<delimiter_hint>.)?\]"
    r"(?:\{(?P<fields>[^}]*)\})?$"
)


def decode(text: str, *, indent: int = 2, delimiter: str = ",") -> Any:
    """Parse TOON-formatted text into Python values."""
    return Decoder(indent=indent, delimiter=delimiter).decode(text)


@dataclass
class Decoder:
    indent: int = 2
    delimiter: str = ","

    def __post_init__(self) -> None:
        if self.indent <= 0:
            raise ValueError("indent must be a positive integer")
        if len(self.delimiter) != 1:
            raise ValueError("delimiter must be a single character")

    def decode(self, text: str) -> Any:
        self.lines = self._preprocess(text)
        if not self.lines:
            return {}
        value, idx = self._parse_root()
        if idx != len(self.lines):
            raise ValueError("Unexpected trailing content while decoding TOON")
        return value

    # ---- parsing helpers -------------------------------------------------
    def _preprocess(self, text: str) -> List[Tuple[int, str]]:
        lines: List[Tuple[int, str]] = []
        for raw in text.splitlines():
            if not raw.strip():
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            if indent % self.indent != 0:
                raise ValueError(f"Invalid indent: {raw!r}")
            level = indent // self.indent
            lines.append((level, raw.strip()))
        return lines

    def _parse_root(self) -> Tuple[Any, int]:
        # Root can be a single array or an object with multiple keys
        # If first line is an array, check if there are more root-level items
        level, content = self.lines[0]
        if self._line_starts_with_array(content):
            name, value, idx = self._parse_array_from_line(0)
            # If there are more root-level items, parse as object instead
            if idx < len(self.lines) and self.lines[idx][0] == 0:
                # Multiple root items - parse as object
                return self._parse_object(0, level=0)
            return value if name is None else {name: value}, idx
        value, idx = self._parse_object(0, level=0)
        return value, idx

    def _parse_object(self, start: int, level: int) -> Tuple[dict, int]:
        result: dict[str, Any] = {}
        idx = start
        while idx < len(self.lines):
            current_level, content = self.lines[idx]
            if current_level < level:
                break
            if current_level > level:
                raise ValueError(f"Unexpected indentation at line: {content!r}")
            if self._line_represents_array_value(content):
                name, value, idx = self._parse_array_from_line(idx)
                if name is None:
                    raise ValueError("Unnamed array encountered inside object")
                result[name] = value
                continue
            if ":" not in content:
                raise ValueError(f"Missing ':' in object entry: {content!r}")
            key, remainder = self._split_field(content)
            if remainder:
                result[key] = self._parse_scalar(remainder)
                idx += 1
                continue
            if idx + 1 >= len(self.lines) or self.lines[idx + 1][0] <= level:
                result[key] = {}
                idx += 1
                continue
            # Parse nested object directly (not using _parse_block which only handles single values)
            value, idx = self._parse_object(idx + 1, level + 1)
            result[key] = value
        return result, idx

    def _parse_block(self, start: int, level: int) -> Tuple[Any, int]:
        _, content = self.lines[start]
        if self._line_starts_with_array(content):
            name, value, idx = self._parse_array_from_line(start)
            return value if name is None else {name: value}, idx
        return self._parse_object(start, level)

    def _parse_array_from_line(self, idx: int) -> Tuple[str | None, Any, int]:
        level, content = self.lines[idx]
        if ":" not in content:
            raise ValueError(f"Array header missing ':' - {content!r}")
        header, remainder = self._split_field(content)
        metadata = self._parse_array_header(header)
        value, next_idx = self._parse_array_body(
            metadata, remainder, idx + 1, level + 1
        )
        return metadata.name, value, next_idx

    def _parse_array_header(self, header: str):
        match = ARRAY_HEADER_RE.match(header)
        if not match:
            raise ValueError(f"Invalid array header: {header!r}")
        name = match.group("name")
        count = int(match.group("count"))
        fields = match.group("fields")
        field_list = None
        if fields is not None:
            if not fields:
                field_list = []
            else:
                field_list = [f.strip() for f in fields.split(self.delimiter)]
        return ArrayMeta(name.strip() if name else None, count, field_list)

    def _parse_array_body(
        self,
        meta: "ArrayMeta",
        inline: str,
        start_idx: int,
        child_level: int,
    ) -> Tuple[Any, int]:
        if inline:
            values = self._parse_row(inline)
            if len(values) != meta.count:
                raise ValueError("Inline array length mismatch")
            return values, start_idx
        if meta.fields is not None:
            rows, idx = self._parse_tabular_rows(
                meta, start_idx, child_level
            )
            return rows, idx
        items, idx = self._parse_list_entries(
            meta.count, start_idx, child_level
        )
        return items, idx

    def _parse_tabular_rows(
        self, meta: "ArrayMeta", start_idx: int, level: int
    ) -> Tuple[List[dict], int]:
        rows: List[dict] = []
        idx = start_idx
        while len(rows) < meta.count and idx < len(self.lines):
            current_level, content = self.lines[idx]
            if current_level < level:
                break
            if current_level != level:
                raise ValueError("Invalid indentation inside tabular array")
            values = self._parse_row(content)
            if len(values) != len(meta.fields):
                raise ValueError("Tabular row column mismatch")
            rows.append(dict(zip(meta.fields, values)))
            idx += 1
        if len(rows) != meta.count:
            raise ValueError("Tabular array row count mismatch")
        return rows, idx

    def _parse_list_entries(
        self, expected: int, start_idx: int, level: int
    ) -> Tuple[List[Any], int]:
        items: List[Any] = []
        idx = start_idx
        while idx < len(self.lines):
            current_level, content = self.lines[idx]
            if current_level < level:
                break
            # List entries can be at level (old format) or level+1 (new format with first key on same line)
            # But we only start a new entry if we see a dash at the expected level
            if current_level == level and content.startswith("-"):
                entry, idx = self._parse_list_item(idx, level)
                items.append(entry)
                if expected and len(items) == expected:
                    break
            elif current_level > level:
                # This might be a continuation of the previous entry (remaining keys)
                # Skip it - it should have been consumed by _parse_list_item
                idx += 1
            else:
                # Unexpected format
                break
        if expected != 0 and len(items) != expected:
            raise ValueError("List entry count mismatch")
        return items, idx

    def _parse_list_item(self, idx: int, level: int) -> Tuple[Any, int]:
        _, content = self.lines[idx]
        remainder = content[1:].strip()
        if not remainder:
            # Old format: just "-" on its own line
            next_idx = idx + 1
            if next_idx >= len(self.lines) or self.lines[next_idx][0] <= level:
                return {}, next_idx
            value, new_idx = self._parse_block(next_idx, level + 1)
            return value, new_idx
        
        # Check if remainder contains a key-value pair (has ":")
        if ":" in remainder:
            # New format: "- key: value" or "- key:"
            key, value_part = self._split_field(remainder)
            result: dict[str, Any] = {key: None}
            
            if value_part:
                # Scalar value on same line: "- key: value"
                result[key] = self._parse_scalar(value_part)
                idx = idx + 1  # Move to next line
            else:
                # Nested value: "- key:" followed by block
                next_idx = idx + 1
                if next_idx >= len(self.lines) or self.lines[next_idx][0] <= level:
                    result[key] = {}
                    idx = next_idx
                else:
                    # Parse the nested value at level + 1
                    nested_value, new_idx = self._parse_block(next_idx, level + 1)
                    result[key] = nested_value
                    idx = new_idx
            
            # Parse remaining keys at level + 1 (they align with the value part)
            while idx < len(self.lines):
                current_level, line_content = self.lines[idx]
                if current_level < level:
                    break
                if current_level != level + 1:
                    # If we're back at the dash level, we've finished this list item
                    if current_level == level and line_content.startswith("-"):
                        break
                    # Otherwise it's an error
                    raise ValueError(f"Unexpected indentation at line: {line_content!r}")
                
                # Parse this key-value pair
                if ":" not in line_content:
                    break
                
                # Check if this line is an array header first
                if self._line_represents_array_value(line_content):
                    name, value, new_idx = self._parse_array_from_line(idx)
                    if name is None:
                        raise ValueError("Unnamed array encountered in list item")
                    result[name] = value
                    idx = new_idx
                    continue
                
                # Otherwise, treat it as a regular key-value pair
                key, value_part = self._split_field(line_content)
                if value_part:
                    result[key] = self._parse_scalar(value_part)
                    idx += 1
                else:
                    # Nested object or other value
                    next_idx = idx + 1
                    if next_idx >= len(self.lines) or self.lines[next_idx][0] <= level + 1:
                        result[key] = {}
                        idx = next_idx
                        continue
                    nested_value, new_idx = self._parse_block(next_idx, level + 2)
                    result[key] = nested_value
                    idx = new_idx
            return result, idx
        else:
            # Scalar value on same line: "- value"
            return self._parse_scalar(remainder), idx + 1

    def _parse_row(self, text: str) -> List[Any]:
        cells: List[str] = []
        current: List[str] = []
        in_quotes = False
        escape = False
        for char in text:
            if escape:
                current.append(char)
                escape = False
                continue
            if char == "\\" and in_quotes:
                escape = True
                continue
            if char == '"':
                in_quotes = not in_quotes
                current.append(char)
                continue
            if not in_quotes and char == self.delimiter:
                cells.append("".join(current).strip())
                current = []
                continue
            current.append(char)
        cells.append("".join(current).strip())
        if in_quotes:
            raise ValueError("Unterminated quote in row")
        return [self._parse_scalar(cell) for cell in cells if cell != "" or cell == '""']

    def _split_field(self, line: str) -> Tuple[str, str]:
        key, remainder = line.split(":", 1)
        return key.strip(), remainder.strip()

    def _line_header(self, content: str) -> str:
        return content.split(":", 1)[0].strip()

    def _line_represents_array_value(self, content: str) -> bool:
        header = self._line_header(content)
        return "[" in header

    def _line_starts_with_array(self, content: str) -> bool:
        header = self._line_header(content)
        return "[" in header

    def _parse_scalar(self, token: str) -> Any:
        if not token:
            return ""
        if token.startswith('"') and token.endswith('"'):
            stripped = token[1:-1]
            # Unescape: process \\\\ first to avoid interfering with other escapes
            # Use a temporary marker for double backslashes
            result = stripped.replace("\\\\", "\x00")
            # Now unescape single escape sequences
            result = (
                result.replace("\\n", "\n")
                .replace("\\r", "\r")
                .replace("\\t", "\t")
                .replace('\\"', '"')
            )
            # Restore actual backslashes
            return result.replace("\x00", "\\")
        lowered = token.lower()
        if lowered == "null":
            return None
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if self._is_int(token):
            return int(token)
        if self._is_float(token):
            return float(token)
        return token

    def _is_int(self, token: str) -> bool:
        return re.fullmatch(r"[+-]?\d+", token) is not None

    def _is_float(self, token: str) -> bool:
        return re.fullmatch(r"[+-]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?", token) is not None


@dataclass
class ArrayMeta:
    name: str | None
    count: int
    fields: Sequence[str] | None
