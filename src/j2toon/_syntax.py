"""Shared tokenisation helpers for the TOON encoder and decoder.

Both directions must agree on exactly which strings need quoting and how
escapes are produced/consumed.  Keeping those rules in one module avoids the
encoder and decoder drifting apart (which previously caused quoted values,
object keys, and backslash escapes to round-trip incorrectly).
"""

from __future__ import annotations

import re

#: Scalars that would be decoded as a bool/null rather than a string.
RESERVED_SCALARS = frozenset({"true", "false", "null"})

#: Matches any JSON-style number, including exponents (``2e-05``, ``1e+16``).
NUMBER_RE = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")

#: Characters that change TOON structure regardless of the active delimiter.
_STRUCTURAL = frozenset({'"', "\\", "\n", "\r", "\t", ":", "[", "]", "{", "}", " "})


def looks_like_scalar(value: str) -> bool:
    """Return ``True`` when *value* would decode as a non-string scalar."""
    if value.lower() in RESERVED_SCALARS:
        return True
    return NUMBER_RE.fullmatch(value) is not None


def escape_string(value: str) -> str:
    """Escape a string for use inside double quotes (TOON/JSON style)."""
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def unescape_string(text: str) -> str:
    """Reverse :func:`escape_string` while preserving literal backslashes."""
    escapes = {"n": "\n", "r": "\r", "t": "\t", '"': '"', "\\": "\\"}
    result: list[str] = []
    i = 0
    length = len(text)
    while i < length:
        char = text[i]
        if char == "\\" and i + 1 < length and text[i + 1] in escapes:
            result.append(escapes[text[i + 1]])
            i += 2
            continue
        result.append(char)
        i += 1
    return "".join(result)


def format_string(value: str, delimiter: str) -> str:
    """Return the TOON token for a string value, quoting when required."""
    if not _needs_quote(value, delimiter):
        return value
    return '"' + escape_string(value) + '"'


def _has_control(value: str) -> bool:
    return any(ord(ch) < 0x20 for ch in value)


def _needs_quote(value: str, delimiter: str) -> bool:
    if value == "":
        return True
    if value.strip() != value:
        return True
    if looks_like_scalar(value):
        return True
    if delimiter in value or any(ch in _STRUCTURAL for ch in value):
        return True
    if _has_control(value):
        return True
    if value.startswith("- "):
        return True
    return False


def format_key(key: str, delimiter: str) -> str:
    """Return the TOON token for an object key or table field name."""
    if key == "":
        return '""'
    if key.strip() != key:
        return '"' + escape_string(key) + '"'
    if key.startswith("-"):
        return '"' + escape_string(key) + '"'
    if delimiter in key or any(ch in _STRUCTURAL for ch in key) or _has_control(key):
        return '"' + escape_string(key) + '"'
    return key


def is_quoted(token: str) -> bool:
    return len(token) >= 2 and token[0] == '"' and token[-1] == '"'


def unquote(token: str) -> str:
    """Decode a token, unescaping it when it is double quoted."""
    if is_quoted(token):
        return unescape_string(token[1:-1])
    return token


def find_unquoted(text: str, char: str) -> int:
    """Index of the first *char* outside quotes, or ``-1``."""
    in_quotes = False
    i = 0
    length = len(text)
    while i < length:
        current = text[i]
        if in_quotes:
            if current == "\\":
                i += 2
                continue
            if current == '"':
                in_quotes = False
        elif current == '"':
            in_quotes = True
        elif current == char:
            return i
        i += 1
    return -1


def split_unquoted(text: str, separator: str, *, strict: bool = False) -> list[str]:
    """Split *text* on *separator* while respecting quoted regions.

    When *strict* is true an unterminated double quote raises ``ValueError``
    instead of silently treating the remainder as quoted text.
    """
    parts: list[str] = []
    current: list[str] = []
    in_quotes = False
    i = 0
    length = len(text)
    while i < length:
        char = text[i]
        if in_quotes:
            current.append(char)
            if char == "\\" and i + 1 < length:
                current.append(text[i + 1])
                i += 2
                continue
            if char == '"':
                in_quotes = False
        elif char == '"':
            in_quotes = True
            current.append(char)
        elif char == separator:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
        i += 1
    if in_quotes and strict:
        raise ValueError("Unterminated quote")
    parts.append("".join(current))
    return parts
