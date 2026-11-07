"""tests/test_load.py — the type-safe loader keeps codes as text, reads dates, and never hides problems.

WHAT:  Writes tiny CSV files into a temporary folder and loads them with load_table().
WHY:   The loader is used by every notebook and script from now on. If it ever turned
       "250" back into a number, or silently dropped bad dates, every later stage would
       inherit the error.
USAGE: pytest -v tests/test_load.py
"""

# pandas: to check column types
import pandas as pd
# pytest: fixtures, warning checks and error checks
import pytest

# The function under test
from ews.data.load import load_table


@pytest.fixture
def folder(tmp_path):
    # ARRANGE: a tiny customers file with one good date (2016-02-01) and one
    # DD/MM/YYYY date (25/12/2019), plus an impossible age (150)
    (tmp_path / "customers.csv").write_text(
        "CUSTOMER_ID,RM_ID,SEGMENT,AGE,CUSTOMER_SINCE\n"
        "C000001,RM001,250,44,2016-02-01\n"
        "C000002,RM002,270,150,25/12/2019\n",
        encoding="utf-8")
    # A tiny answer-key file, to test the _truth_ guard
    (tmp_path / "_truth_customer_monthly.csv").write_text(
        "CUSTOMER_ID,SNAPSHOT_DATE,LATENT_HEALTH\nC000001,2023-01-31,0.5\n", encoding="utf-8")
    # Give the folder path to each test
    return tmp_path


def test_codes_stay_text(folder):
    # parse_dates=False: this test is only about codes, so skip the (expected) date warning
    df = load_table("customers", parse_dates=False, folder=folder)
    assert df["SEGMENT"].tolist() == ["250", "270"]          # text codes, not numbers
    assert df["CUSTOMER_ID"].iloc[0] == "C000001"            # leading zeros kept


def test_dates_parsed_and_bad_ones_reported(folder):
    # pytest.warns: the test FAILS if this warning is NOT raised (silence would be a bug)
    with pytest.warns(UserWarning, match="1 values are not YYYY-MM-DD"):
        df = load_table("customers", folder=folder)
    assert pd.api.types.is_datetime64_any_dtype(df["CUSTOMER_SINCE"])   # a real date column now
    assert df["CUSTOMER_SINCE"].isna().sum() == 1            # the DD/MM/YYYY value became NaT


def test_raw_dates_available_for_eda(folder):
    # parse_dates=False lets EDA SEE the messy text exactly as it arrived
    df = load_table("customers", parse_dates=False, folder=folder)
    assert df["CUSTOMER_SINCE"].tolist() == ["2016-02-01", "25/12/2019"]


def test_loader_does_not_clean_values(folder):
    df = load_table("customers", parse_dates=False, folder=folder)
    assert 150 in df["AGE"].tolist()                          # impossible age KEPT: cleaning is Stage 4's job


def test_truth_tables_are_guarded(folder):
    # Without permission: refused
    with pytest.raises(PermissionError):
        load_table("_truth_customer_monthly", folder=folder)
    # With explicit permission: allowed (for checking work only)
    assert len(load_table("_truth_customer_monthly", allow_truth=True, folder=folder)) == 1


def test_unknown_table_and_missing_file(folder):
    # Typo in the table name -> clear ValueError
    with pytest.raises(ValueError):
        load_table("not_a_table", folder=folder)
    # Valid name but the file isn't there -> clear FileNotFoundError
    with pytest.raises(FileNotFoundError):
        load_table("loans", folder=folder)