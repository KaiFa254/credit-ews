"""tests/test_customers.py — check the RM and customer generators follow the data dictionary.

WHAT:  Builds a small sample (500 customers) and checks keys, links, ranges,
       types and reproducibility against docs/data_dictionary.md.
WHY:   If a later change breaks the generator (a duplicate ID, an age of 150,
       a customer with no RM), these tests fail immediately.
USAGE: pytest -v tests/test_customers.py
"""

import numpy as np
import pandas as pd
import pytest

from ews.data.customers import REGIONS, SECTORS, make_customers, make_relationship_managers


# A "fixture" builds test data once and hands it to every test that asks for it by name.
@pytest.fixture
def tables():
    rng = np.random.default_rng(123)                       # a fixed seed just for tests
    rms = make_relationship_managers(rng, n_rms=40)
    customers = make_customers(rng, n_customers=500, rms=rms, reference_date="2023-01-31")
    return rms, customers


def test_row_counts(tables):
    rms, customers = tables
    assert len(rms) == 40
    assert len(customers) == 500


def test_primary_keys_are_unique(tables):
    rms, customers = tables
    assert rms["RM_ID"].is_unique                          # one row per RM
    assert customers["CUSTOMER_ID"].is_unique              # one row per customer
    assert rms["RM_EMAIL"].is_unique                       # every RM has their own inbox


def test_every_region_has_an_rm(tables):
    rms, _ = tables
    assert set(rms["REGION"]) == set(REGIONS)              # no region left without an RM


def test_referential_integrity_customer_to_rm(tables):
    rms, customers = tables
    # every customer's RM must exist (no orphans)
    assert customers["RM_ID"].isin(rms["RM_ID"]).all()
    # and the RM must be in the customer's own region
    merged = customers.merge(rms[["RM_ID", "REGION"]], on="RM_ID", suffixes=("", "_RM"))
    assert (merged["REGION"] == merged["REGION_RM"]).all()


def test_values_follow_the_data_dictionary(tables):
    rms, customers = tables
    assert customers["AGE"].between(21, 75).all()
    assert customers["BUSINESS_YEARS"].between(0, 40).all()
    assert (customers["DECLARED_MONTHLY_INCOME"] > 0).all()
    assert set(customers["SEGMENT"]) <= {"250", "270"}      # <= means "is a subset of"
    assert set(customers["SECTOR"]) <= set(SECTORS)
    assert set(customers["GENDER"]) <= {"M", "F"}
    assert rms["RM_EMAIL"].str.endswith("@example.com").all()   # never a real domain


def test_segment_is_text_not_number(tables):
    _, customers = tables
    # "250" must stay a code (text). A number 250 would lose meaning and break joins.
    assert customers["SEGMENT"].map(type).eq(str).all()


def test_customer_since_within_allowed_dates(tables):
    _, customers = tables
    since = pd.to_datetime(customers["CUSTOMER_SINCE"])
    assert since.min() >= pd.Timestamp("2005-01-01")
    assert since.max() <= pd.Timestamp("2023-01-31")


def test_income_is_right_skewed(tables):
    _, customers = tables
    income = customers["DECLARED_MONTHLY_INCOME"]
    # right-skewed money: a long tail of large businesses pulls the mean above the median
    assert income.mean() > income.median()


def test_same_seed_gives_identical_data():
    def build(seed):
        rng = np.random.default_rng(seed)
        rms = make_relationship_managers(rng, 40)
        return make_customers(rng, 200, rms, "2023-01-31")

    pd.testing.assert_frame_equal(build(7), build(7))      # same seed -> identical tables
    assert not build(7).equals(build(8))                   # different seed -> different data