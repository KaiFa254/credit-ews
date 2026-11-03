"""scripts/generate_data.py — build the synthetic CSME loan book and save it as CSV files.

WHAT:  Reads settings from config.yaml, creates each synthetic table, and writes them
       to data/synthetic/.
         Lesson 6: relationship_managers, customers
         Lesson 7: loans, loan_monthly
       (Lessons 8–11 add monthly behaviour, CRB, macro, DPD, the target and data issues.)
WHY:   One command rebuilds the whole dataset identically, on any laptop:
           python scripts/generate_data.py
HOW:   ONE random generator, created from the config seed, is passed to every step
       in a fixed order. Same seed + same order = identical data every run.
"""

import time

import numpy as np
import pandas as pd

from ews.config import load_config, resolve_path
from ews.data.customers import make_customers, make_relationship_managers
from ews.data.loans import PLAN_COLUMNS, make_loan_monthly, make_loans


def main() -> None:
    t0 = time.perf_counter()                              # start a stopwatch (to show run time)
    cfg = load_config()                                   # all settings from config/config.yaml
    seed = cfg["project"]["random_seed"]                  # 42
    sd = cfg["synthetic_data"]                            # size and dates of the synthetic book
    out_dir = resolve_path(cfg["paths"]["synthetic_data"])  # .../credit-ews/data/synthetic
    out_dir.mkdir(parents=True, exist_ok=True)            # create the folder if it doesn't exist

    # The 36 month-end snapshot dates, e.g. 2023-01-31 ... 2025-12-31 ("ME" = month-end)
    snapshots = pd.date_range(sd["start_month"], periods=sd["n_months"], freq="ME")

    # ONE random generator for the whole run (never call random functions without it)
    rng = np.random.default_rng(seed)

    # --- Tables 1–2: relationship managers and customers (Lesson 6) ---
    rms = make_relationship_managers(rng, sd["n_relationship_managers"])
    customers = make_customers(rng, sd["n_customers"], rms, reference_date=sd["start_month"])

    # --- Tables 3–4: loans and their monthly life (Lesson 7) ---
    loans = make_loans(rng, customers, snapshots)
    loan_monthly = make_loan_monthly(rng, loans, snapshots)
    loans = loans.drop(columns=PLAN_COLUMNS)              # planning helpers never leave the generator

    # --- Save as CSV (index=False: don't write pandas' row numbers as a column) ---
    tables = {"relationship_managers": rms, "customers": customers,
              "loans": loans, "loan_monthly": loan_monthly}
    for name, df in tables.items():
        path = out_dir / f"{name}.csv"
        df.to_csv(path, index=False)
        print(f"  saved {name:<22} {len(df):>9,} rows  -> {path}")

    print(f"\nDone (seed = {seed}) in {time.perf_counter() - t0:.1f} seconds.")


# This block runs only when the file is executed directly (python scripts/generate_data.py),
# not when another file imports it. It's the standard "entry point" pattern for scripts.
if __name__ == "__main__":
    main()