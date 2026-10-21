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

# One pass over the text: find the next quote or bracket, and inside a string jump from one quote or backslash to the next.
# Nothing is rescanned, so the cost is linear in the input however many escaped quotes it holds.
_NEXT = re.compile(r'["\[\]{}]')
_STRING_STEP = re.compile(r'["\\]')


class InputBoundsError(ValueError):
    """Input exceeded the byte budget or the nesting-depth limit."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class DuplicateMemberError(ValueError):
    """A JSON object contained the same member name more than once."""


def check_depth(text: str, max_depth: int = MAX_NESTING_DEPTH) -> None:
    """Raise InputBoundsError if brackets nest deeper than ``max_depth``.

    A string that never closes ends the scan: the rest of the text is inside it, and the JSON parser refuses the text itself.
    """
    depth = 0
    pos = 0
    while True:
        match = _NEXT.search(text, pos)
        if match is None:
            return
        ch = match.group()
        pos = match.end()
        if ch == '"':
            while True:
                step = _STRING_STEP.search(text, pos)
                if step is None:
                    return
                pos = step.end()
                if step.group() == '"':
                    break
                pos += 1  # the character after a backslash belongs to the escape
        elif ch == "[" or ch == "{":
            depth += 1
            if depth > max_depth:
                raise InputBoundsError(
                    "nesting_depth_exceeded",
                    f"input nesting depth exceeds {max_depth}",
                )
        else:
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


class NonFiniteNumberError(ValueError):
    """A JSON document contained NaN, Infinity or -Infinity, which are not JSON."""


def _reject_constant(name: str) -> Any:
    raise NonFiniteNumberError(f"non-finite JSON number is not accepted: {name}")


def load_json_bounded(
    path: str | Path,
    *,
    reject_duplicates: bool = True,
    max_bytes: int = MAX_INPUT_BYTES,
    max_depth: int = MAX_NESTING_DEPTH,
) -> Any:
    """Parse a JSON file within bounds.

    A JSON object that repeats a member name is refused (``DuplicateMemberError``, a ``ValueError``) unless
    ``reject_duplicates=False`` is passed explicitly: the parser would otherwise keep only the last value, so what is
    validated would differ from what a reader of the file sees.
    """
    text = read_bounded_text(path, max_bytes=max_bytes, max_depth=max_depth)
    hook = _no_duplicates if reject_duplicates else None
    return json.loads(text, object_pairs_hook=hook, parse_constant=_reject_constant)
