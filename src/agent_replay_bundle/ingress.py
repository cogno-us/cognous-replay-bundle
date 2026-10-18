"""Bounded reading of JSON input files.

Every CLI command and the file loader read untrusted JSON through this module.
It applies a byte budget and a nesting-depth limit before the standard parser
runs, and reports a violation as ``InputBoundsError`` (a ``ValueError``) so the
caller can map it to a dedicated exit code instead of an uncaught exception.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_NESTING_DEPTH = 128

#: CLI exit code for input that exceeds the bounds; distinct from 1 (INVALID)
#: and 2 (file, parse or model error).
EXIT_INPUT_BOUNDS = 3

_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|[\[\]{}]', re.DOTALL)


class InputBoundsError(ValueError):
    """Input exceeded the byte budget or the nesting-depth limit."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class DuplicateMemberError(ValueError):
    """A JSON object contained the same member name more than once."""


def check_depth(text: str, max_depth: int = MAX_NESTING_DEPTH) -> None:
    """Raise InputBoundsError if brackets nest deeper than ``max_depth``."""
    depth = 0
    for match in _TOKEN.finditer(text):
        ch = match.group()
        if ch == "[" or ch == "{":
            depth += 1
            if depth > max_depth:
                raise InputBoundsError(
                    "nesting_depth_exceeded",
                    f"input nesting depth exceeds {max_depth}",
                )
        elif ch == "]" or ch == "}":
            depth -= 1


def read_bounded_text(
    path: str | Path,
    *,
    max_bytes: int = MAX_INPUT_BYTES,
    max_depth: int = MAX_NESTING_DEPTH,
) -> str:
    """Read a UTF-8 file within the byte budget and depth limit."""
    with open(path, "rb") as handle:
        data = handle.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise InputBoundsError(
            "input_too_large", f"input exceeds the {max_bytes} byte limit"
        )
    text = data.decode("utf-8")
    check_depth(text, max_depth)
    return text


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateMemberError(f"duplicate member name: {key!r}")
        out[key] = value
    return out


def load_json_bounded(
    path: str | Path,
    *,
    reject_duplicates: bool = False,
    max_bytes: int = MAX_INPUT_BYTES,
    max_depth: int = MAX_NESTING_DEPTH,
) -> Any:
    """Parse a JSON file within bounds.

    Duplicate members keep the parser default (last one wins) unless
    ``reject_duplicates`` is set.
    """
    text = read_bounded_text(path, max_bytes=max_bytes, max_depth=max_depth)
    hook = _no_duplicates if reject_duplicates else None
    return json.loads(text, object_pairs_hook=hook)
