"""Regression tests for encoding/decoding edge cases.

These cover the families that previously round-tripped incorrectly:
reserved/numeric-looking strings, exponent numbers, escape preservation in
rows/inline arrays, arbitrary object keys, root scalars, control characters,
and tabular arrays whose rows list the same keys in a different order.
"""

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

from j2toon import json2toon, toon2json

DELIMITERS = [",", "\t", "|"]

_REPO_SRC = Path(__file__).resolve().parents[1] / "src"

SPECIAL_KEYS = [
    "",
    "a b",
    " a ",
    "a,b",
    "a:b",
    "a[0]",
    "a{b}",
    'q"r',
    "a\nb",
    "a\tb",
    "a\\b",
    "caf\u00e9",
    "\U0001f600",
    "123",
    "true",
    "- x",
]


def assert_same_value(actual, expected, path="$"):
    """Recursive equality that also compares runtime types.

    Plain ``==`` treats ``True == 1`` and ``1 == 1.0`` as equal, which would
    hide bool/int/float/string confusion introduced by the codec.
    """
    assert type(actual) is type(expected), (
        f"{path}: type {type(actual).__name__} != {type(expected).__name__} "
        f"({actual!r} vs {expected!r})"
    )
    if isinstance(expected, dict):
        assert set(actual) == set(expected), f"{path}: keys {set(actual)} != {set(expected)}"
        for key in expected:
            assert_same_value(actual[key], expected[key], f"{path}[{key!r}]")
    elif isinstance(expected, list):
        assert len(actual) == len(expected), f"{path}: length {len(actual)} != {len(expected)}"
        for i, (a, e) in enumerate(zip(actual, expected)):
            assert_same_value(a, e, f"{path}[{i}]")
    else:
        assert actual == expected, f"{path}: {actual!r} != {expected!r}"
        if isinstance(expected, float) and expected == 0.0:
            assert math.copysign(1.0, actual) == math.copysign(1.0, expected), (
                f"{path}: zero sign +0.0 != -0.0 ({actual!r} vs {expected!r})"
            )


def roundtrip(data, **kwargs):
    encoded = json2toon(data, **kwargs)
    decoded = toon2json(
        encoded,
        indent=kwargs.get("indent", 2),
        delimiter=kwargs.get("delimiter", ","),
    )
    assert_same_value(decoded, data, path="roundtrip")
    return encoded


# ---------------------------------------------------------------------------
# Reserved words and numeric-looking strings must stay strings
# ---------------------------------------------------------------------------
RESERVED_STRINGS = [
    "true",
    "false",
    "null",
    "True",
    "False",
    "NULL",
    "TRUE",
    "None",
    "123",
    "-5",
    "+5",
    "3.14",
    "1e5",
    "007",
    "1.0",
    "0.0",
    "2e-05",
    "1e+16",
    ".5",
]


@pytest.mark.parametrize("value", RESERVED_STRINGS)
def test_reserved_and_numeric_strings(value):
    encoded = roundtrip({"k": value})
    assert value in encoded or '"' in encoded
    assert toon2json(encoded) == {"k": value}


@pytest.mark.parametrize("value", RESERVED_STRINGS)
def test_reserved_and_numeric_strings_inline(value):
    roundtrip({"v": [value, "plain"]})


# ---------------------------------------------------------------------------
# Exponent and float decoding
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value", [2e-05, 1e16, 1.5e-10, 3.0e2, 1e5, -2e-3, 0.1 + 0.2, -0.0]
)
def test_exponent_and_float_numbers(value):
    roundtrip({"n": value})
    roundtrip({"n": [value, value]})
    decoded = toon2json(json2toon({"n": value}))
    assert type(decoded["n"]) is float


def test_decoder_parses_exponent_tokens_as_floats():
    assert toon2json("n: 2e-05") == {"n": 2e-05}
    assert toon2json("n: 1e+16") == {"n": 1e16}
    assert toon2json("n[2]: 1e5,1.5e-3") == {"n": [1e5, 1.5e-3]}
    assert type(toon2json("n: 2e-05")["n"]) is float
    assert type(toon2json("n: 1e+16")["n"]) is float
    assert type(toon2json("n[2]: 1e5,1.5e-3")["n"][0]) is float


