"""tests/test_delinquency.py — DPD paths, arrears, restructures and write-offs.

WHAT:  Checks the repayment history added to loan_monthly obeys the dictionary and the
       rules of how arrears actually evolve, and that poor health causes arrears.
WHY:   DPD is the raw material of the target. A DPD that jumps impossibly, a written-off
       loan that keeps reporting, or arrears unrelated to health would corrupt the label.
USAGE: pytest -v tests/test_delinquency.py
"""

import numpy as np


def test_keys_and_new_columns(small_book):
    lm = small_book["loan_monthly"]
    assert not lm.duplicated(["LOAN_ID", "SNAPSHOT_DATE"]).any()
    for col in ["DPD", "ARREARS_AMOUNT", "MISSED_INSTALMENT_FLAG", "RESTRUCTURED_FLAG"]:
        assert col in lm.columns and lm[col].notna().all()


def test_dpd_and_arrears_ranges(small_book):
    lm = small_book["loan_monthly"]
    assert lm["DPD"].between(0, 360).all()
    assert (lm["ARREARS_AMOUNT"] >= 0).all()
    assert (lm.loc[lm["DPD"] == 0, "ARREARS_AMOUNT"] == 0).all()   # no arrears when current
    assert (lm.loc[lm["DPD"] > 0, "ARREARS_AMOUNT"] > 0).all()      # arrears when overdue


def test_dpd_moves_realistically(small_book):
    lm = small_book["loan_monthly"].sort_values(["LOAN_ID", "SNAPSHOT_DATE"])
    prev = lm.groupby("LOAN_ID")["DPD"].shift(1)
    both = prev.notna() & (prev > 0) & (lm["DPD"] > 0)
    # once overdue, DPD can only grow by ~30 a month (capped at 360) unless it cures to 0
    step = lm.loc[both, "DPD"] - prev[both]
    assert ((step == 30) | (lm.loc[both, "DPD"] == 360)).all()


def test_statuses_and_reasons(small_book):
    lm = small_book["loan_monthly"]
    assert set(lm["ACCOUNT_STATUS"]) <= {"ACTIVE", "CLOSED", "RESTRUCTURED", "WRITTEN_OFF"}
    assert set(lm["CLOSURE_REASON"].dropna()) <= {"PAID_OFF", "MATURED", "REFINANCED", "WRITTEN_OFF"}
    restr = lm[lm["RESTRUCTURED_FLAG"] == 1]
    assert (restr["ACCOUNT_STATUS"] == "RESTRUCTURED").all() and (restr["DPD"] == 0).all()


def test_no_rows_after_write_off(small_book):
    lm = small_book["loan_monthly"]
    wo = lm[lm["ACCOUNT_STATUS"] == "WRITTEN_OFF"].set_index("LOAN_ID")["SNAPSHOT_DATE"]
    last = lm.groupby("LOAN_ID")["SNAPSHOT_DATE"].max()
    assert (last[wo.index] == wo).all()                    # the write-off month is the last row
    assert (lm.loc[lm["ACCOUNT_STATUS"] == "WRITTEN_OFF", "DPD"] >= 180).all()


def test_poor_health_causes_arrears(small_book):
    lm = small_book["loan_monthly"].merge(small_book["loans"][["LOAN_ID", "CUSTOMER_ID"]], on="LOAN_ID")
    x = lm.merge(small_book["truth"], on=["CUSTOMER_ID", "SNAPSHOT_DATE"])
    overdue = x["DPD"] >= 30
    assert x.loc[overdue, "LATENT_HEALTH"].mean() < x.loc[~overdue, "LATENT_HEALTH"].mean() - 0.5


def test_contractual_rows_preserved_until_write_off(small_book):
    # delinquency only ADDS information; it may drop rows only after a write-off
    contractual, lm = small_book["contractual"], small_book["loan_monthly"]
    assert len(lm) <= len(contractual)
    assert set(lm["LOAN_ID"]) == set(contractual["LOAN_ID"])
    assert np.isclose(lm["MOB"].min(), 0)