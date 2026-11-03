"""tests/test_loans.py — check the loan generators follow the data dictionary and loan maths.

WHAT:  Builds a small loan book (300 customers, 36 months) and checks keys, links,
       product rules, the EMI formula, balances, utilisation, closures and reproducibility.
WHY:   Loans are where arrears (and our target) will come from. A wrong balance, a loan
       appearing before it was booked, or a refinance pointing nowhere would silently
       corrupt everything built on top.
USAGE: pytest -v tests/test_loans.py
"""

import numpy as np
import pandas as pd
import pytest

from ews.data.customers import make_customers, make_relationship_managers
from ews.data.loans import PRODUCTS, balance_after, calc_emi, make_loan_monthly, make_loans

SNAPSHOTS = pd.date_range("2023-01-31", periods=36, freq="ME")


def build(seed=123, n_customers=300):
    """Build customers -> loans -> loan_monthly, exactly as generate_data.py does."""
    rng = np.random.default_rng(seed)
    rms = make_relationship_managers(rng, 40)
    customers = make_customers(rng, n_customers, rms, "2023-01-31")
    loans = make_loans(rng, customers, SNAPSHOTS)
    monthly = make_loan_monthly(rng, loans, SNAPSHOTS)
    return customers, loans, monthly


@pytest.fixture(scope="module")      # scope="module": build once and share across all tests in this file
def book():
    return build()


# --- Loan maths -------------------------------------------------------------------
def test_emi_formula_known_example():
    # 1,000,000 at 12% a year for 12 months -> 88,848.79 a month (standard annuity result)
    assert calc_emi(1_000_000, 12.0, 12) == pytest.approx(88_848.79, abs=0.01)


def test_balance_reaches_zero_at_maturity():
    emi = calc_emi(1_000_000, 12.0, 12)
    assert balance_after(1_000_000, 12.0, emi, 0) == pytest.approx(1_000_000)   # nothing paid yet
    assert balance_after(1_000_000, 12.0, emi, 12) == pytest.approx(0, abs=0.01)  # fully repaid


# --- Keys and links ----------------------------------------------------------------
def test_primary_keys_are_unique(book):
    _, loans, monthly = book
    assert loans["LOAN_ID"].is_unique
    assert not monthly.duplicated(["LOAN_ID", "SNAPSHOT_DATE"]).any()   # composite key


def test_referential_integrity(book):
    customers, loans, monthly = book
    assert loans["CUSTOMER_ID"].isin(customers["CUSTOMER_ID"]).all()    # every loan has a customer
    assert monthly["LOAN_ID"].isin(loans["LOAN_ID"]).all()              # every monthly row has a loan


def test_every_customer_has_at_least_one_loan(book):
    customers, loans, _ = book
    assert set(customers["CUSTOMER_ID"]) == set(loans["CUSTOMER_ID"])


# --- Product rules from the data dictionary ----------------------------------------
def test_product_values_and_secured_flag(book):
    _, loans, _ = book
    assert set(loans["PRODUCT"]) <= set(PRODUCTS)
    expected = loans["PRODUCT"].map(lambda p: PRODUCTS[p]["secured"])
    assert (loans["SECURED_FLAG"] == expected).all()
    assert loans["INTEREST_RATE"].between(9, 36).all()
    assert (loans["LOAN_AMOUNT"] > 0).all()


def test_instalment_vs_revolving_terms(book):
    _, loans, _ = book
    revolving = loans["PRODUCT"].map(lambda p: PRODUCTS[p]["kind"] == "revolving")
    # instalment loans: tenor, EMI and maturity present; revolving: none of them
    assert loans.loc[~revolving, "TENOR_MONTHS"].notna().all()
    assert (loans.loc[~revolving, "EMI"] > 0).all()
    assert loans.loc[revolving, "TENOR_MONTHS"].isna().all()
    assert (loans.loc[revolving, "EMI"] == 0).all()
    assert loans.loc[revolving, "MATURITY_DATE"].isna().all()


