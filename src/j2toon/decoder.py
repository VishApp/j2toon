"""TOON decoder that converts TOON text back into Python data structures."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Sequence, Tuple

from ._syntax import (
    NUMBER_RE,
    find_unquoted,
    is_quoted,
    split_unquoted,
    unquote,
)

_ARRAY_BRACKET_RE = re.compile(r"\[(\d+)(.)?\]")
_INT_RE = re.compile(r"[+-]?\d+")


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
        # Split only on "\n" so that quoted control characters (which
        # str.splitlines would otherwise treat as line boundaries) survive.
        for raw in text.split("\n"):
            line = raw.rstrip("\r")
            if not line.strip(" "):
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent % self.indent != 0:
                raise ValueError(f"Invalid indent: {raw!r}")
            level = indent // self.indent
            lines.append((level, line.strip(" ")))
        return lines

    def _parse_root(self) -> Tuple[Any, int]:
        # Root can be a bare scalar, a single array, or an object.
        level, content = self.lines[0]
        if self._line_starts_with_array(content):
            if self._has_colon(content):
                name, value, idx = self._parse_array_from_line(0)
                # If there are more root-level items, parse as object instead.
                if idx < len(self.lines) and self.lines[idx][0] == 0:
                    return self._parse_object(0, level=0)
                return value if name is None else {name: value}, idx
            if self._looks_like_array_header(content):
                raise ValueError(f"Array header missing ':' - {content!r}")
            return self._parse_scalar(content), 1
        if len(self.lines) == 1 and not self._has_colon(content):
            # A single unquoted token is a bare root scalar (e.g. ``42``,
            # ``true``, ``hello``, ``[a]``).  Multi-token lines without a
            # colon keep raising so malformed objects stay detectable.
            if is_quoted(content) or " " not in content:
                return self._parse_scalar(content), 1
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
            if not self._has_colon(content):
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
            value, idx = self._parse_object(idx + 1, level + 1)
            result[key] = value
        return result, idx

    def _parse_block(self, start: int, level: int) -> Tuple[Any, int]:
        _, content = self.lines[start]
        if self._line_starts_with_array(content):
            # A bare (unnamed) array header is a standalone array value; a
            # named header is the first field of an object, so parse the whole
            # object to keep its sibling keys.
            header = self._header_part(content).strip()
            if header.startswith("["):
                _, value, idx = self._parse_array_from_line(start)
                return value, idx
        return self._parse_object(start, level)

    def _parse_array_from_line(self, idx: int) -> Tuple[str | None, Any, int]:
        level, content = self.lines[idx]
        colon = find_unquoted(content, ":")
        if colon < 0:
            raise ValueError(f"Array header missing ':' - {content!r}")
        header = content[:colon].strip()
        remainder = content[colon + 1 :].strip()
        metadata = self._parse_array_header(header)
        value, next_idx = self._parse_array_body(
            metadata, remainder, idx + 1, level + 1
        )
        return metadata.name, value, next_idx

    def _parse_array_header(self, header: str):
        header = header.strip()
        open_idx = find_unquoted(header, "[")
        if open_idx < 0:
            raise ValueError(f"Invalid array header: {header!r}")
        name_part = header[:open_idx].strip()
        rest = header[open_idx:]
        match = _ARRAY_BRACKET_RE.match(rest)
        if not match:
            raise ValueError(f"Invalid array header: {header!r}")
        count = int(match.group(1))
        tail = rest[match.end() :].strip()
        field_list = None
        if tail.startswith("{"):
            end = find_unquoted(tail, "}")
            if end < 0:
                raise ValueError(f"Invalid array header: {header!r}")
            inner = tail[1:end]
            if inner == "":
                field_list = []
            else:
                try:
                    raw_fields = split_unquoted(
                        inner, self.delimiter, strict=True
                    )
                except ValueError:
                    raise ValueError(f"Invalid array header: {header!r}") from None
                field_list = [unquote(field.strip()) for field in raw_fields]
            tail = tail[end + 1 :].strip()
        if tail:
            raise ValueError(f"Invalid array header: {header!r}")
        name = unquote(name_part) if name_part else None
        return ArrayMeta(name, count, field_list)

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
            rows, idx = self._parse_tabular_rows(meta, start_idx, child_level)
            return rows, idx
        items, idx = self._parse_list_entries(meta.count, start_idx, child_level)
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
            # List entries can be at level (old format) or level+1 (new format
            # with the first key on the same line).
            if current_level == level and content.startswith("-"):
                entry, idx = self._parse_list_item(idx, level)
                items.append(entry)
                if expected and len(items) == expected:
                    break
            elif current_level > level:
                # Continuation of the previous entry (remaining keys); it
                # should already have been consumed by _parse_list_item.
                idx += 1
            else:
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

        # Check if remainder contains a key-value pair (has an unquoted ":")
        if self._has_colon(remainder):
            # New format: "- key: value" or "- key:"
            key, value_part = self._split_field(remainder)
            result: dict[str, Any] = {key: None}

            if value_part:
                # Scalar value on same line: "- key: value"
                result[key] = self._parse_scalar(value_part)
                idx = idx + 1
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
                    # Back at the dash level means this list item is finished.
                    if current_level == level and line_content.startswith("-"):
                        break
                    raise ValueError(
                        f"Unexpected indentation at line: {line_content!r}"
                    )

                if not self._has_colon(line_content):
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
                    next_idx = idx + 1
                    if (
                        next_idx >= len(self.lines)
                        or self.lines[next_idx][0] <= level + 1
                    ):
                        result[key] = {}
                        idx = next_idx
                        continue
                    nested_value, new_idx = self._parse_block(next_idx, level + 2)
                    result[key] = nested_value
                    idx = new_idx
            return result, idx

        # Scalar value on same line: "- value"
        return self._parse_scalar(remainder), idx + 1

    def _parse_row(self, text: str) -> List[Any]:
        try:
            cells = split_unquoted(text, self.delimiter, strict=True)
        except ValueError:
            raise ValueError("Unterminated quote in row") from None
        return [self._parse_scalar(cell.strip(" ")) for cell in cells]

    def _split_field(self, line: str) -> Tuple[str, str]:
        colon = find_unquoted(line, ":")
        if colon < 0:
            return unquote(line.strip()), ""
        key = unquote(line[:colon].strip())
        remainder = line[colon + 1 :].strip()
        return key, remainder

    def _header_part(self, content: str) -> str:
        colon = find_unquoted(content, ":")
        return content[:colon] if colon >= 0 else content

    def _has_colon(self, content: str) -> bool:
        return find_unquoted(content, ":") >= 0

    def _line_represents_array_value(self, content: str) -> bool:
        return find_unquoted(self._header_part(content), "[") >= 0

    def _line_starts_with_array(self, content: str) -> bool:
        return find_unquoted(self._header_part(content), "[") >= 0

    def _looks_like_array_header(self, content: str) -> bool:
        open_idx = find_unquoted(content, "[")
        if open_idx < 0:
            return False
        return _ARRAY_BRACKET_RE.match(content[open_idx:]) is not None

    def _parse_scalar(self, token: str) -> Any:
        if not token:
            return ""
        if is_quoted(token):
            return unquote(token)
        lowered = token.lower()
        if lowered == "null":
            return None
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if _INT_RE.fullmatch(token):
            return int(token)
        if NUMBER_RE.fullmatch(token):
            return float(token)
        return token


@dataclass
class ArrayMeta:
    name: str | None
    count: int
    fields: Sequence[str] | None
