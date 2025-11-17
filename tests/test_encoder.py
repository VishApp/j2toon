import textwrap

from j2toon import json2toon, toon2json  # type: ignore


def normalize(text: str) -> str:
    return "\n".join(line.rstrip() for line in textwrap.dedent(text).strip().splitlines())


def test_inline_array():
    data = {"tags": ["foo", "bar"]}
    assert json2toon(data) == "tags[2]: foo,bar"


def test_tabular_array():
    data = {
        "items": [
            {"sku": "A1", "qty": 2, "price": 9.99},
            {"sku": "B2", "qty": 1, "price": 14.5},
        ]
    }
    expected = """
    items[2]{sku,qty,price}:
      A1,2,9.99
      B2,1,14.5
    """
    assert normalize(json2toon(data)) == normalize(expected)


def test_mixed_array():
    data = {"values": [1, {"a": 1}, ["x", "y"]]}
    output = json2toon(data)
    assert "values[3]:" in output
    assert "- 1" in output
    # New format: first key on same line as dash
    assert "- a: 1" in output


def test_decode_inline_object():
    toon = "tags[2]: foo,bar"
    assert toon2json(toon) == {"tags": ["foo", "bar"]}


def test_roundtrip():
    payload = {
        "users": [
            {"id": 1, "name": "Ada", "active": True},
            {"id": 2, "name": "Linus", "active": False},
        ],
        "values": [1, {"nested": ["x", "y"]}],
    }
    encoded = json2toon(payload)
    assert toon2json(encoded) == payload


def test_root_array_decode():
    toon = "[2]: foo,bar"
    assert toon2json(toon) == ["foo", "bar"]

