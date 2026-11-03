"""Replay-1 (finding csf_fd59316cadb886433f1e97ec): one JSON-semantic equality for value bindings.

Python ``==`` equates ``True``/``1``, ``False``/``0.0`` and ``[True]``/``[1]``; a boolean could stand in for a number in a
value bound to a committed operation. These tests pin the helper semantics, the routed binding sites and the w3 lineage
(no ``str()`` bridge). Canonical serialization is not touched and is pinned by the golden digests below."""
import ast
import copy
import json
from pathlib import Path

import pytest

import agent_replay_bundle.importers as I
from agent_replay_bundle.importers import ImportContractError, import_bounded_workflow, _sha256
from agent_replay_bundle.json_equality import NonJsonValue, json_contains, json_equal, json_key, MAX_NODES
from agent_replay_bundle.w3_c8_lineage import C8LineageError, import_c8_source
from tests import test_importers as T
from tests.test_w3_c8_lineage import data as c8_data

SRC = Path(I.__file__).parent

# pairs Python == equates but JSON does not
COERCIVE = [
    ("bool/int true", True, 1), ("bool/int false", False, 0),
    ("bool/float true", True, 1.0), ("bool/float false/-0.0", False, -0.0),
    ("nested list", [1, [True]], [1, [1]]),
    ("nested object", {"a": {"b": False}}, {"a": {"b": 0}}),
    ("list in object", {"k": [True, 0.0]}, {"k": [1, False]}),
]
# pairs both Python and JSON consider different
DIFFERENT = [
    ("string/number", "1", 1), ("string/float", "1.0", 1.0), ("string/bool", "true", True), ("string/bool false", "", False),
    ("null/false", None, False), ("null/zero", None, 0), ("null/empty string", None, ""),
    ("missing vs null member", {"a": None}, {}), ("extra member", {"a": 1}, {"a": 1, "b": 2}),
    ("different key", {"a": 1}, {"b": 1}), ("array length", [1], [1, 1]), ("array order", [1, 2], [2, 1]),
    ("object vs array", {}, []), ("empty string vs empty list", "", []),
]
EQUAL = [
    ("int/float", 50, 50.0), ("zero/-0.0", 0, -0.0), ("0.0/-0.0", 0.0, -0.0), ("0/0.0", 0, 0.0),
    ("nested numeric", [1, {"x": 2.0}], [1.0, {"x": 2}]), ("list/tuple", [1, ["a"]], (1, ("a",))),
    ("key order", {"a": 1, "b": 2}, {"b": 2, "a": 1}),
    ("identical", {"a": [None, True, "s", 1.5]}, {"a": [None, True, "s", 1.5]}),
]


