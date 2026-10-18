"""Hardening checks from the 2026-10 security review: survivor binding, HMAC value shape, input bounds, terminal-safe output."""
import copy
import subprocess
import sys

import pytest

from agent_replay_bundle import ImportContractError, import_bounded_workflow
from agent_replay_bundle import importers
from agent_replay_bundle.reconstruction import verify_reconstruction_hmac
from agent_replay_bundle.signing import is_hex_digest

from .test_programme2_profiles import P2, first, mutate, refused, run

FOLDED = "merge-folded-operation-dispatches-under-survivor"


def test_join_merged_into_must_name_the_recorded_survivor():
    def to_third_admitted_operation(cp):
        third = copy.deepcopy(cp["operations"][0])
        third["operation_id"] = "op-unrelated/third"
        cp["operations"].append(third)
        first(cp["attempt_joins"], operation_id="op-order-100/refund-2")["merged_into"] = third["operation_id"]

    refused(mutate(FOLDED, to_third_admitted_operation), "merged_into_survivor_mismatch")


def test_recorded_survivor_still_accepted():
    import_bounded_workflow(run(FOLDED), control_plane_revision=P2)


@pytest.mark.parametrize("value", ["", "zz", "A" * 64, "a" * 63, "a" * 65, "é" * 64, "٣" * 64, ("a" * 64) + "\n"])
def test_hmac_value_shape(value):
    assert not is_hex_digest(value)


def test_hmac_value_shape_accepts_lowercase_sha256_hex():
    assert is_hex_digest("0123456789abcdef" * 4)


def _signed_bundle():
    from .test_importers import sign_reconstruction_bundle
    bundle = import_bounded_workflow(run(FOLDED), control_plane_revision=P2)
    return sign_reconstruction_bundle(bundle, "secret", key_id="k")


def test_reconstruction_hmac_verifies_then_rejects_non_hex_value():
    signed = _signed_bundle()
    assert verify_reconstruction_hmac(signed, "secret") is True
    for bad in (signed.integrity[-1].value.upper(), "é" * 64, signed.integrity[-1].value + "\n"):
        tampered = signed.model_copy(deep=True)
        tampered.integrity[-1].value = bad
        assert verify_reconstruction_hmac(tampered, "secret") is False


def _deep(depth):
    value = []
    for _ in range(depth):
        value = [value]
    return value


def test_dict_api_refuses_too_deep_input():
    cp = copy.deepcopy(run(FOLDED))
    cp["x-deep"] = _deep(importers.MAX_RECORD_DEPTH + 5)
    with pytest.raises(ImportContractError) as info:
        import_bounded_workflow(cp, control_plane_revision=P2)
    assert info.value.code == "input_too_deep"


def test_dict_api_refuses_oversized_list(monkeypatch):
    monkeypatch.setattr(importers, "MAX_RECORD_LIST_LENGTH", 10)
    cp = copy.deepcopy(run(FOLDED))
    cp["decisions"] = cp["decisions"] * 20
    with pytest.raises(ImportContractError) as info:
        import_bounded_workflow(cp, control_plane_revision=P2)
    assert info.value.code == "input_too_large"


def test_dict_api_refuses_too_many_nodes(monkeypatch):
    monkeypatch.setattr(importers, "MAX_RECORD_NODES", 50)
    with pytest.raises(ImportContractError) as info:
        import_bounded_workflow(copy.deepcopy(run(FOLDED)), control_plane_revision=P2)
    assert info.value.code == "input_too_large"


def test_cli_escapes_control_characters_in_bundle_text(tmp_path):
    from agent_replay_bundle.cli import _t

    out = _t("a\x1b[31mred\x07\r\nb")
    assert "\x1b" not in out and "\x07" not in out and "\r" not in out
