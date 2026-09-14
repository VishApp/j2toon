"""Tests for the nested/table/auto output mode option."""

import json
import sys

import pytest

from j2toon import json2toon, toon2json
from j2toon.cli import j2toon_cli, json2toon_cli

ROWS = {
    "items": [
        {"sku": "A1", "qty": 2, "price": 9.99},
        {"sku": "B2", "qty": 1, "price": 14.5},
    ]
}

HETEROGENEOUS = {"items": [{"a": 1}, {"b": 2}]}

NESTED_VALUES = {
    "items": [
        {"id": 1, "meta": {"x": 1}},
        {"id": 2, "meta": {"x": 2}},
    ]
}


def test_auto_is_default_and_unchanged():
    assert json2toon(ROWS) == json2toon(ROWS, mode="auto")
    assert "items[2]{sku,qty,price}:" in json2toon(ROWS)


def test_table_mode_emits_table():
    out = json2toon(ROWS, mode="table")
    assert "items[2]{sku,qty,price}:" in out
    assert "- sku:" not in out
    assert toon2json(out) == ROWS


def test_nested_mode_avoids_tables():
    out = json2toon(ROWS, mode="nested")
    assert "{sku,qty,price}" not in out
    assert "items[2]:" in out
    assert "- sku: A1" in out
    assert toon2json(out) == ROWS


def test_nested_mode_roundtrips_complex_document():
    payload = {
        "company": {
            "name": "Acme",
            "teams": [
                {"id": 1, "name": "Backend", "active": True},
                {"id": 2, "name": "Frontend", "active": False},
            ],
            "tags": ["a", "b"],
        }
    }
    out = json2toon(payload, mode="nested")
    assert "{id,name,active}" not in out
    assert toon2json(out) == payload


def test_table_mode_keeps_primitive_arrays_inline():
    payload = {"tags": ["hardware", "beta"], "nums": [1, 2, 3]}
    out = json2toon(payload, mode="table")
    assert "tags[2]: hardware,beta" in out
    assert toon2json(out) == payload


def test_table_mode_supports_root_array():
    payload = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    out = json2toon(payload, mode="table")
    assert out.startswith("[2]{a,b}:")
    assert toon2json(out) == payload


def test_table_mode_rejects_heterogeneous_objects():
    with pytest.raises(ValueError, match="mode='table' cannot represent array"):
        json2toon(HETEROGENEOUS, mode="table")


def test_table_mode_rejects_non_scalar_fields():
    with pytest.raises(ValueError, match="mode='table' cannot represent array"):
        json2toon(NESTED_VALUES, mode="table")


def test_nested_mode_handles_heterogeneous_objects():
    out = json2toon(HETEROGENEOUS, mode="nested")
    assert toon2json(out) == HETEROGENEOUS


def test_auto_mode_falls_back_to_nested():
    out = json2toon(HETEROGENEOUS, mode="auto")
    assert "{a,b}" not in out
    assert toon2json(out) == HETEROGENEOUS


def test_invalid_mode_raises():
    with pytest.raises(ValueError, match="mode must be one of"):
        json2toon(ROWS, mode="bogus")


def test_cli_json2toon_table_mode(tmp_path, monkeypatch, capsys):
    src = tmp_path / "data.json"
    src.write_text(json.dumps(ROWS), encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv", ["json2toon", str(src), "--mode", "table"]
    )
    json2toon_cli()
    out = capsys.readouterr().out
    assert "items[2]{sku,qty,price}:" in out


def test_cli_json2toon_nested_mode(tmp_path, monkeypatch, capsys):
    src = tmp_path / "data.json"
    src.write_text(json.dumps(ROWS), encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv", ["json2toon", str(src), "--mode", "nested"]
    )
    json2toon_cli()
    out = capsys.readouterr().out
    assert "{sku,qty,price}" not in out
    assert "- sku: A1" in out


def test_cli_convert_honours_nested_mode(tmp_path, monkeypatch, capsys):
    src = tmp_path / "data.json"
    src.write_text(json.dumps(ROWS), encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv", ["j2toon", "convert", str(src), "--mode", "nested"]
    )
    j2toon_cli()
    out = capsys.readouterr().out
    assert "{sku,qty,price}" not in out
    assert "- sku: A1" in out


def test_cli_convert_extensionless_json_surfaces_table_error(
    tmp_path, monkeypatch, capsys
):
    src = tmp_path / "payload"
    src.write_text(json.dumps(HETEROGENEOUS), encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv", ["j2toon", "convert", str(src), "--mode", "table"]
    )
    with pytest.raises(ValueError, match="mode='table' cannot represent array"):
        j2toon_cli()
    assert capsys.readouterr().out == ""