class TestHelperSemantics:
    @pytest.mark.parametrize("label,a,b", COERCIVE, ids=[c[0] for c in COERCIVE])
    def test_python_equal_but_not_json_equal(self, label, a, b):
        assert (a == b) is True
        assert json_equal(a, b) is False and json_equal(b, a) is False

    @pytest.mark.parametrize("label,a,b", DIFFERENT, ids=[c[0] for c in DIFFERENT])
    def test_different(self, label, a, b):
        assert json_equal(a, b) is False and json_equal(b, a) is False

    @pytest.mark.parametrize("label,a,b", EQUAL, ids=[c[0] for c in EQUAL])
    def test_positive_controls(self, label, a, b):
        assert json_equal(a, b) is True and json_equal(b, a) is True
        assert json_key(a) == json_key(b)

    def test_numbers_are_compared_exactly(self):
        assert not json_equal(2**53 + 1, float(2**53))
        assert json_equal(2**53, float(2**53))
        assert not json_equal(10**400, 1e308)
        assert not json_equal(0.1 + 0.2, 0.3)

    def test_json_key_distinguishes_what_json_equal_distinguishes(self):
        for _, a, b in COERCIVE + DIFFERENT:
            assert json_key(a) != json_key(b)
        assert json_key(0) == json_key(-0.0) == json_key(0.0)

    def test_contains(self):
        assert json_contains({"a": 1.0}, [{"a": 1}, 2])
        assert not json_contains({"a": True}, [{"a": 1}])
        assert not json_contains(True, [1, 1.0])

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
    def test_non_finite_numbers_refused(self, bad):
        for a, b in ((bad, 1), (1, bad), ([bad], [bad]), ({"k": bad}, {"k": 1})):
            with pytest.raises(NonJsonValue):
                json_equal(a, b)

    @pytest.mark.parametrize("bad", [b"x", {1}, object(), {1: "a"}, complex(1, 0), frozenset()])
    def test_non_json_operands_refused(self, bad):
        with pytest.raises(NonJsonValue):
            json_equal(bad, bad)
        with pytest.raises(NonJsonValue):
            json_equal([bad], [1])

    def test_non_json_refused_even_when_the_rest_already_differs(self):
        # a typed refusal, never a plain False, and never a False hiding an unvalidated member
        with pytest.raises(NonJsonValue):
            json_equal([1, b"x"], [2, 2])
        with pytest.raises(NonJsonValue):
            json_equal({"a": 1, "b": {1}}, {"a": 2})

    def test_subclasses_of_json_types_refused(self):
        class S(str): pass
        class I_(int): pass
        class D(dict): pass
        for bad in (S("x"), I_(1), D()):
            with pytest.raises(NonJsonValue):
                json_equal(bad, bad)

    def test_list_and_tuple_compare_only_after_members_are_valid(self):
        assert json_equal([1, 2], (1, 2))
        with pytest.raises(NonJsonValue):
            json_equal([1, {2}], (1, {2}))

    def test_duplicate_members_are_refused_at_parse_time_and_missing_is_not_null(self, tmp_path):
        from agent_replay_bundle.ingress import DuplicateMemberError, load_json_bounded
        path = tmp_path / "dup.json"
        path.write_text('{"effects": 1, "effects": true}', encoding="utf-8")
        with pytest.raises(DuplicateMemberError):
            load_json_bounded(path)
        assert not json_equal({"effects": None}, {})

    def test_deep_nesting_and_node_budget(self):
        def deep(n):
            root = cur = []
            for _ in range(n):
                nxt = []
                cur.append(nxt)
                cur = nxt
            return root
        assert json_equal(deep(100_000), deep(100_000))
        assert not json_equal(deep(100_000), deep(99_999))
        with pytest.raises(NonJsonValue):
            json_equal(list(range(MAX_NODES + 1)), [])

    def test_does_not_mutate_operands(self):
        a = {"a": [1, {"b": True}]}
        before = copy.deepcopy(a)
        json_equal(a, copy.deepcopy(a))
        assert a == before


class TestPrimitiveSites:
    @pytest.mark.parametrize("label,a,b", COERCIVE, ids=[c[0] for c in COERCIVE])
    def test_require_equal_refuses_contradictory_json_types(self, label, a, b):
        with pytest.raises(ImportContractError):
            I._require_equal(a, b, "p")

    @pytest.mark.parametrize("label,a,b", EQUAL, ids=[c[0] for c in EQUAL])
    def test_require_equal_accepts_equal_values(self, label, a, b):
        I._require_equal(a, b, "p")

    @pytest.mark.parametrize("label,a,b", DIFFERENT, ids=[c[0] for c in DIFFERENT])
    def test_require_equal_refuses_different_values(self, label, a, b):
        with pytest.raises(ImportContractError):
            I._require_equal(a, b, "p")

    def test_require_equal_keeps_the_callers_refusal_code(self):
        with pytest.raises(ImportContractError) as info:
            I._require_equal(True, 1, "p", "result_binding_mismatch")
        assert info.value.code == "result_binding_mismatch"

    def test_require_equal_non_json_operand_is_typed_refusal(self):
        with pytest.raises(ImportContractError) as info:
            I._require_equal(b"x", b"x", "p")
        assert info.value.code == "schema_violation"
        with pytest.raises(ImportContractError) as info:
            I._require_equal(float("nan"), float("nan"), "p", "result_binding_mismatch")
        assert info.value.code == "result_binding_mismatch"

    def test_unique_or_same(self):
        seen = {}
        I._unique_or_same(seen, "k", {"approved": 1, "n": [True]}, "x")
        I._unique_or_same(seen, "k", {"n": [True], "approved": 1.0}, "x")  # same content
        with pytest.raises(ImportContractError):
            I._unique_or_same(seen, "k", {"approved": True, "n": [True]}, "x")
        with pytest.raises(ImportContractError):
            I._unique_or_same(seen, "k", {"approved": 1, "n": [1]}, "x")

    def test_has_equal_rows(self):
        assert I._has_equal_rows([{"a": 1}, {"a": True}]) is False
        assert I._has_equal_rows([{"a": 1}, {"a": "1"}]) is False
        assert I._has_equal_rows([{"a": 1}, {"a": 1.0}]) is True
        assert I._has_equal_rows([{"a": [1, 2]}, {"a": (1, 2)}]) is True
        assert I._has_equal_rows([{"a": 0}, {"a": -0.0}]) is True
        assert I._has_equal_rows([]) is False
        with pytest.raises(ImportContractError):
            I._has_equal_rows([{"a": {1}}, {"a": 2}])


