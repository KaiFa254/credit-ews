"""tests/conftest.py — shared test setup, loaded automatically by pytest before any test.

WHAT:  A "small_book" fixture: the WHOLE synthetic pipeline run once on 400 customers.
WHY:   The behaviour, delinquency, target and data-issue tests all need the same small
       book. Building it once per test session (scope="session") keeps the tests fast.
USAGE: Any test can ask for it by name:   def test_something(small_book): ...
       Never run this file directly: pytest finds it by its special name.
"""

import numpy as np
import pandas as pd
import pytest

from ews.data.behaviour import (make_crb_monthly, make_customer_monthly, make_macro,
                                make_sector, make_truth)
from ews.data.customers import SECTORS, make_customers, make_relationship_managers
from ews.data.delinquency import apply_delinquency
from ews.data.loans import PLAN_COLUMNS, make_loan_monthly, make_loans
from ews.data.quality_issues import plant_issues
from ews.data.target import build_target

SNAPSHOTS = pd.date_range("2023-01-31", periods=36, freq="ME")


def build_book(seed: int = 2024, n_customers: int = 400) -> dict:
    """Run every generation step, in the same order as scripts/generate_data.py."""
    rng = np.random.default_rng(seed)
    rms = make_relationship_managers(rng, 40)
    customers = make_customers(rng, n_customers, rms, "2023-01-31")
    loans = make_loans(rng, customers, SNAPSHOTS)
    contractual = make_loan_monthly(rng, loans, SNAPSHOTS)
    loans = loans.drop(columns=PLAN_COLUMNS)
    macro = make_macro(rng, SNAPSHOTS)
    sector = make_sector(rng, SNAPSHOTS, list(SECTORS))
    truth = make_truth(rng, customers, loans, SNAPSHOTS, macro, sector)
    customer_monthly = make_customer_monthly(rng, customers, truth, SNAPSHOTS)
    crb = make_crb_monthly(rng, customers, truth, SNAPSHOTS)
    loan_monthly = apply_delinquency(rng, loans, contractual, truth, customers, SNAPSHOTS[0])
    target = build_target(loan_monthly, loans, customer_monthly, SNAPSHOTS)
    clean = {"customers": customers, "loans": loans, "loan_monthly": loan_monthly,
             "customer_monthly": customer_monthly, "crb_monthly": crb}
    dirty, log = plant_issues(rng, clean)
    return {"rms": rms, "customers": customers, "loans": loans, "contractual": contractual,
            "macro": macro, "sector": sector, "truth": truth, "customer_monthly": customer_monthly,
            "crb": crb, "loan_monthly": loan_monthly, "target": target, "clean": clean,
            "dirty": dirty, "log": log}


@pytest.fixture(scope="session")
def small_book():
    return build_book()