"""The one JSON-semantic equality used where Replay binds retained values to committed operation values.

Python ``==`` is not JSON equality: ``True == 1``, ``False == 0.0`` and ``[True] == [1]`` all hold, so a boolean could
silently stand in for a number (or the reverse) in a value that is bound to a committed operation. This module compares
values by their JSON type (RFC 8259):

* six JSON types: null, boolean, number, string, array, object; a value only ever equals a value of the same type.
* a boolean equals only the same boolean and is never a number; a string never equals a number or a boolean;
  null equals only null (``None != False``, a missing member never equals a null member).
* int and float are one JSON number type and compare by exact mathematical value (``50 == 50.0``,
  ``-0.0 == 0 == 0.0``; ``2**53 + 1 != float(2**53)``).
* list and tuple are the same JSON array, compared element-wise, only after every member is a valid JSON value.
* objects need the identical set of string keys and equal values; key order is irrelevant. Duplicate members cannot exist
  in a parsed ``dict`` (the ingress parser refuses them).
* anything else (bytes, set, Decimal, datetime, NaN/Infinity, non-``str`` keys, subclasses of the JSON types, arbitrary
  objects, or a structure over the node budget) is not JSON: ``NonJsonValue`` is raised, never a plain ``False``, even when
  the rest of the comparison would already differ. Both operands are validated in full before they are compared.

The comparison is iterative (no recursion limit) and bounded. It never changes how values are serialized.
"""
from __future__ import annotations

import math
from typing import Any

MAX_NODES = 1_000_000


class NonJsonValue(ValueError):
    """An operand of a JSON-semantic comparison is not a JSON value (fail closed)."""


def _tag(value: Any) -> str:
    kind = type(value)
    if value is None:
        return "null"
    if kind is bool:
        return "boolean"
    if kind is int:
        return "number"
    if kind is float:
        if not math.isfinite(value):
            raise NonJsonValue("non-finite number is not a JSON value")
        return "number"
    if kind is str:
        return "string"
    if kind is list or kind is tuple:
        return "array"
    if kind is dict:
        return "object"
    raise NonJsonValue(f"not a JSON value: {kind.__name__}")


def validate_json_value(value: Any) -> None:
    """Raise ``NonJsonValue`` unless ``value`` is made only of JSON values (iterative, bounded)."""
    stack = [value]
    nodes = 0
    while stack:
        item = stack.pop()
        nodes += 1
        if nodes > MAX_NODES:
            raise NonJsonValue("value exceeds the comparison node budget")
        tag = _tag(item)
        if tag == "array":
            stack.extend(item)
        elif tag == "object":
            for key in item:
                if type(key) is not str:
                    raise NonJsonValue("object key is not a string")
            stack.extend(item.values())


def json_equal(a: Any, b: Any) -> bool:
    """JSON-semantic equality of two values; raises ``NonJsonValue`` if either is not (entirely) a JSON value."""
    validate_json_value(a)
    validate_json_value(b)
    stack = [(a, b)]
    while stack:
        x, y = stack.pop()
        tx = _tag(x)
        if tx != _tag(y):
            return False
        if tx == "array":
            if len(x) != len(y):
                return False
            stack.extend(zip(x, y))
        elif tx == "object":
            if x.keys() != y.keys():
                return False
            stack.extend((x[key], y[key]) for key in x)
        elif x != y:  # same tag: null, boolean, number (exact value, -0.0 == 0) or string
            return False
    return True


def json_contains(item: Any, collection: Any) -> bool:
    """Semantic ``item in collection`` for a JSON array (list or tuple) of JSON values."""
    validate_json_value(item)
    if type(collection) not in (list, tuple):
        raise NonJsonValue("collection is not a JSON array")
    return any(json_equal(item, member) for member in collection)


def json_key(value: Any) -> Any:
    """A hashable key such that ``json_key(a) == json_key(b)`` exactly when ``json_equal(a, b)``.

    Types are tagged (a boolean is not a number), numbers are normalised by exact value (``1`` and ``1.0`` agree,
    ``-0.0`` is ``0``), arrays become tuples (list == tuple) and objects become frozensets of (key, key(value)).
    Raises ``NonJsonValue`` for a non-JSON value. Used to find equal rows in one hash pass.
    """
    validate_json_value(value)

    def build(node: Any) -> Any:
        tag = _tag(node)
        if tag == "null":
            return ("null",)
        if tag == "boolean":
            return ("boolean", node)
        if tag == "number":
            return ("number", 0 if node == 0 else node)
        if tag == "string":
            return ("string", node)
        if tag == "array":
            return ("array", tuple(build(member) for member in node))
        return ("object", frozenset((key, build(member)) for key, member in node.items()))

    # validate_json_value already bounded the node count; depth is bounded by the ingress depth limit upstream,
    # and a pathological depth surfaces as RecursionError which the caller treats as a refusal.
    return build(value)
