"""scripts/generate_data.py — build the complete synthetic CSME loan book.

WHAT:  Reads config.yaml, builds every synthetic table in order, plants data-quality
       issues, and writes CSV files to data/synthetic/:
         relationship_managers, customers, loans, loan_monthly,
         customer_monthly, crb_monthly, macro_monthly, sector_monthly       (the "extracts")
         _truth_customer_monthly          hidden health            (NEVER a model input)
         _truth_target_customer_month     reference target, built from CLEAN data
         _truth_planted_issues            log of every planted data problem
WHY:   One command rebuilds the whole dataset identically, on any laptop:
           python scripts/generate_data.py
HOW:   ONE random generator from the config seed is passed to every step in a fixed
       order, so the same seed always gives exactly the same data.

NOTE:  In a real bank these tables come from separate source systems and extracts;
       here one script fakes all of them, which never happens in reality.
"""

import time

import numpy as np
import pandas as pd

from ews.config import load_config, resolve_path
from ews.data.behaviour import (make_crb_monthly, make_customer_monthly, make_macro,
                                make_sector, make_truth)
from ews.data.customers import SECTORS, make_customers, make_relationship_managers
from ews.data.delinquency import apply_delinquency
from ews.data.loans import PLAN_COLUMNS, make_loan_monthly, make_loans
from ews.data.quality_issues import plant_issues
from ews.data.target import build_target


def main() -> None:
    t0 = time.perf_counter()                               # stopwatch, to show how long each step takes
    cfg = load_config()                                    # all settings from config/config.yaml
    seed = cfg["project"]["random_seed"]                   # 42
    sd, tg = cfg["synthetic_data"], cfg["target"]          # data size/dates, and target rules
    out_dir = resolve_path(cfg["paths"]["synthetic_data"]) # .../credit-ews/data/synthetic
    out_dir.mkdir(parents=True, exist_ok=True)             # create the folder if missing

    # The 36 month-end snapshot dates: 2023-01-31 ... 2025-12-31
    snapshots = pd.date_range(sd["start_month"], periods=sd["n_months"], freq="ME")
    rng = np.random.default_rng(seed)                      # ONE random generator for everything

    def step(msg):                                         # small progress printer
        print(f"  [{time.perf_counter() - t0:5.1f}s] {msg}")

    # --- Static tables (Lesson 6) ---
    step("relationship managers and customers")
    rms = make_relationship_managers(rng, sd["n_relationship_managers"])
    customers = make_customers(rng, sd["n_customers"], rms, reference_date=sd["start_month"])

    # --- Loans and their contractual life (Lesson 7) ---
    step("loans and contractual loan_monthly")
    loans = make_loans(rng, customers, snapshots)
    loan_monthly = make_loan_monthly(rng, loans, snapshots)
    loans = loans.drop(columns=PLAN_COLUMNS)               # planning helpers never leave the generator

    # --- The hidden story and its symptoms (Lesson 8) ---
    step("economy, sector shocks and hidden health")
    macro = make_macro(rng, snapshots)
    sector = make_sector(rng, snapshots, list(SECTORS))
    truth = make_truth(rng, customers, loans, snapshots, macro, sector)
    step("account behaviour and credit bureau")
    customer_monthly = make_customer_monthly(rng, customers, truth, snapshots)
    crb_monthly = make_crb_monthly(rng, customers, truth, snapshots)

    # --- Real repayment history: DPD, arrears, restructures, write-offs (Lesson 9) ---
    step("delinquency (DPD paths)")
    loan_monthly = apply_delinquency(rng, loans, loan_monthly, truth, customers, snapshots[0])

    # --- Reference target from the CLEAN data (Lesson 9) ---
    step("reference target")
    target = build_target(loan_monthly, loans, customer_monthly, snapshots,
                          dpd_threshold=tg["dpd_threshold"], horizon_months=tg["horizon_months"],
                          max_dpd_at_snapshot=tg["max_dpd_at_snapshot"])

    # --- Plant realistic data problems into COPIES of the extracts (Lesson 10) ---
    step("planting data-quality issues")
    clean = {"customers": customers, "loans": loans, "loan_monthly": loan_monthly,
             "customer_monthly": customer_monthly, "crb_monthly": crb_monthly}
    dirty, issue_log = plant_issues(rng, clean)

    # --- Save: the dirty extracts (what a real analyst receives) plus the _truth_ files ---
    tables = {
        "relationship_managers": rms, **dirty,
        "macro_monthly": macro, "sector_monthly": sector,
        "_truth_customer_monthly": truth,
        "_truth_target_customer_month": target,
        "_truth_planted_issues": issue_log,
    }
    step("saving CSV files")
    for name, df in tables.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)    # index=False: don't save pandas row numbers
        print(f"      {name:<30} {len(df):>9,} rows")

    # --- A short summary of the target, to sanity-check the book ---
    labelled = target[target["TARGET_STATUS"] == "LABELLED"]
    print("\n  Target status counts:")
    print(target["TARGET_STATUS"].value_counts().to_string().replace("\n", "\n    ").join(["    ", ""]))
    print(f"\n  Bad rate (labelled customer-months): {labelled['TARGET_DPD30_90D'].mean():.2%}")
    print(f"  Planted data issues logged: {len(issue_log):,}")
    print(f"\nDone (seed = {seed}) in {time.perf_counter() - t0:.1f} seconds.")


# Runs only when started from the terminal (python scripts/generate_data.py), not when imported
if __name__ == "__main__":
    main()