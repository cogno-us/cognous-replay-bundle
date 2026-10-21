"""Wave 7 (T1-D): overflowing float literals, non-finite `num` values and non-finite canonical dumps are refused."""
import pytest

from agent_replay_bundle import programme2_profiles as p2
from agent_replay_bundle.ingress import NonFiniteNumberError, load_json_bounded
from agent_replay_bundle.signing import canonical_bundle_json, canonical_envelope_bytes


@pytest.mark.parametrize("text", [
    '{"a": 1e999}', '{"b": -1e999}', '{"c": [1E400]}', '{"d": 1.5e+9999}', '{"n": {"x": [0, -2E999]}}',
])
def test_overflowing_float_literal_refused(tmp_path, text):
    path = tmp_path / "i.json"
    path.write_text(text)
    with pytest.raises(NonFiniteNumberError):
        load_json_bounded(path)


def test_finite_floats_still_load(tmp_path):
    path = tmp_path / "i.json"
    path.write_text('{"a": 1e300, "b": -2.5, "c": 0.0, "d": 7}')
    assert load_json_bounded(path) == {"a": 1e300, "b": -2.5, "c": 0.0, "d": 7}


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_num_kind_requires_finite(value):
    with pytest.raises(Exception):
        p2._check_kind(value, "num", "field")


def test_num_kind_accepts_finite():
    p2._check_kind(1.5, "num", "field")
    p2._check_kind(0, "num", "field")


class _Dump:
    def __init__(self, data):
        self._data = data

    def model_dump(self, mode="json"):
        return dict(self._data)


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_canonical_dumps_refuse_non_finite(value):
    with pytest.raises(ValueError):
        canonical_bundle_json(_Dump({"x": value}))
    with pytest.raises(ValueError):
        canonical_envelope_bytes("id", _Dump({"k": "v"}), _Dump({"x": value}))