# ---------------------------------------------------------------------------
# Escape preservation: newline / tab / backslash / quotes
# ---------------------------------------------------------------------------
ESCAPE_VALUES = [
    "",
    " ",
    " x",
    "x ",
    "a,b",
    "a\tb",
    "a\nb",
    "a\rb",
    'a"b',
    "a\\b",
    "a\\nb",
    "a:b",
    "- item",
    "[a]",
    "{a}",
    "caf\u00e9",
    "\u4f60\u597d",
    "\U0001f600\U0001f680",
    'a,b\n"c"\\d',
]


@pytest.mark.parametrize("value", ESCAPE_VALUES)
def test_escape_preservation_object_value(value):
    roundtrip({"k": value})


@pytest.mark.parametrize("value", ESCAPE_VALUES)
def test_escape_preservation_root_scalar(value):
    roundtrip(value)


@pytest.mark.parametrize("delimiter", DELIMITERS)
@pytest.mark.parametrize("value", ESCAPE_VALUES)
def test_escape_preservation_table_row(value, delimiter):
    roundtrip({"t": [{"a": value, "b": "z"}]}, mode="table", delimiter=delimiter)


@pytest.mark.parametrize("delimiter", DELIMITERS)
@pytest.mark.parametrize("value", ESCAPE_VALUES)
def test_escape_preservation_inline_array(value, delimiter):
    roundtrip({"v": [value, "plain", "tail"]}, delimiter=delimiter)


@pytest.mark.parametrize("delimiter", DELIMITERS)
def test_escape_preservation_table_row_multi(delimiter):
    rows = [{"a": value, "b": f"x{delimiter}y"} for value in ESCAPE_VALUES]
    roundtrip({"t": rows}, mode="table", delimiter=delimiter)


# ---------------------------------------------------------------------------
# Control characters must survive quoting and line splitting
# ---------------------------------------------------------------------------
CONTROL_VALUES = [
    "a\rb",
    "a\x0bb",
    "a\x0cb",
    "\x01\x02",
    "x\x1cy",
    "a\u0085b",
    "\x00z",
    "a\u00a0b",
    "\u2028x",
]


@pytest.mark.parametrize("value", CONTROL_VALUES)
def test_control_characters_roundtrip(value):
    roundtrip({"k": value})
    roundtrip({"k": [value, "plain"]})
    roundtrip(value)
    roundtrip({"t": [{"a": value}, {"a": "b"}]}, mode="table")


# ---------------------------------------------------------------------------
# Object keys: arbitrary strings, table headers, nested first list entry
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("key", SPECIAL_KEYS)
def test_arbitrary_object_keys(key):
    roundtrip({key: 1})


@pytest.mark.parametrize("key", SPECIAL_KEYS)
def test_arbitrary_object_key_nested_values(key):
    roundtrip({key: {"c": 1}})
    roundtrip({key: [1, 2]})


@pytest.mark.parametrize("key", SPECIAL_KEYS)
def test_special_keys_in_table_headers(key):
    roundtrip({"t": [{key: "v1"}, {key: "v2"}]}, mode="table")


@pytest.mark.parametrize("key", SPECIAL_KEYS)
def test_special_key_as_nested_first_list_entry(key):
    encoded = json2toon({"t": [{key: "v", "z": 1}]}, mode="nested")
    assert toon2json(encoded) == {"t": [{key: "v", "z": 1}]}


def test_table_with_empty_key_roundtrip():
    roundtrip({"t": [{"": 1, "b": 2}, {"": 3, "b": 4}]}, mode="table")


# ---------------------------------------------------------------------------
# Root scalar decoding
# ---------------------------------------------------------------------------
ROOT_SCALARS = [
    42,
    -1,
    0,
    3.14,
    2e-05,
    1e16,
    True,
    False,
    None,
    "",
    "hello",
    "hello world",
    "a:b",
    "[a]",
    "{a}",
    "[2]: x",
    "- item",
    "123",
    "true",
    "TRUE",
    "1e5",
    "a,b",
    "a\nb",
    "a\\b",
    'a"b',
    "caf\u00e9",
]


@pytest.mark.parametrize("value", ROOT_SCALARS)
def test_root_scalar_roundtrip(value):
    roundtrip(value)


def test_root_empty_string_decodes_to_empty_string():
    assert toon2json('""') == ""
    assert toon2json('""') != {}


