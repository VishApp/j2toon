# j2toon

`j2toon` is a simple Python tool that converts JSON data into [TOON format](https://github.com/toon-format/toon) and converts it back. TOON is a human-readable data format that's easier to read and edit than JSON. You don't need to learn all the TOON rules—the tool automatically chooses the best format for your data.

## Why use j2toon?

- **Easy to use** – just two simple functions: `json2toon` and `toon2json`
- **Smart formatting** – automatically formats your data in the most readable way (tables, lists, or nested blocks)
- **No extra packages needed** – works with just Python, no additional libraries required

## Installation

Install j2toon using pip or uv:

```bash
pip install j2toon
```

or

```bash
uv pip install j2toon
```

## Usage

Here's a simple example showing how to convert JSON to TOON and back:

```python
from j2toon import json2toon, toon2json

# Start with some JSON data
document = {
    "items": [
        {"sku": "A1", "qty": 2, "price": 9.99},
        {"sku": "B2", "qty": 1, "price": 14.5}
    ],
    "tags": ["hardware", "beta"]
}

# Convert JSON to TOON format
text = json2toon(document)
print(text)
# items[2]{sku,qty,price}:
#   A1,2,9.99
#   B2,1,14.5
# tags[2]: hardware,beta

# Convert back to JSON to verify it works
assert toon2json(text) == document
```

### Command line

You can also use j2toon from the command line:

```bash
json2toon data.json -o data.toon        # Convert JSON to TOON
toon2json data.toon --indent 2          # Convert TOON back to JSON
```

Both commands support these options:
- `--indent` – how many spaces to use for indentation (default is 2)
- `--delimiter` – what character to use to separate values (default is comma)

The encoding commands (`json2toon` and `j2toon convert`) additionally support:
- `--mode` – how to encode arrays of objects: `auto` (default), `table`, or `nested`. This option is encoding-only; `toon2json` does not accept it.

### Options

When using the functions in Python, you can customize the output with these options:

- `indent` – how many spaces to use for each level of nesting (default is 2)
- `delimiter` – what character to use to separate values in lists and tables. You can use `","` (comma), `"\t"` (tab), or `"|"` (pipe)
- `mode` – how to encode arrays of objects (default is `"auto"`):
  - `"auto"` – use a table when all objects share the same scalar fields, otherwise use nested list entries
  - `"table"` – force tabular output for non-empty arrays whose items are all objects. If those objects do not share the same scalar fields, a `ValueError` is raised. Primitive arrays (e.g. `[1, 2, 3]`) and mixed arrays (objects and primitives together) keep their normal representation and never raise.
  - `"nested"` – never use tables; always emit nested list entries

### Choosing table vs nested output

By default (`"auto"`) an array of uniform objects becomes a compact table. Pass
`mode="nested"` to force one entry per object instead, which is useful when you
want to preserve per-object grouping or diff two documents line by line:

```python
from j2toon import json2toon

document = {
    "items": [
        {"sku": "A1", "qty": 2, "price": 9.99},
        {"sku": "B2", "qty": 1, "price": 14.5},
    ]
}

print(json2toon(document))
# items[2]{sku,qty,price}:
#   A1,2,9.99
#   B2,1,14.5

print(json2toon(document, mode="nested"))
# items[2]:
#   - sku: A1
#     qty: 2
#     price: 9.99
#   - sku: B2
#     qty: 1
#     price: 14.5
```

Use `mode="table"` when you need to guarantee tabular output. The strict rule
only applies to non-empty arrays whose items are all objects: if they do not
share the same scalar fields, a `ValueError` is raised so you can fix the input
instead of silently getting a different layout. Primitive arrays and mixed
arrays are unaffected and keep their normal representation.

Tables use the field order of the **first row** for the header. Later rows may
list the same fields in any order; they are mapped back onto the first row's
order when decoded.

`mode` is an encoding-only option. It is accepted by `json2toon` (and the
`json2toon` / `j2toon convert` commands) but not by `toon2json`, whose only
decode-time options are `indent` and `delimiter`.

### Reserved strings, exponents, and special keys

Values that merely look like other types stay strings: `"true"`, `"null"`,
`"123"`, `"1e5"`, and other numeric-looking tokens are quoted on the way out so
they decode back to strings. Exponents such as `2e-05` and `1e16` are written
bare and decode to floats. Keys containing delimiters or structural characters
(`a,b`, `a:b`, `a[0]`, empty strings, leading dashes) are quoted too:

```python
from j2toon import json2toon, toon2json

document = {
    "true": "false",        # reserved word as a key
    "ratio": 2e-05,         # exponent number
    "a,b": "x:y",           # delimiter/structural chars in key and value
}

text = json2toon(document)
# true: "false"
# ratio: 2e-05
# "a,b": "x:y"

assert toon2json(text) == document
```

```bash
json2toon data.json --mode nested        # Force nested list entries
json2toon data.json --mode table         # Force tables, error if impossible
j2toon convert data.json --mode nested   # Same, via the unified CLI
j2toon convert data.json --mode table    # Force tables, error if impossible
```


## Development

To set up the project for development:

```bash
pip install -e .
pytest
```

**Requirements:**
- Python 3.9 or higher
- Tests are in the `tests/` folder and check that conversions work correctly in both directions

## Maintainer

- Vishnu Prasad — vishnuprasadapp@gmail.com

## Learn More

For complete details about the TOON format, check out the [official TOON specification](https://github.com/toon-format/toon). This tool focuses on the most commonly used parts of TOON to keep things simple and reliable.