def _binding(cp):
    return cp["decisions"][0]["binding"]


def _import(mutate, with_moltbot=True):
    cp = T.bounded_source()
    proposal = T.proposal_source()
    moltbot = T.moltbot_source(cp) if with_moltbot else None
    mutate(cp, proposal, moltbot)
    return import_bounded_workflow(cp, proposal=proposal, moltbot_export=moltbot)


def _refix_operation_digest(moltbot):
    digest = _sha256(moltbot["execution_envelope"]["operation"])
    moltbot["attempts"][0]["operation_digest"] = digest
    moltbot["effects"][0]["operation_digest"] = digest


class TestImportBoundedWorkflow:
    def test_valid_import_accepted(self):
        _import(lambda c, p, m: None)

    @pytest.mark.parametrize("value", [True, "1"])
    def test_binding_effects_must_equal_the_proposal(self, value):
        with pytest.raises(ImportContractError):
            _import(lambda c, p, m: _binding(c).__setitem__("effects", value), with_moltbot=False)

    @pytest.mark.parametrize("field,value", [("effects", True), ("effective_max_effects", True),
                                             ("effects", "1"), ("effective_max_effects", 1.5)])
    def test_operation_effects_must_equal_the_commitment(self, field, value):
        def mutate(c, p, m):
            m["execution_envelope"]["operation"][field] = value
            _refix_operation_digest(m)
        with pytest.raises(ImportContractError):
            _import(mutate)

    def test_binding_amount_bool_is_refused(self):
        with pytest.raises(ImportContractError):
            _import(lambda c, p, m: _binding(c).__setitem__("amount", True), with_moltbot=False)

    def test_int_float_numeric_equivalence_is_still_accepted(self):
        _import(lambda c, p, m: _binding(c).__setitem__("effects", 1.0), with_moltbot=False)

    def test_golden_digests_unchanged(self):
        # canonical serialization is not altered by this change
        assert _sha256(T.proposal_source()).startswith("sha256:51d05130")
        assert _sha256(T.proposal_source()).endswith("2bb0")
        binding = _sha256(_binding(T.bounded_source()))
        assert binding.startswith("sha256:bd56c9af") and binding.endswith("e34")


