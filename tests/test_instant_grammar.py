"""Strict instant grammar at every place Replay reads a time: ``YYYY-MM-DDThh:mm:ss[.f]`` then ``Z`` or ``+hh:mm``/``-hh:mm``.

Upper-case ``T``, ASCII digits, seconds present, one to six fraction digits, hour 00 to 23, a real calendar date, an offset.
"""
import pytest

from agent_replay_bundle import ImportContractError
from agent_replay_bundle import importers, programme2_profiles as p2, recovery_inspection as ri

VALID = ["2026-01-01T00:00:00Z", "2026-10-05T19:00:00+00:00", "2026-10-05T19:00:00-07:30", "2026-01-01T23:59:59.1Z",
         "2026-01-01T23:59:59.123456+14:00", "2024-02-29T12:00:00Z"]
INVALID = {
    "hour-24": "2026-01-01T24:00:00Z",
    "seventh-fraction-digit": "2026-01-01T00:00:00.1234567Z",
    "space-separator": "2026-01-01 00:00:00Z",
    "week-date": "2026-W01-4T00:00:00Z",
    "ordinal-date": "2026-001T00:00:00Z",
    "compact": "20260101T000000Z",
    "lower-case-t": "2026-01-01t00:00:00Z",
    "lower-case-z": "2026-01-01T00:00:00z",
    "no-seconds": "2026-01-01T00:00Z",
    "leap-second": "2026-01-01T00:00:60Z",
    "short-offset": "2026-01-01T00:00:00+00",
    "compact-offset": "2026-01-01T00:00:00+0000",
    "offset-hour-24": "2026-01-01T00:00:00+24:00",
    "naive": "2026-01-01T00:00:00",
    "trailing-newline": "2026-01-01T00:00:00Z\n",
    "leading-space": " 2026-01-01T00:00:00Z",
    "non-ascii-digits": "٢٠٢٦-01-01T00:00:00Z",
    "empty-fraction": "2026-01-01T00:00:00.Z",
    "impossible-date": "2026-02-30T00:00:00Z",
    "not-leap-year": "2026-02-29T00:00:00Z",
    "year-zero": "0000-01-01T00:00:00Z",
    "not-text": 20260101,
}

SITES = {
    "importers-aware-time": importers._aware_time,
    "profiles-instant": lambda v: p2.instant(v, "probe"),
    "recovery-inspection-time": ri._time,
}


def refuses(fn, value):
    try:
        fn(value)
    except Exception:
        return True
    return False


@pytest.mark.parametrize("site", sorted(SITES))
@pytest.mark.parametrize("form", sorted(INVALID))
def test_malformed_instant_is_refused(site, form):
    assert refuses(SITES[site], INVALID[form])


@pytest.mark.parametrize("site", sorted(SITES))
@pytest.mark.parametrize("value", VALID)
def test_valid_instant_is_accepted(site, value):
    assert not refuses(SITES[site], value)


def test_a_malformed_instant_in_a_retained_row_is_a_refusal_with_the_timestamp_code():
    from .test_programme2_profiles import mutate, refused, first
    for form in ("hour-24", "seventh-fraction-digit", "space-separator", "week-date"):
        refused(mutate("merge-folded-operation-dispatches-under-survivor",
                       lambda cp: first(cp["merge_records"]).update(recorded_at=INVALID[form])), "timestamp_invalid")


@pytest.mark.parametrize("form", ["hour-24", "seventh-fraction-digit", "space-separator", "week-date", "naive"])
def test_route_b_linearized_at_follows_the_same_grammar(form):
    from .test_route_b_recovery_import import EXECUTED, _both_evidence, rejects
    rejects(EXECUTED, lambda x: _both_evidence(x, lambda e: e.__setitem__("linearized_at", INVALID[form])), "invalid route B linearized_at")


def test_route_b_linearized_at_valid_form_is_accepted():
    from .test_route_b_recovery_import import EXECUTED, _both_evidence, planted
    for value in ("2026-10-07T16:00:00+00:00", "2026-10-07T16:00:00.5Z"):
        planted(EXECUTED, lambda x: _both_evidence(x, lambda e: e.__setitem__("linearized_at", value)))
