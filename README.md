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

### Options

When using the functions in Python, you can customize the output with these options:

- `indent` – how many spaces to use for each level of nesting (default is 2)
- `delimiter` – what character to use to separate values in lists and tables. You can use `","` (comma), `"\t"` (tab), or `"|"` (pipe)

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