class TestW3C8Lineage:
    @staticmethod
    def run(mutate):
        x = c8_data()
        mutate(x)
        return import_c8_source(authority=x)

    @staticmethod
    def claim(x, **changes):
        row = x["rows"]["execution_claims_v1"][0]
        raw = json.loads(row["claim_json"])
        raw.update(changes)
        row["claim_json"] = json.dumps(raw)

    def test_positive_control(self):
        self.run(lambda x: None)

    def test_numeric_claim_json_revision_never_equals_string_row_revision(self):
        with pytest.raises(C8LineageError):
            self.run(lambda x: self.claim(x, grant_revision=1))

    def test_numeric_grant_row_revision_never_equals_string_claim_revision(self):
        with pytest.raises(C8LineageError):
            self.run(lambda x: x["rows"]["authority_grants_v1"][0].__setitem__("revision", 1))

    @pytest.mark.parametrize("value", [1.0, True, None])
    def test_other_revision_types_refused(self, value):
        with pytest.raises(C8LineageError):
            self.run(lambda x: x["rows"]["authority_grants_v1"][0].__setitem__("revision", value))

    def test_numeric_revision_on_both_sides_is_consistent(self):
        def mutate(x):
            x["rows"]["execution_claims_v1"][0]["grant_revision"] = 1
            self.claim(x, grant_revision=1)
            x["rows"]["authority_grants_v1"][0]["revision"] = 1
        self.run(mutate)
        def mutate_float(x):
            mutate(x)
            x["rows"]["authority_grants_v1"][0]["revision"] = 1.0
        self.run(mutate_float)  # JSON number equivalence

    def test_policy_version_string_never_equals_number(self):
        def mutate(x):
            raw = json.loads(x["rows"]["execution_claims_v1"][0]["claim_json"])
            raw["policy_state"] = [{"ref": "p", "version": 1}]
            x["rows"]["execution_claims_v1"][0]["claim_json"] = json.dumps(raw)
        with pytest.raises(C8LineageError):
            self.run(mutate)

    def test_non_json_revision_is_typed_refusal(self):
        with pytest.raises(C8LineageError):
            self.run(lambda x: x["rows"]["authority_grants_v1"][0].__setitem__("revision", {1}))


class TestScopeLint:
    """Low-risk AST guards: the routed primitives stay free of Python ``==``/``!=``/``in`` on values, and the str() bridge stays removed."""

    @staticmethod
    def _function(path, name):
        tree = ast.parse((SRC / path).read_text(encoding="utf-8"))
        return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)

    @pytest.mark.parametrize("name", ["_require_equal", "_unique_or_same", "_json_same", "_json_in"])
    def test_routed_primitives_use_no_python_value_equality(self, name):
        fn = self._function("importers.py", name)
        ops = [type(op).__name__ for n in ast.walk(fn) if isinstance(n, ast.Compare) for op in n.ops]
        assert not {"Eq", "NotEq", "In", "NotIn"} & set(ops), (name, ops)

    def test_c8_lineage_has_no_str_bridge(self):
        tree = ast.parse((SRC / "w3_c8_lineage.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                for sub in ast.walk(node):
                    assert not (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == "str"), ast.dump(node)[:120]


class TestRouteBReceiptBinding:
    """The route B authority receipt is bound to the committed operation's grant_revision by JSON-semantic equality."""

    @staticmethod
    def _check(op_revision, receipt_revision):
        profile = I.ROUTE_B_AUTHORITY_PROFILE
        evidence = {"local_authority_effect_profile": profile, "claim_id": "claim-1", "linearized_at": "2026-01-01T00:00:00Z",
                    "authority_receipt": {"attempt_id": "a1", "effect_id": "e1", "decision_id": "d1", "claim_id": "claim-1",
                                          "grant_id": "g1", "grant_revision": receipt_revision, "profile": profile,
                                          "grant_status": "active"}}
        result = {"status": "executed", "attempted": True, "acknowledged": True, "newly_executed": True, "attempt_id": "a1"}
        op = {"grant_id": "g1", "grant_revision": op_revision}
        I._validate_route_b_execution_evidence(evidence, result, "e1", "d1", op)

    @pytest.mark.parametrize("op_revision,receipt_revision", [(1, 1), (1, 1.0), ("1", "1")])
    def test_positive_controls(self, op_revision, receipt_revision):
        self._check(op_revision, receipt_revision)

    @pytest.mark.parametrize("op_revision,receipt_revision", [(1, True), (True, 1), (0, False), (1, "1"), ("1", 1),
                                                              (None, None), (1, None), (1, {1})])
    def test_receipt_revision_type_confusion_is_refused(self, op_revision, receipt_revision):
        with pytest.raises(ImportContractError):
            self._check(op_revision, receipt_revision)


def test_c8_policy_key_depth_is_a_typed_refusal():
    def deep(n):
        root = cur = []
        for _ in range(n):
            nxt = []
            cur.append(nxt)
            cur = nxt
        return root
    x = c8_data()
    raw = json.loads(x["rows"]["execution_claims_v1"][0]["claim_json"])
    x["rows"]["authority_policies_v1"][0]["version"] = deep(20_000)
    with pytest.raises(C8LineageError):
        import_c8_source(authority=x)