def test_root_array_header_without_colon_still_raises():
    with pytest.raises(ValueError, match="Array header missing ':'"):
        toon2json("items[2]")


# ---------------------------------------------------------------------------
# Tabular arrays tolerate equal key sets in different insertion orders
# ---------------------------------------------------------------------------
def test_table_allows_reordered_keys_using_first_row_order():
    data = {"t": [{"a": 1, "b": 2}, {"b": 4, "a": 3}]}
    encoded = json2toon(data, mode="table")
    assert encoded.splitlines()[0] == "t[2]{a,b}:"
    assert toon2json(encoded) == {"t": [{"a": 1, "b": 2}, {"a": 3, "b": 4}]}


def test_auto_mode_table_allows_reordered_keys():
    data = {"t": [{"x": "1", "y": "2"}, {"y": "4", "x": "3"}]}
    encoded = json2toon(data)
    assert "{x,y}" in encoded
    roundtrip(data)


def test_table_reordered_keys_with_special_values():
    data = {
        "t": [
            {"a,b": 'q"r', "c": "true"},
            {"c": "x\ny", "a,b": "z"},
        ]
    }
    roundtrip(data, mode="table")


# ---------------------------------------------------------------------------
# Nested list entries whose first value is non-scalar (empty object, nested
# object, array) must not absorb their sibling keys.
# ---------------------------------------------------------------------------
NESTED_FIRST = [
    {"t": [{"a": {}, "b": 1}]},
    {"t": [{"a": {"x": 1}, "b": 2}]},
    {"t": [{"a": {"x": {"y": 1}}, "b": 2}]},
    {"t": [{"a": [1, 2], "b": 3}]},
    {"t": [{"a": [{"x": 1}], "b": 3}]},
    {"t": [{"a": {}, "b": 1}, {"a": {"x": 2}, "b": 4}]},
    {"t": [{"a": {"x": 1}, "b": 2, "c": {"y": 3}}], "root_after": 9},
    {"root_before": 1, "t": [{"a": {"x": 1}, "b": 2}]},
    {"t": [{"a": {"x": 1}, "b": 2}], "tail": {"z": 3}},
]


@pytest.mark.parametrize("data", NESTED_FIRST)
@pytest.mark.parametrize("indent", [1, 2, 3, 4, 8])
def test_nested_first_non_scalar_value_roundtrip(data, indent):
    encoded = json2toon(data, indent=indent, mode="nested")
    assert toon2json(encoded, indent=indent) == data, encoded


@pytest.mark.parametrize("data", NESTED_FIRST)
def test_auto_mode_first_nested_scalarless_roundtrip(data):
    roundtrip(data)


def test_nested_first_nested_object_keeps_siblings_distinct():
    encoded = json2toon({"t": [{"a": {"x": 1}, "b": 2}]}, mode="nested")
    decoded = toon2json(encoded)
    assert decoded == {"t": [{"a": {"x": 1}, "b": 2}]}
    assert decoded["t"][0]["b"] == 2


def test_legacy_compact_nested_first_field_decodes():
    legacy = "t[1]:\n  - a:\n    x: 1"
    assert toon2json(legacy) == {"t": [{"a": {"x": 1}}]}


MIXED_SIBLINGS = [
    {"t": [{"a": {}, "b": [1]}]},
    {"t": [{"a": {}, "b": []}]},
    {"t": [{"a": {"x": 1}, "b": [1, 2], "c": 3}]},
    {"t": [{"a": {}, "b": {"y": 2}, "c": [3]}]},
    {"t": [{"a": [1], "b": {"y": 2}}]},
    {"t": [{"a": {"x": 1}, "b": [{"y": 2}], "c": {"z": 3}}]},
    {"t": [{"a": {}, "b": [1]}, {"a": {"x": 2}, "b": []}]},
]


@pytest.mark.parametrize("data", MIXED_SIBLINGS)
@pytest.mark.parametrize("indent", [1, 2, 3, 4, 8])
@pytest.mark.parametrize("mode", ["nested", "auto"])
def test_mixed_sibling_arrays_and_objects_roundtrip(data, indent, mode):
    encoded = json2toon(data, indent=indent, mode=mode)
    assert_same_value(
        toon2json(encoded, indent=indent), data, path=f"{mode}:{indent}"
    )