def test_booking_dates_within_dictionary_range(book):
    _, loans, _ = book
    booked = pd.to_datetime(loans["BOOKING_DATE"])
    assert booked.min() >= pd.Timestamp("2015-01-01")
    assert booked.max() <= pd.Timestamp("2025-12-31")


# --- Monthly life of each loan ------------------------------------------------------
def test_no_row_before_booking_and_mob_counts_up(book):
    _, loans, monthly = book
    m = monthly.merge(loans[["LOAN_ID", "BOOKING_DATE"]], on="LOAN_ID")
    assert (pd.to_datetime(m["SNAPSHOT_DATE"]) >= pd.to_datetime(m["BOOKING_DATE"])).all()
    assert (m["MOB"] >= 0).all()
    # MOB rises by exactly 1 from one month to the next for each loan
    steps = m.sort_values(["LOAN_ID", "SNAPSHOT_DATE"]).groupby("LOAN_ID")["MOB"].diff().dropna()
    assert (steps == 1).all()


def test_instalment_balances_never_rise(book):
    _, loans, monthly = book
    inst_ids = loans.loc[loans["PRODUCT"].map(lambda p: PRODUCTS[p]["kind"] == "instalment"), "LOAN_ID"]
    m = monthly[monthly["LOAN_ID"].isin(inst_ids)].sort_values(["LOAN_ID", "SNAPSHOT_DATE"])
    change = m.groupby("LOAN_ID")["OUTSTANDING_BALANCE"].diff().dropna()
    assert (change <= 0.01).all()                               # balances only go down (or stay)
    assert (m["OUTSTANDING_BALANCE"] >= 0).all()


def test_revolving_utilisation_in_range(book):
    _, loans, monthly = book
    rev_ids = loans.loc[loans["PRODUCT"].map(lambda p: PRODUCTS[p]["kind"] == "revolving"), "LOAN_ID"]
    util = monthly.loc[monthly["LOAN_ID"].isin(rev_ids), "LIMIT_UTILISATION"]
    assert util.notna().all() and util.between(0, 1).all()


def test_closures_are_last_row_with_zero_balance_and_a_reason(book):
    _, _, monthly = book
    closed = monthly[monthly["ACCOUNT_STATUS"] == "CLOSED"]
    assert set(closed["CLOSURE_REASON"]) <= {"PAID_OFF", "MATURED", "REFINANCED"}
    assert (closed["OUTSTANDING_BALANCE"] == 0).all()
    last_rows = monthly.sort_values("SNAPSHOT_DATE").groupby("LOAN_ID").tail(1)
    assert closed["LOAN_ID"].isin(last_rows.loc[last_rows["ACCOUNT_STATUS"] == "CLOSED", "LOAN_ID"]).all()
    assert closed["LOAN_ID"].is_unique                          # a loan closes only once


def test_refinanced_loans_point_to_a_closed_loan_in_the_same_month(book):
    _, loans, monthly = book
    new = loans.dropna(subset=["REFINANCED_FROM_LOAN_ID"])
    assert len(new) > 0                                         # the case exists in the data
    closed = monthly[monthly["CLOSURE_REASON"] == "REFINANCED"].set_index("LOAN_ID")["SNAPSHOT_DATE"]
    first_month = monthly.groupby("LOAN_ID")["SNAPSHOT_DATE"].min()
    for row in new.itertuples(index=False):
        assert row.REFINANCED_FROM_LOAN_ID in closed.index      # the old loan really closed as REFINANCED
        assert first_month[row.LOAN_ID] == closed[row.REFINANCED_FROM_LOAN_ID]   # replaced the same month


def test_same_seed_gives_identical_loans():
    _, loans_a, monthly_a = build(seed=7, n_customers=100)
    _, loans_b, monthly_b = build(seed=7, n_customers=100)
    pd.testing.assert_frame_equal(loans_a, loans_b)
    pd.testing.assert_frame_equal(monthly_a, monthly_b)