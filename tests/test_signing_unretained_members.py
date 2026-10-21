"""``arb verify`` refuses a signed file that carries members the models do not retain (the HMAC does not cover them)."""
import json

from agent_replay_bundle.models import SignedReplayBundle
from agent_replay_bundle.loader import load_replay_bundle
from agent_replay_bundle.signing import sign_replay_bundle

from .test_input_bounds import VALID, run_arb
from .test_signing import make_bundle


def _write(tmp_path, change=None):
    signed = sign_replay_bundle(load_replay_bundle(VALID), "s3", key_id="k")
    data = json.loads(signed.model_dump_json())
    if change:
        change(data)
    p = tmp_path / "signed.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_control_clean_signed_file_verifies(tmp_path):
    rc, out, _ = run_arb("verify", str(_write(tmp_path)), "--secret", "s3")
    assert rc == 0 and "Signature VALID" in out


def test_extra_member_in_inner_bundle_is_invalid(tmp_path):
    p = _write(tmp_path, lambda d: d["replay_bundle"]["frame"].update(approved_by="CFO"))
    rc, out, _ = run_arb("verify", str(p), "--secret", "s3")
    assert rc == 1 and "INVALID" in out and "approved_by" in out and "VALID" not in out.replace("INVALID", "")


def test_extra_member_in_list_item_is_invalid(tmp_path):
    def change(d):
        d["replay_bundle"]["action_proposals"][0]["extra_unsigned"] = {"amount": 1}
    rc, out, _ = run_arb("verify", str(_write(tmp_path, change)), "--secret", "s3")
    assert rc == 1 and "action_proposals[0].extra_unsigned" in out


def test_extra_top_level_member_is_invalid(tmp_path):
    rc, out, _ = run_arb("verify", str(_write(tmp_path, lambda d: d.update(note="x"))), "--secret", "s3")
    assert rc == 1 and "$.note" in out


def test_free_form_members_are_retained_and_not_flagged(tmp_path):
    def change(d):
        d["replay_bundle"]["metadata"] = {"anything": {"nested": [1, 2]}}
    signed = sign_replay_bundle(make_bundle(), "s3")
    data = json.loads(signed.model_dump_json())
    change(data)
    # re-sign so the free-form metadata is covered
    bundle = SignedReplayBundle.model_validate(data).replay_bundle
    signed = sign_replay_bundle(bundle, "s3")
    p = tmp_path / "s.json"
    p.write_text(signed.model_dump_json(), encoding="utf-8")
    rc, out, _ = run_arb("verify", str(p), "--secret", "s3")
    assert rc == 0 and "Signature VALID" in out


def test_unretained_members_reports_paths():
    from agent_replay_bundle.signing import unretained_members

    signed = sign_replay_bundle(make_bundle(), "s3")
    dump = signed.model_dump(mode="json")
    raw = json.loads(json.dumps(dump))
    raw["replay_bundle"]["x"] = 1
    assert unretained_members(raw, dump) == ["$.replay_bundle.x"]
    assert unretained_members(dump, dump) == []


def _rule_matched_file(tmp_path, value):
    """A signed file whose first evaluated rule was signed with ``matched: false``, then edited to ``value``."""
    bundle = load_replay_bundle(VALID)
    bundle.policy_traces[0].rules_evaluated[0].matched = False
    signed = sign_replay_bundle(bundle, "s3", key_id="k")
    data = json.loads(signed.model_dump_json())
    data["replay_bundle"]["policy_traces"][0]["rules_evaluated"][0]["matched"] = value
    p = tmp_path / "coerced.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_control_signed_false_verifies(tmp_path):
    rc, out, _ = run_arb("verify", str(_rule_matched_file(tmp_path, False)), "--secret", "s3")
    assert rc == 0 and "Signature VALID" in out


def test_scalar_edited_to_a_coercible_value_is_invalid(tmp_path):
    for value in ("false", 0, "False", "no"):
        rc, out, _ = run_arb("verify", str(_rule_matched_file(tmp_path, value)), "--secret", "s3")
        assert rc == 1 and "Signature INVALID" in out and "matched[value]" in out, (value, out)


def test_unretained_members_compares_scalar_type_and_value():
    from agent_replay_bundle.signing import unretained_members

    assert unretained_members({"a": "false"}, {"a": False}) == ["$.a[value]"]
    assert unretained_members({"a": 0}, {"a": False}) == ["$.a[value]"]
    assert unretained_members({"a": True}, {"a": 1}) == ["$.a[value]"]
    assert unretained_members({"a": "x"}, {"a": "y"}) == ["$.a[value]"]
    assert unretained_members({"a": None}, {"a": ""}) == ["$.a[value]"]
    assert unretained_members({"a": [1, "2"]}, {"a": [1, 2]}) == ["$.a[1][value]"]
    # an integer and a float of the same value are the same JSON number
    assert unretained_members({"a": 1}, {"a": 1.0}) == []
    assert unretained_members({"a": False, "b": None, "c": "s", "d": 2}, {"a": False, "b": None, "c": "s", "d": 2}) == []
