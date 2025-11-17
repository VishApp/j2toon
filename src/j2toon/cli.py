"""Minimal CLI wrappers around the json2toon/toon2json helpers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .encoder import encode as json2toon
from .decoder import decode as toon2json

_DELIMITER_ALIASES = {
    "comma": ",",
    ",": ",",
    "tab": "\t",
    "\t": "\t",
    "pipe": "|",
    "|": "|",
}


def _normalize_delimiter(value: str) -> str:
    try:
        return _DELIMITER_ALIASES[value]
    except KeyError:  # pragma: no cover - argparse already bounds options
        raise argparse.ArgumentTypeError(
            "delimiter must be one of: comma, tab, pipe"
        ) from None


def _read_text(path: str | None) -> str:
    if path is None or path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _read_json(path: str | None) -> object:
    if path is None or path == "-":
        return json.load(sys.stdin)
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_text(path: str | None, content: str) -> None:
    if path is None or path == "-":
        sys.stdout.write(content)
        sys.stdout.write("\n")
        return
    Path(path).write_text(content, encoding="utf-8")


def _write_json(path: str | None, payload: object) -> None:
    if path is None or path == "-":
        json.dump(payload, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)


def json2toon_cli() -> None:
    parser = argparse.ArgumentParser(description="Convert JSON to TOON")
    parser.add_argument("input", nargs="?", default="-", help="JSON file (default: stdin)")
    parser.add_argument(
        "-o", "--output", default="-", help="Where to write TOON (default: stdout)"
    )
    parser.add_argument(
        "--indent", type=int, default=2, help="Indent width (default: 2)"
    )
    parser.add_argument(
        "--delimiter",
        type=_normalize_delimiter,
        default=",",
        choices=list(_DELIMITER_ALIASES.keys()),
        help="Delimiter: comma, tab, pipe (default: comma)",
    )
    args = parser.parse_args()

    data = _read_json(args.input)
    output = json2toon(data, indent=args.indent, delimiter=args.delimiter)
    _write_text(args.output, output)


def toon2json_cli() -> None:
    parser = argparse.ArgumentParser(description="Convert TOON to JSON")
    parser.add_argument("input", nargs="?", default="-", help="TOON file (default: stdin)")
    parser.add_argument(
        "-o", "--output", default="-", help="Where to write JSON (default: stdout)"
    )
    parser.add_argument(
        "--indent", type=int, default=2, help="Indent width used in the input (default: 2)"
    )
    parser.add_argument(
        "--delimiter",
        type=_normalize_delimiter,
        default=",",
        choices=list(_DELIMITER_ALIASES.keys()),
        help="Delimiter used in tabular rows (default: comma)",
    )
    args = parser.parse_args()

    text = _read_text(args.input)
    data = toon2json(text, indent=args.indent, delimiter=args.delimiter)
    _write_json(args.output, data)


def j2toon_cli() -> None:
    """Unified CLI that auto-detects conversion direction."""
    parser = argparse.ArgumentParser(
        description="Convert between JSON and TOON formats (auto-detects direction)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  j2toon convert data.json -o data.toon    # JSON -> TOON
  j2toon convert data.toon -o data.json    # TOON -> JSON
  json2toon data.json -o data.toon         # JSON -> TOON (alternative)
  toon2json data.toon -o data.json         # TOON -> JSON (alternative)
        """,
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Command to run")
    
    # Convert subcommand (auto-detects direction)
    convert_parser = subparsers.add_parser("convert", help="Convert between JSON and TOON (auto-detects direction)")
    convert_parser.add_argument("input", nargs="?", default="-", help="Input file (default: stdin)")
    convert_parser.add_argument(
        "-o", "--output", default="-", help="Output file (default: stdout)"
    )
    convert_parser.add_argument(
        "--indent", type=int, default=2, help="Indent width (default: 2)"
    )
    convert_parser.add_argument(
        "--delimiter",
        type=_normalize_delimiter,
        default=",",
        choices=list(_DELIMITER_ALIASES.keys()),
        help="Delimiter: comma, tab, pipe (default: comma)",
    )
    
    args = parser.parse_args()
    
    if args.command == "convert":
        # Auto-detect direction based on file extensions
        input_path = args.input if args.input != "-" else None
        output_path = args.output if args.output != "-" else None
        
        # Determine direction: if input is .json or output is .toon, encode (JSON -> TOON)
        # Otherwise, decode (TOON -> JSON)
        if input_path and input_path.endswith(".json"):
            # JSON -> TOON
            data = _read_json(args.input)
            output = json2toon(data, indent=args.indent, delimiter=args.delimiter)
            _write_text(args.output, output)
        elif output_path and output_path.endswith(".json"):
            # TOON -> JSON
            text = _read_text(args.input)
            data = toon2json(text, indent=args.indent, delimiter=args.delimiter)
            _write_json(args.output, data)
        elif input_path and input_path.endswith(".toon"):
            # TOON -> JSON
            text = _read_text(args.input)
            data = toon2json(text, indent=args.indent, delimiter=args.delimiter)
            _write_json(args.output, data)
        elif output_path and output_path.endswith(".toon"):
            # JSON -> TOON
            data = _read_json(args.input)
            output = json2toon(data, indent=args.indent, delimiter=args.delimiter)
            _write_text(args.output, output)
        else:
            # Default: try to detect from content or assume JSON -> TOON
            # For stdin/stdout, we'll try JSON -> TOON first
            try:
                data = _read_json(args.input)
                output = json2toon(data, indent=args.indent, delimiter=args.delimiter)
                _write_text(args.output, output)
            except (json.JSONDecodeError, ValueError):
                # If JSON parsing fails, try TOON -> JSON
                text = _read_text(args.input)
                data = toon2json(text, indent=args.indent, delimiter=args.delimiter)
                _write_json(args.output, data)
