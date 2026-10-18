"""Merge records read in time order: an operation is folded once, a survivor is not already folded, a chain of folds is accepted.

Valid cases are the captured real record ``merge-folded-operation-dispatches-under-survivor`` plus merge rows added to it;
every refused case is one such addition.
"""
import copy

import pytest

from .test_programme2_profiles import do_import, first, refused, run

NAME = "merge-folded-operation-dispatches-under-survivor"
O0, O1, O2, O3 = "op-order-100/refund-0", "op-order-100/refund-1", "op-order-100/refund-2", "op-order-100/refund-3"
T0, T1, T2 = "2026-10-05T18:59:59+00:00", "2026-10-05T19:00:00+00:00", "2026-10-05T19:00:01+00:00"


def record():
    return copy.deepcopy(run(NAME))


def admit(cp, *operation_ids):
    for operation_id in operation_ids:
        row = copy.deepcopy(cp["operations"][0])
        row["operation_id"] = operation_id
        cp["operations"].append(row)


def merge(cp, merge_id, survivor, folded, recorded_at=None, **members):
    row = copy.deepcopy(cp["merge_records"][0])
    row.update(merge_id=merge_id, survivor_operation_id=survivor, folded_operation_ids=folded, **members)
    if recorded_at:
        row["recorded_at"] = recorded_at
    cp["merge_records"].append(row)


# ----------------------------------------------------------------------------------------------------- accepted
def test_control_the_captured_record_is_accepted():
    do_import(record())


def test_control_a_chain_of_folds_in_time_order_is_accepted_whatever_the_row_order():
    """refund-3 into refund-2 (earlier), then refund-2 into refund-1 (later): the second row is listed first."""
    cp = record()
    admit(cp, O3)
    cp["merge_records"][0]["recorded_at"] = T2
    merge(cp, "merge-earlier", O2, [O3], T1)
    do_import(cp)


def test_control_two_separate_folds_into_one_survivor_are_accepted():
    cp = record()
    admit(cp, O3)
    merge(cp, "merge-second", O1, [O3], T2)
    do_import(cp)


@pytest.mark.parametrize("outcome,reasons", [("refused", ["merge_operation_already_folded"]), ("held", ["merge_authority_unfunded"])])
def test_control_a_row_without_effect_does_not_count_as_a_fold(outcome, reasons):
    cp = record()
    admit(cp, O3)
    merge(cp, "merge-no-effect", O3, [O2], T2, outcome=outcome, reasons=reasons)
    do_import(cp)


def test_control_a_join_may_name_the_survivor_or_the_root_of_a_chain():
    """refund-2 was folded into refund-1, which is later folded into refund-0: a join written after both names refund-0."""
    for target in (O1, O0):
        cp = record()
        admit(cp, O0)
        merge(cp, "merge-chain", O0, [O1], T2)
        first(cp["attempt_joins"], operation_id=O2)["merged_into"] = target
        do_import(cp)


def test_control_records_with_one_timestamp_are_accepted_in_any_row_order_that_has_a_valid_history():
    """Equal timestamps carry no order: refund-3 into refund-2 and refund-2 into refund-1, listed in either order."""
    for survivor_first in (True, False):
        cp = record()
        admit(cp, O3)
        merge(cp, "merge-tied", O2, [O3])  # same recorded_at as the captured row
        if survivor_first:
            cp["merge_records"].reverse()
        do_import(cp)


# ----------------------------------------------------------------------------------------------------- refused
def test_a_cycle_among_records_with_one_timestamp_is_refused():
    cp = record()
    merge(cp, "merge-tied-cycle", O2, [O1])  # same recorded_at as the captured row
    refused(cp, "merge_survivor_already_folded")


def test_an_operation_folded_twice_by_records_with_one_timestamp_is_refused():
    cp = record()
    admit(cp, O3)
    merge(cp, "merge-tied-second-fold", O3, [O2])
    refused(cp, "merge_operation_already_folded")


def test_a_fold_cycle_is_refused():
    cp = record()
    merge(cp, "merge-cycle", O2, [O1], T2)
    refused(cp, "merge_survivor_already_folded")


def test_a_longer_cycle_is_refused():
    cp = record()
    admit(cp, O3)
    merge(cp, "merge-a", O3, [O2], T0)       # 2 -> 3
    merge(cp, "merge-b", O1, [O3], T0)       # 3 -> 1, and the captured row folds 2 into 1 as well
    refused(cp, "merge_operation_already_folded")
    cp = record()
    admit(cp, O3)
    cp["merge_records"][0].update(survivor_operation_id=O2, folded_operation_ids=[O1])   # 1 -> 2
    merge(cp, "merge-b", O3, [O2], T2)       # 2 -> 3
    merge(cp, "merge-c", O1, [O3], T2)       # 3 -> 1
    refused(cp, "merge_survivor_already_folded")


def test_an_operation_folded_into_two_survivors_is_refused():
    cp = record()
    admit(cp, O3)
    merge(cp, "merge-second-fold", O3, [O2], T2)
    refused(cp, "merge_operation_already_folded")


def test_an_operation_folded_twice_into_the_same_survivor_is_refused():
    cp = record()
    merge(cp, "merge-repeat", O1, [O2], T2)
    refused(cp, "merge_operation_already_folded")


def test_a_survivor_that_was_already_folded_is_refused():
    """refund-2 is folded into refund-1 first, then refund-3 is folded into refund-2."""
    cp = record()
    admit(cp, O3)
    merge(cp, "merge-late", O2, [O3], T2)
    refused(cp, "merge_survivor_already_folded")


def test_a_join_naming_an_operation_outside_the_chain_is_still_refused():
    cp = record()
    admit(cp, O0, O3)
    merge(cp, "merge-other", O0, [O3], T2)
    first(cp["attempt_joins"], operation_id=O2)["merged_into"] = O0
    refused(cp, "merged_into_survivor_mismatch")
