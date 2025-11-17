"""Tests for complex nested JSON structures."""

import textwrap

from j2toon import json2toon, toon2json


def normalize(text: str) -> str:
    return "\n".join(line.rstrip() for line in textwrap.dedent(text).strip().splitlines())


def test_deeply_nested_structure():
    """Test deeply nested objects and arrays."""
    data = {
        "company": {
            "name": "Tech Corp",
            "departments": [
                {
                    "id": 1,
                    "name": "Engineering",
                    "teams": [
                        {
                            "id": 101,
                            "name": "Backend",
                            "members": [
                                {"id": 1001, "name": "Alice", "role": "Senior", "active": True},
                                {"id": 1002, "name": "Bob", "role": "Junior", "active": True},
                            ],
                        },
                        {
                            "id": 102,
                            "name": "Frontend",
                            "members": [
                                {"id": 2001, "name": "Charlie", "role": "Lead", "active": False},
                            ],
                        },
                    ],
                },
                {
                    "id": 2,
                    "name": "Sales",
                    "teams": [],
                },
            ],
            "metadata": {
                "founded": 2010,
                "locations": ["NYC", "SF", "London"],
                "active": True,
            },
        },
    }

    toon = json2toon(data)
    decoded = toon2json(toon)
    assert decoded == data


def test_mixed_array_types():
    """Test arrays with mixed primitive and object types."""
    data = {
        "mixed": [
            1,
            "string",
            True,
            None,
            3.14,
            {"nested": "value"},
            [1, 2, 3],
        ],
    }

    toon = json2toon(data)
    decoded = toon2json(toon)
    assert decoded == data


def test_empty_structures():
    """Test empty objects, arrays, and strings."""
    data = {
        "empty_dict": {},
        "empty_list": [],
        "empty_string": "",
        "null_value": None,
        "nested_empty": {
            "inner": {},
            "list": [],
        },
    }

    toon = json2toon(data)
    decoded = toon2json(toon)
    assert decoded == data


def test_special_characters_in_strings():
    """Test strings with special characters that need escaping."""
    data = {
        "quotes": 'String with "quotes"',
        "newline": "Line 1\nLine 2",
        "tab": "Column1\tColumn2",
        "colon": "Key: Value",
        "dash_prefix": "- This looks like a list",
        "delimiter": "Item1,Item2,Item3",
        "backslash": "Path\\to\\file",
    }

    toon = json2toon(data)
    decoded = toon2json(toon)
    assert decoded == data


def test_numbers_edge_cases():
    """Test various number formats."""
    data = {
        "integers": [0, -1, 42, 1000000],
        "floats": [0.0, -3.14, 1.5e10, 0.001],
        "scientific": [1e5, -2e-3, 3.14e2],
    }

    toon = json2toon(data)
    decoded = toon2json(toon)
    assert decoded == data


def test_boolean_and_null():
    """Test boolean and null values."""
    data = {
        "booleans": [True, False, True, False],
        "nulls": [None, None, None],
        "mixed_bool_null": [True, None, False, None, True],
    }

    toon = json2toon(data)
    decoded = toon2json(toon)
    assert decoded == data


def test_large_tabular_array():
    """Test large uniform array that should use tabular format."""
    data = {
        "products": [
            {"id": i, "name": f"Product {i}", "price": i * 10.5, "in_stock": i % 2 == 0}
            for i in range(1, 21)
        ],
    }

    toon = json2toon(data)
    # Should use tabular format
    assert "products[20]{" in toon
    decoded = toon2json(toon)
    assert decoded == data
    assert len(decoded["products"]) == 20


def test_nested_tabular_arrays():
    """Test tabular arrays nested inside objects."""
    data = {
        "departments": [
            {
                "name": "Engineering",
                "employees": [
                    {"id": 1, "name": "Alice", "salary": 100000},
                    {"id": 2, "name": "Bob", "salary": 95000},
                ],
            },
            {
                "name": "Sales",
                "employees": [
                    {"id": 3, "name": "Charlie", "salary": 80000},
                ],
            },
        ],
    }

    toon = json2toon(data)
    decoded = toon2json(toon)
    assert decoded == data


def test_root_level_array():
    """Test array at root level."""
    data = [
        {"id": 1, "value": "first"},
        {"id": 2, "value": "second"},
    ]

    toon = json2toon(data)
    decoded = toon2json(toon)
    assert decoded == data


def test_very_deep_nesting():
    """Test extremely deep nesting."""
    data = {
        "level1": {
            "level2": {
                "level3": {
                    "level4": {
                        "level5": {
                            "level6": {
                                "value": "deep",
                                "numbers": [1, 2, 3],
                            },
                        },
                    },
                },
            },
        },
    }

    toon = json2toon(data)
    decoded = toon2json(toon)
    assert decoded == data


def test_complex_real_world_scenario():
    """Test a realistic complex scenario combining many features."""
    data = {
        "api_response": {
            "status": "success",
            "timestamp": 1234567890,
            "data": {
                "users": [
                    {
                        "id": 1,
                        "username": "alice",
                        "email": "alice@example.com",
                        "profile": {
                            "first_name": "Alice",
                            "last_name": "Smith",
                            "age": 30,
                            "active": True,
                        },
                        "tags": ["admin", "developer"],
                        "metadata": None,
                    },
                    {
                        "id": 2,
                        "username": "bob",
                        "email": "bob@example.com",
                        "profile": {
                            "first_name": "Bob",
                            "last_name": "Jones",
                            "age": 25,
                            "active": False,
                        },
                        "tags": ["user"],
                        "metadata": {"last_login": "2024-01-01"},
                    },
                ],
                "pagination": {
                    "page": 1,
                    "per_page": 10,
                    "total": 2,
                },
            },
            "errors": [],
        },
    }

    toon = json2toon(data)
    decoded = toon2json(toon)
    assert decoded == data


def test_different_delimiters():
    """Test with different delimiter options."""
    data = {
        "items": [
            {"a": 1, "b": 2},
            {"a": 3, "b": 4},
        ],
    }

    # Test comma delimiter (default)
    toon_comma = json2toon(data, delimiter=",")
    decoded_comma = toon2json(toon_comma, delimiter=",")
    assert decoded_comma == data

    # Test tab delimiter
    toon_tab = json2toon(data, delimiter="\t")
    decoded_tab = toon2json(toon_tab, delimiter="\t")
    assert decoded_tab == data

    # Test pipe delimiter
    toon_pipe = json2toon(data, delimiter="|")
    decoded_pipe = toon2json(toon_pipe, delimiter="|")
    assert decoded_pipe == data


def test_different_indent_sizes():
    """Test with different indent sizes."""
    data = {
        "nested": {
            "deep": {
                "value": 42,
            },
        },
    }

    for indent in [2, 4, 8]:
        toon = json2toon(data, indent=indent)
        decoded = toon2json(toon, indent=indent)
        assert decoded == data

