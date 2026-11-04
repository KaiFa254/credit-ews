"""tests/test_target.py — the target TARGET_DPD30_90D follows every agreed rule.

WHAT:  (1) A tiny hand-made example where we KNOW the right answer for each snapshot,
       (2) rule checks on the generated small book.
WHY:   The label is what the model learns. A single wrong rule (labelling immature
       months as good, dropping paid-off customers, counting already-bad customers)
       silently biases every model and every validation number.
USAGE: pytest -v tests/test_target.py
"""

import pandas as pd

from ews.data.target import build_target

SNAPS = pd.date_range("2024-01-31", periods=8, freq="ME")
S = list(SNAPS.strftime("%Y-%m-%d"))


def _toy(dpd_by_month, segments=None, extra_rows=None):
    """One customer C1 with one loan L1 whose DPD follows `dpd_by_month` (None = no row that month)."""
    rows = [{"LOAN_ID": "L1", "SNAPSHOT_DATE": s, "DPD": d, "RESTRUCTURED_FLAG": 0,
             "ACCOUNT_STATUS": "ACTIVE"} for s, d in zip(S, dpd_by_month) if d is not None]
    lm = pd.DataFrame(rows + (extra_rows or []))
    loans = pd.DataFrame({"LOAN_ID": ["L1"], "CUSTOMER_ID": ["C1"]})
    cm = pd.DataFrame({"CUSTOMER_ID": "C1", "SNAPSHOT_DATE": S,
                       "SEGMENT_AT_SNAPSHOT": segments or ["250"] * len(S)})
    return build_target(lm, loans, cm, SNAPS).set_index("SNAPSHOT_DATE")


def test_hand_made_example_like_cell_8():
    # Same story as notebook cell 8: DPD 0, 0, 3, 0, 12, 35, 62, 90
    t = _toy([0, 0, 3, 0, 12, 35, 62, 90])
    assert t.loc[S[0], "TARGET_DPD30_90D"] == 0            # next 3 months worst = 3
    assert t.loc[S[1], "TARGET_DPD30_90D"] == 0            # next 3 months worst = 12
    assert t.loc[S[2], "TARGET_DPD30_90D"] == 1            # next 3 months worst = 35
    assert t.loc[S[3], "TARGET_DPD30_90D"] == 1            # next 3 months worst = 62
    assert t.loc[S[4], "TARGET_STATUS"] == "EXCLUDED_DPD"  # DPD 12 > 5 at the snapshot
    assert (t.loc[S[5:], "TARGET_STATUS"] != "LABELLED").all()   # already bad and/or immature


def test_last_three_months_are_immature():
    t = _toy([0] * 8)
    assert (t.loc[S[-3:], "TARGET_STATUS"] == "IMMATURE").all()
    assert t.loc[S[-3:], "TARGET_DPD30_90D"].isna().all()   # no label, NOT zero


def test_paid_off_customer_is_good_not_dropped():
    # Loan closes in month 2 with no arrears: later months have no loan rows at all.
    t = _toy([0, None, None, None, None, None, None, None],
             extra_rows=[{"LOAN_ID": "L1", "SNAPSHOT_DATE": S[1], "DPD": 0, "RESTRUCTURED_FLAG": 0,
                          "ACCOUNT_STATUS": "CLOSED"}])
    assert t.loc[S[0], "TARGET_STATUS"] == "LABELLED"
    assert t.loc[S[0], "TARGET_DPD30_90D"] == 0             # left the book cleanly -> good
    assert t.loc[S[2], "TARGET_STATUS"] == "EXCLUDED_NO_LOANS"


def test_restructure_counts_as_bad():
    lm_rows = [{"LOAN_ID": "L1", "SNAPSHOT_DATE": s, "DPD": 0, "RESTRUCTURED_FLAG": int(i == 2),
                "ACCOUNT_STATUS": "RESTRUCTURED" if i == 2 else "ACTIVE"} for i, s in enumerate(S)]
    loans = pd.DataFrame({"LOAN_ID": ["L1"], "CUSTOMER_ID": ["C1"]})
    cm = pd.DataFrame({"CUSTOMER_ID": "C1", "SNAPSHOT_DATE": S, "SEGMENT_AT_SNAPSHOT": "250"})
    t = build_target(pd.DataFrame(lm_rows), loans, cm, SNAPS).set_index("SNAPSHOT_DATE")
    assert t.loc[S[0], "TARGET_DPD30_90D"] == 1             # restructure within 3 months -> bad (DPD reset hides it)


def test_segment_migration_is_indeterminate():
    t = _toy([0] * 8, segments=["250", "250", "260", "260", "260", "260", "260", "260"])
    assert t.loc[S[0], "TARGET_STATUS"] == "INDETERMINATE"  # left CSME within the window
    assert t.loc[S[2], "TARGET_STATUS"] == "EXCLUDED_NOT_CSME"   # no longer a CSME customer


def test_generated_book_follows_rules(small_book):
    t = small_book["target"]
    assert not t.duplicated(["CUSTOMER_ID", "SNAPSHOT_DATE"]).any()
    lab = t[t["TARGET_STATUS"] == "LABELLED"]
    assert lab["TARGET_DPD30_90D"].isin([0, 1]).all()
    assert (lab["DPD_NOW"] <= 5).all()                      # population rule
    assert t.loc[t["TARGET_STATUS"] != "LABELLED", "TARGET_DPD30_90D"].isna().all()
    assert 0.01 < lab["TARGET_DPD30_90D"].mean() < 0.15     # a realistic bad rate
    last3 = sorted(t["SNAPSHOT_DATE"].unique())[-3:]
    assert not (t["SNAPSHOT_DATE"].isin(last3) & (t["TARGET_STATUS"] == "LABELLED")).any()