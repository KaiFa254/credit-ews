"""scripts/generate_data.py — build the synthetic CSME loan book and save it as CSV files.

WHAT:  Reads settings from config.yaml, creates each synthetic table, and writes them
       to data/synthetic/. Lesson 6: relationship_managers and customers.
       (Lessons 7–11 add loans, monthly behaviour, CRB, macro, the target and data issues.)
WHY:   One command rebuilds the whole dataset identically, on any laptop:
           python scripts/generate_data.py
HOW:   ONE random generator, created from the config seed, is passed to every step
       in a fixed order. Same seed + same order = identical data every run.
"""

import numpy as np

from ews.config import load_config, resolve_path
from ews.data.customers import make_customers, make_relationship_managers


def main() -> None:
    cfg = load_config()                                   # all settings from config/config.yaml
    seed = cfg["project"]["random_seed"]                  # 42
    sd = cfg["synthetic_data"]                            # size and dates of the synthetic book
    out_dir = resolve_path(cfg["paths"]["synthetic_data"])  # .../credit-ews/data/synthetic
    out_dir.mkdir(parents=True, exist_ok=True)            # create the folder if it doesn't exist

    # ONE random generator for the whole run (never call random functions without it)
    rng = np.random.default_rng(seed)

    # --- Table 1: relationship managers ---
    rms = make_relationship_managers(rng, sd["n_relationship_managers"])

    # --- Table 2: customers (assigned to RMs in their region) ---
    customers = make_customers(rng, sd["n_customers"], rms, reference_date=sd["start_month"])

    # --- Save as CSV (index=False: don't write pandas' row numbers as a column) ---
    tables = {"relationship_managers": rms, "customers": customers}
    for name, df in tables.items():
        path = out_dir / f"{name}.csv"
        df.to_csv(path, index=False)
        print(f"  saved {name:<22} {len(df):>7,} rows  -> {path}")

    print(f"\nDone (seed = {seed}).")


# This block runs only when the file is executed directly (python scripts/generate_data.py),
# not when another file imports it. It's the standard "entry point" pattern for scripts.
if __name__ == "__main__":
    main()