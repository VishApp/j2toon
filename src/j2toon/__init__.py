"""Public entry points for converting between Python values and TOON text."""

from .decoder import decode as toon2json
from .encoder import encode as json2toon

# Aliases for compatibility with PyPI package
json_to_toon = json2toon
toon_to_json = toon2json

__all__ = [
    "json2toon",
    "toon2json",
    "json_to_toon",
    "toon_to_json",
]

