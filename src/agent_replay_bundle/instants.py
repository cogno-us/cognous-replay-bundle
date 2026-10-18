"""One strict reader for the instants Replay accepts.

``YYYY-MM-DDThh:mm:ss[.f]`` followed by ``Z`` or ``+hh:mm`` / ``-hh:mm``: upper-case ``T`` and ``Z``, ASCII digits only, seconds
present, one to six fraction digits, hour 00 to 23, minute and second 00 to 59, a real calendar date, an explicit offset. A
bare ``datetime.fromisoformat`` also takes a space separator, week and ordinal dates, a seventh fraction digit, compact forms and (from
Python 3.14) hour 24, so it is not used on its own.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

_SHAPE = (r"[0-9]{4}-[0-9]{2}-[0-9]{2}T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\.[0-9]{1,6})?")
_INSTANT = re.compile(_SHAPE + r"(Z|[+-]([01][0-9]|2[0-3]):[0-5][0-9])")
_NAIVE = re.compile(_SHAPE)


def parse_instant(value: Any) -> datetime | None:
    """A timezone-aware datetime, or None for anything outside the grammar (never a guess)."""
    if not isinstance(value, str) or _INSTANT.fullmatch(value) is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def is_naive_shape(value: Any) -> bool:
    """True for an otherwise valid time with no offset (used only to word a refusal)."""
    return isinstance(value, str) and _NAIVE.fullmatch(value) is not None
