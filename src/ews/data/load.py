"""ews.data.load — read any project table with the CORRECT data types, every time.

WHAT:  load_table("customers") reads data/synthetic/customers.csv and applies the types
       from docs/data_dictionary.md: IDs and codes as TEXT, date columns as real DATES.
       load_all() loads every extract at once.
WHY:   CSV files have no types, so pandas GUESSES: segment "250" becomes the number 250,
       dates stay as text. Fixing that by hand in every notebook is easy to forget.
       This loader is the PERMANENT fix: one function, used by every notebook and script.
HOW:   The loader only fixes TYPES. It does NOT clean values (impossible ages, duplicates,
       messy categories stay exactly as they are). Cleaning is a separate step (Stage 4),
       so EDA sees the data as it really arrived.
       Dates that can't be read as YYYY-MM-DD become blank (NaT) and a WARNING says how
       many, so a problem like mixed date formats is never hidden silently.
       _truth_ files are refused unless you explicitly ask for them (leakage guard).
"""

# warnings: Python's built-in way to print a "heads-up" without stopping the program
import warnings
# Path: handles file paths the same way on Windows and Linux
from pathlib import Path

# pandas: reads the CSV into a DataFrame
import pandas as pd

# Our own helpers from Stage 1: read config.yaml, and turn "data/synthetic" into a full path
from ews.config import load_config, resolve_path

# ---------------------------------------------------------------------------------------
# TYPE RULES (copied from docs/data_dictionary.md)
# ---------------------------------------------------------------------------------------

# Columns that must be read as TEXT (identifiers and codes).
# Any column NOT listed here is left to pandas, which handles normal numbers correctly.
TEXT_COLUMNS = {
    "relationship_managers": ["RM_ID"],                                  # RM001 ...
    "customers": ["CUSTOMER_ID", "RM_ID", "SEGMENT"],                    # SEGMENT is a code, not a number
    "loans": ["LOAN_ID", "CUSTOMER_ID", "REFINANCED_FROM_LOAN_ID"],      # IDs
    "loan_monthly": ["LOAN_ID"],                                         # ID
    "customer_monthly": ["CUSTOMER_ID", "SEGMENT_AT_SNAPSHOT"],          # segment code each month
    "crb_monthly": ["CUSTOMER_ID"],                                      # ID
    "macro_monthly": [],                                                 # all numbers + a date
    "sector_monthly": [],                                                # all numbers/text + a date
    "_truth_customer_monthly": ["CUSTOMER_ID"],                          # answer key
    "_truth_target_customer_month": ["CUSTOMER_ID"],                     # answer key
    "_truth_planted_issues": ["ROW_KEY", "ORIGINAL_VALUE", "PLANTED_VALUE"],  # mixed values -> keep as text
}

# Columns that hold dates (written as YYYY-MM-DD text in the CSV)
DATE_COLUMNS = {
    "customers": ["CUSTOMER_SINCE"],                     # when the relationship started
    "loans": ["BOOKING_DATE", "MATURITY_DATE"],          # loan start and contractual end
    "loan_monthly": ["SNAPSHOT_DATE"],                   # month-end as-at date
    "customer_monthly": ["SNAPSHOT_DATE"],
    "crb_monthly": ["SNAPSHOT_DATE"],
    "macro_monthly": ["SNAPSHOT_DATE"],
    "sector_monthly": ["SNAPSHOT_DATE"],
    "_truth_customer_monthly": ["SNAPSHOT_DATE"],
    "_truth_target_customer_month": ["SNAPSHOT_DATE"],
}

# The "extracts": what a real analyst would receive from the bank (NO _truth_ answer keys)
EXTRACT_TABLES = ["relationship_managers", "customers", "loans", "loan_monthly",
                  "customer_monthly", "crb_monthly", "macro_monthly", "sector_monthly"]


def load_table(name: str, parse_dates: bool = True, allow_truth: bool = False,
               folder: Path | str | None = None) -> pd.DataFrame:
    """Read one table with the dictionary's types.

    Args:
        name:        table name, e.g. "customers" (without .csv)
        parse_dates: True = turn date columns into real dates; False = keep them as raw text
                     (useful in EDA to SEE badly formatted dates before they become blank)
        allow_truth: must be True to load a _truth_ file (answer keys are never model inputs)
        folder:      where the CSVs are; defaults to paths.synthetic_data in config.yaml
    """
    # Guard 1: a typo like "customer" (no s) fails loudly and lists the valid names
    if name not in TEXT_COLUMNS:
        raise ValueError(f"Unknown table '{name}'. Known tables: {sorted(TEXT_COLUMNS)}")
    # Guard 2: answer keys need an explicit "yes, I know what I'm doing"
    if name.startswith("_truth") and not allow_truth:
        raise PermissionError(f"'{name}' is an answer key (TRUTH). Pass allow_truth=True only "
                              "for checking your work, never for features or models.")

    # Where to read from: the folder you pass (tests use a temp folder), else config.yaml
    folder = Path(folder) if folder else resolve_path(load_config()["paths"]["synthetic_data"])
    # Build the full file path, e.g. .../data/synthetic/customers.csv
    path = folder / f"{name}.csv"
    # Guard 3: a missing file gives a clear instruction, not a confusing pandas error
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run: python scripts/generate_data.py")

    # STEP 1 — Read. dtype={...: str} forces the listed columns to TEXT.
    # Empty cells still become NaN (missing), so missingness stays visible for EDA.
    # low_memory=False makes pandas look at the whole column before deciding a type.
    df = pd.read_csv(path, dtype={c: str for c in TEXT_COLUMNS[name]}, low_memory=False)

    # STEP 2 — Dates. Strict YYYY-MM-DD; anything else becomes NaT and is REPORTED.
    if parse_dates:
        # Loop over this table's date columns (none for e.g. relationship_managers)
        for col in DATE_COLUMNS.get(name, []):
            # Keep the original text so we can count failures
            raw = df[col]
            # errors="coerce": unreadable values become NaT instead of crashing
            parsed = pd.to_datetime(raw, format="%Y-%m-%d", errors="coerce")
            # A failure = there WAS text (raw not missing) but it didn't parse (parsed missing)
            n_bad = int((parsed.isna() & raw.notna()).sum())
            # Never hide it: warn with the count and how to inspect it
            if n_bad:
                warnings.warn(f"{name}.{col}: {n_bad:,} values are not YYYY-MM-DD and became NaT "
                              f"(load with parse_dates=False to inspect them)", stacklevel=2)
            # Replace the text column with the real date column
            df[col] = parsed
    # Hand back the typed (but NOT cleaned) table
    return df


def load_all(parse_dates: bool = True, folder: Path | str | None = None) -> dict[str, pd.DataFrame]:
    """Load every extract table (no _truth_ files) into a dictionary {name: DataFrame}."""
    # Dictionary comprehension: {"customers": DataFrame, "loans": DataFrame, ...}
    return {name: load_table(name, parse_dates=parse_dates, folder=folder) for name in EXTRACT_TABLES}