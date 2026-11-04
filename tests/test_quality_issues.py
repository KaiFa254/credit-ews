"""tests/test_quality_issues.py — planted data problems exist, are logged, and never touch clean data.

WHAT:  Checks every promised issue type was planted and logged, that the dirty tables
       really contain the problems, and that the clean originals are untouched.
WHY:   In Stages 3–4 you'll hunt for these problems. The log is the answer key, so it must
       be complete and accurate; and the clean target must stay clean.
USAGE: pytest -v tests/test_quality_issues.py
"""

import pandas as pd

EXPECTED = {
    ("customers", "MISSING_VALUE"), ("customers", "INVALID_VALUE"), ("customers", "INCONSISTENT_CATEGORY"),
    ("customers", "UNEXPECTED_CATEGORY"), ("customers", "MIXED_DATE_FORMAT"),
    ("loans", "OUTLIER"), ("loans", "UNEXPECTED_CATEGORY"), ("loans", "ORPHAN_RECORD"),
    ("loan_monthly", "INVALID_VALUE"), ("loan_monthly", "DUPLICATE_KEY"),
    ("customer_monthly", "MISSING_VALUE"), ("customer_monthly", "INVALID_VALUE"),
    ("customer_monthly", "OUTLIER"), ("customer_monthly", "EXACT_DUPLICATE"),
    ("crb_monthly", "INVALID_VALUE"), ("crb_monthly", "ROWS_MISSING"),
}


def test_every_issue_type_is_logged(small_book):
    logged = set(map(tuple, small_book["log"][["TABLE", "ISSUE_TYPE"]].drop_duplicates().to_numpy()))
    assert EXPECTED <= logged


def test_clean_tables_are_untouched(small_book):
    clean = small_book["clean"]
    assert clean["customers"]["AGE"].between(21, 75).all()
    assert not clean["loan_monthly"].duplicated(["LOAN_ID", "SNAPSHOT_DATE"]).any()
    assert (clean["loan_monthly"]["DPD"] >= 0).all()
    assert clean["loans"]["CUSTOMER_ID"].isin(clean["customers"]["CUSTOMER_ID"]).all()


def test_dirty_tables_contain_the_problems(small_book):
    d = small_book["dirty"]
    assert (~d["customers"]["AGE"].between(21, 75)).any()                       # invalid ages
    assert d["customers"]["DECLARED_MONTHLY_INCOME"].isna().any()                # missing income
    assert d["customers"]["CUSTOMER_SINCE"].str.contains("/").any()             # DD/MM/YYYY dates
    assert d["loan_monthly"].duplicated(["LOAN_ID", "SNAPSHOT_DATE"]).any()     # key duplicates
    assert d["customer_monthly"].duplicated().any()                              # exact duplicates
    assert (~d["loans"]["CUSTOMER_ID"].isin(d["customers"]["CUSTOMER_ID"])).sum() == 12   # orphans
    assert (d["loans"]["PRODUCT"] == "LEASE").sum() == 5                          # unexpected product
    june = d["crb_monthly"]["SNAPSHOT_DATE"] == "2024-06-30"
    assert june.sum() < 0.7 * len(small_book["customers"])                       # partly failed feed


def test_log_counts_match_reality(small_book):
    log, d = small_book["log"], small_book["dirty"]
    n_age = ((log["TABLE"] == "customers") & (log["COLUMN"] == "AGE")).sum()
    assert n_age == (~d["customers"]["AGE"].between(21, 75)).sum()
    n_dup = ((log["TABLE"] == "customer_monthly") & (log["ISSUE_TYPE"] == "EXACT_DUPLICATE")).sum()
    assert n_dup == d["customer_monthly"].duplicated().sum()


def test_truth_never_planted(small_book):
    # hidden health and the reference target are built from CLEAN data and never made dirty
    assert "_truth_customer_monthly" not in set(small_book["log"]["TABLE"])
    assert isinstance(small_book["truth"], pd.DataFrame) and small_book["truth"]["LATENT_HEALTH"].notna().all()