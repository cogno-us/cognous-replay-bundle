"""Input validation bounds: linear-time depth scan, inner JSON text depth, and a work budget for the journal matcher."""
import copy
import json
import random
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from agent_replay_bundle import ImportContractError, import_bounded_workflow
from agent_replay_bundle.importers import _decode_payload_json
from agent_replay_bundle.ingress import InputBoundsError, check_depth

from .test_refusal_journal import EXECUTOR, JOURNAL_REVISIONS, load, run

ROOT = Path(__file__).resolve().parent.parent


def _in_child(code, limit):
    """Run ``code`` in a child interpreter with a hard time limit; returns stdout or None when the limit passed."""
    try:
        done = subprocess.run([sys.executable, "-I", "-c", textwrap.dedent(code)], capture_output=True, text=True, timeout=limit)
    except subprocess.TimeoutExpired:
        return None
    assert done.returncode == 0, done.stderr[-400:]
    return done.stdout.strip()


# ------------------------------------------------------------------------------------------------ depth scan: cost
def test_scan_of_80_kb_of_escaped_quotes_is_fast():
    out = _in_child("""
        import time
        from agent_replay_bundle.ingress import check_depth
        text = '"' + '\\\\"' * 40000
        started = time.perf_counter()
        check_depth(text)
        print(round(time.perf_counter() - started, 3))
    """, limit=20)
    assert out is not None and float(out) < 1.0


@pytest.mark.parametrize("unit", ['\\"', '\\\\', '\\u0022', '"', '["', '\\"["'])
def test_scan_cost_of_unterminated_strings_is_linear_in_the_input(unit):
    out = _in_child(f"""
        import time
        from agent_replay_bundle.ingress import check_depth
        text = '"' + {unit!r} * 40000
        started = time.perf_counter()
        try:
            check_depth(text)
        except ValueError:
            pass
        print(round(time.perf_counter() - started, 3))
    """, limit=20)
    assert out is not None and float(out) < 1.0


# ------------------------------------------------------------------------------------------ depth scan: unchanged result
def _depth(value):
    best, stack = 0, [(value, 1)]
    while stack:
        item, d = stack.pop()
        if isinstance(item, (dict, list)):
            best = max(best, d)
            stack.extend((c, d + 1) for c in (item.values() if isinstance(item, dict) else item))
    return best


def _random_json(rng, depth):
    if depth == 0 or rng.random() < 0.2:
        return rng.choice([1, None, True, 'plain', 'with "quote"', 'back\\slash\\', '[{', ']}"', '\\"', '\\\\"[', 'é '])
    if rng.random() < 0.5:
        return [_random_json(rng, depth - 1) for _ in range(rng.randint(0, 4))]
    return {rng.choice(['a', 'b"', '[', '\\', 'k\\"']): _random_json(rng, depth - 1) for _ in range(rng.randint(0, 4))}


def test_scan_agrees_with_the_true_nesting_depth_of_valid_documents():
    rng = random.Random(7)
    for _ in range(400):
        value = _random_json(rng, rng.randint(1, 9))
        for text in (json.dumps(value), json.dumps(value, indent=1), json.dumps(value, ensure_ascii=False)):
            true_depth = _depth(value)
            check_depth(text, max_depth=max(true_depth, 1))
            if true_depth >= 1:
                with pytest.raises(InputBoundsError):
                    check_depth(text, max_depth=true_depth - 1)


def test_scan_ignores_brackets_inside_strings_and_counts_those_after_an_escaped_backslash():
    check_depth(json.dumps({"a": "[" * 1000 + '\\"' + "{" * 1000}), max_depth=2)
    check_depth('["\\\\", ["x"]]', max_depth=2)            # the string "\\" ends at its closing quote
    with pytest.raises(InputBoundsError):
        check_depth('["\\\\", [["x"]]]', max_depth=2)


def test_scan_leaves_an_unterminated_string_to_the_json_parser():
    check_depth('["abc', max_depth=2)  # no nesting beyond the limit is seen; json.loads refuses the text itself
    with pytest.raises(ValueError):
        json.loads('["abc')


# ----------------------------------------------------------------------------------------------- inner payload_json
def test_inner_payload_json_nested_beyond_the_limit_is_refused_not_raised():
    with pytest.raises(ImportContractError) as caught:
        _decode_payload_json("[" * 200000 + "]" * 200000, "x.payload_json")
    assert caught.value.code == "input_too_deep"


def test_inner_payload_json_must_still_decode_to_an_object_and_a_valid_one_decodes():
    assert _decode_payload_json('{"a": {"b": [1, 2, {"c": null}]}}', "x") == {"a": {"b": [1, 2, {"c": None}]}}
    nested = {"k": 1}
    for _ in range(100):
        nested = {"k": nested}
    assert _decode_payload_json(json.dumps(nested), "x") == nested
    with pytest.raises(ImportContractError):
        _decode_payload_json("[1]", "x")


def test_inner_claim_json_nested_beyond_the_limit_is_refused_as_corrupt():
    from agent_replay_bundle.w3_c8_lineage import C8LineageError, import_c8_source
    from .test_w3_c8_lineage import data
    x = data()
    x["rows"]["execution_claims_v1"][0]["claim_json"] = "[" * 200000 + "]" * 200000
    with pytest.raises(C8LineageError):
        import_c8_source(authority=x)


# ------------------------------------------------------------------------------------------------- matcher budget
def crowded(cp, copies):
    """Add ``copies`` completed journals of the first check and as many separately recorded checks with the same content."""
    base = [e for e in cp["check_events"] if e["check_id"] == cp["check_events"][0]["check_id"]]
    check = next(x for x in cp["resolution_checks"] if x["stage"] == base[0]["stage"])
    for n in range(copies):
        cp["check_events"].extend(dict(copy.deepcopy(e), check_id=f"crowd-{n}") for e in base)
        cp["resolution_checks"].append(dict(copy.deepcopy(check), check_id=f"crowd-check-{n}"))
    return cp


def test_valid_run_with_many_identical_checks_is_accepted():
    revision = JOURNAL_REVISIONS[-1]
    cp, proposal, executor = load(EXECUTOR[revision])
    crowded(cp, 300)
    started = time.perf_counter()
    bundle = run(cp, proposal, executor, revision)
    assert time.perf_counter() - started < 10
    assert bundle.status == "reconstruction_complete"


def test_a_crowd_of_identical_checks_beyond_the_work_budget_is_refused_with_a_code_and_quickly():
    out = _in_child(f"""
        import sys, time
        sys.path.insert(0, {str(ROOT)!r})
        from tests.test_refusal_journal import EXECUTOR, JOURNAL_REVISIONS, load, run
        from tests.test_scan_and_matching_bounds import crowded
        from agent_replay_bundle import ImportContractError
        revision = JOURNAL_REVISIONS[-1]
        cp, proposal, executor = load(EXECUTOR[revision])
        crowded(cp, 1500)
        started = time.perf_counter()
        try:
            run(cp, proposal, executor, revision)
            print("accepted", round(time.perf_counter() - started, 1))
        except ImportContractError as exc:
            print(exc.code, round(time.perf_counter() - started, 1))
    """, limit=90)
    assert out is not None, "matching did not finish within 90 s"
    code, seconds = out.split()
    assert code == "input_too_large" and float(seconds) < 60