def test_first_non_scalar_record_does_not_absorb_sibling_array():
    data = {"t": [{"a": {}, "b": [1]}]}
    encoded = json2toon(data, mode="nested")
    decoded = toon2json(encoded)
    assert decoded == data
    assert decoded["t"][0]["b"] == [1]
    assert decoded["t"][0]["a"] == {}


def test_first_non_scalar_record_empty_sibling_array():
    data = {"t": [{"a": {}, "b": []}]}
    encoded = json2toon(data, mode="nested")
    assert toon2json(encoded) == data


# ---------------------------------------------------------------------------
# Array headers: reject trailing garbage and unterminated field lists, while
# accepting valid quoted field names that contain delimiters/structural chars.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "header",
    [
        "items[1]oops:",
        "items[1]{a,b}oops:",
        "items[1]x{a,b}:",
        "items[1]{a,b",
    ],
)
def test_array_header_rejects_malformed_suffix(header):
    with pytest.raises(ValueError):
        toon2json(header + "\n  1,2")


@pytest.mark.parametrize(
    "header", ["items[1]{\"a,b}", "items[1]{a,\"b}", "items[1]{\"unterminated}"]
)
def test_array_header_rejects_unterminated_field_quotes(header):
    with pytest.raises(ValueError):
        toon2json(header + ":\n  1,2")


@pytest.mark.parametrize("delimiter", DELIMITERS)
def test_array_header_accepts_quoted_fields_with_structural_chars(delimiter):
    key_with_delim = "k" + delimiter
    data = {"t": [{key_with_delim: "v" + delimiter + "y", "c:d": "z"}]}
    encoded = json2toon(data, mode="table", delimiter=delimiter)
    assert toon2json(encoded, delimiter=delimiter) == data


# ---------------------------------------------------------------------------
# CLI roundtrips (stdin TOON must not silently become {})
# ---------------------------------------------------------------------------
def _run_cli(fn, args, stdin=None):
    code = f"from j2toon.cli import {fn} as f; f()"
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(_REPO_SRC), existing) if part
    )
    return subprocess.run(
        [sys.executable, "-c", code, *args],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=".",
        env=env,
    )


def test_cli_json2toon_stdin_matches_file(tmp_path):
    data = {"items": [{"sku": "A1", "qty": 2}], "tags": ["a", "b"]}
    src = tmp_path / "data.json"
    src.write_text(json.dumps(data), encoding="utf-8")

    file_result = _run_cli("json2toon_cli", [str(src)])
    stdin_result = _run_cli("json2toon_cli", [], stdin=json.dumps(data))
    assert file_result.returncode == 0
    assert stdin_result.returncode == 0
    assert stdin_result.stdout == file_result.stdout


def test_cli_convert_stdin_toon_decodes():
    data = {"items": [{"sku": "A1", "qty": 2}], "tags": ["a", "b"]}
    toon = json2toon(data)
    result = _run_cli("j2toon_cli", ["convert"], stdin=toon)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == data


def test_cli_convert_stdin_json_encodes():
    data = {"items": [{"sku": "A1", "qty": 2}]}
    result = _run_cli("j2toon_cli", ["convert"], stdin=json.dumps(data))
    assert result.returncode == 0, result.stderr
    assert "items[1]{sku,qty}:" in result.stdout


@pytest.mark.parametrize("delimiter", DELIMITERS)
def test_cli_roundtrip_all_delimiters(tmp_path, delimiter):
    data = {
        "items": [{"a": "x" + delimiter + "y", "b": "p\nq"}],
        "tags": ["a\\b", 'c"d'],
    }
    src = tmp_path / "data.json"
    src.write_text(json.dumps(data), encoding="utf-8")
    toon_file = tmp_path / "data.toon"
    alias = {",": "comma", "\t": "tab", "|": "pipe"}[delimiter]

    encode = _run_cli(
        "json2toon_cli",
        [str(src), "-o", str(toon_file), "--delimiter", alias],
    )
    assert encode.returncode == 0, encode.stderr

    decode = _run_cli(
        "toon2json_cli",
        [str(toon_file), "--delimiter", alias],
    )
    assert decode.returncode == 0, decode.stderr
    assert json.loads(decode.stdout) == data
