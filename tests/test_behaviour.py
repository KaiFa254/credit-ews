"""tests/test_behaviour.py — the economy, sector shocks, hidden health and its symptoms.

WHAT:  Checks shapes, keys and ranges of macro_monthly, sector_monthly, the hidden health,
       customer_monthly and crb_monthly, AND that the planted cause-and-effect really exists.
WHY:   If symptoms didn't move with health, the model would have nothing real to learn,
       and every later stage would be meaningless.
USAGE: pytest -v tests/test_behaviour.py
"""

import numpy as np
import pandas as pd

from ews.data.behaviour import SECTOR_SHOCKS


def test_macro_shape_and_ranges(small_book):
    macro = small_book["macro"]
    assert len(macro) == 36 and macro["SNAPSHOT_DATE"].is_unique
    assert macro["INFLATION_RATE"].between(2, 12).all()
    assert macro["CBK_RATE"].between(6, 14).all()
    assert macro["UNEMPLOYMENT_PROXY"].between(3, 15).all()
    assert macro["ECON_STRESS_INDEX"].between(0, 1).all()


def test_macro_downturn_peaks_mid_2024(small_book):
    stress = small_book["macro"].set_index("SNAPSHOT_DATE")["ECON_STRESS_INDEX"]
    # the planted downturn: stress around Sep 2024 is clearly above early 2023
    assert stress["2024-09-30"] > stress["2023-02-28"] + 0.25


def test_sector_drought_hits_agriculture(small_book):
    s = small_book["sector"].pivot(index="SNAPSHOT_DATE", columns="SECTOR", values="SECTOR_STRESS_INDEX")
    start, end, _ = SECTOR_SHOCKS["Agriculture"][0]
    during = s["Agriculture"].iloc[start:end + 1].mean()
    before = s["Agriculture"].iloc[:start].mean()
    assert during > before + 0.15                       # the drought is visible in the index
    assert s.stack().between(0, 1).all()


def test_truth_keys_and_range(small_book):
    truth, customers = small_book["truth"], small_book["customers"]
    assert len(truth) == len(customers) * 36
    assert not truth.duplicated(["CUSTOMER_ID", "SNAPSHOT_DATE"]).any()
    assert truth["LATENT_HEALTH"].between(-4, 4).all()


def test_customer_monthly_keys_and_ranges(small_book):
    cm = small_book["customer_monthly"]
    assert not cm.duplicated(["CUSTOMER_ID", "SNAPSHOT_DATE"]).any()          # clean version: no duplicates
    assert (cm[["CREDIT_TURNOVER", "DEBIT_TURNOVER", "UNPAID_AMOUNT"]] >= 0).all().all()
    assert cm["DAYS_OVERDRAWN"].between(0, 31).all()
    assert (cm["MIN_BALANCE"] <= cm["AVG_BALANCE"]).all()
    assert set(cm["SEGMENT_AT_SNAPSHOT"]) <= {"250", "270", "260"}


def test_symptoms_move_with_health(small_book):
    x = small_book["truth"].merge(small_book["customer_monthly"], on=["CUSTOMER_ID", "SNAPSHOT_DATE"])
    poor = x["LATENT_HEALTH"] < -1
    good = x["LATENT_HEALTH"] > 1
    # unhealthy customers: more unpaids, more days overdrawn, lower balances
    assert x.loc[poor, "UNPAID_COUNT"].mean() > 3 * x.loc[good, "UNPAID_COUNT"].mean()
    assert x.loc[poor, "DAYS_OVERDRAWN"].mean() > x.loc[good, "DAYS_OVERDRAWN"].mean()
    assert x.loc[poor, "AVG_BALANCE"].median() < x.loc[good, "AVG_BALANCE"].median()


def test_december_seasonality(small_book):
    cm = small_book["customer_monthly"].copy()
    cm["MONTH"] = pd.to_datetime(cm["SNAPSHOT_DATE"]).dt.month
    by_month = cm.groupby("MONTH")["CREDIT_TURNOVER"].median()
    assert by_month[12] > by_month[11]                   # December peak
    assert by_month[1] < by_month[12]                    # January dip


def test_crb_rules(small_book):
    crb = small_book["crb"]
    scored = crb["CRB_SCORE"].dropna()
    assert scored.between(200, 900).all()
    assert (crb["ENQUIRIES_90D"] >= crb["ENQUIRIES_30D"]).all()
    assert (crb["MOBILE_LOANS_NPL"] <= crb["MOBILE_LOANS_ACTIVE"]).all()
    no_hit_share = crb.groupby("CUSTOMER_ID")["CRB_SCORE"].apply(lambda s: s.isna().all()).mean()
    assert 0.02 < no_hit_share < 0.15                     # ~8% have no bureau record


def test_crb_score_tracks_health(small_book):
    x = small_book["truth"].merge(small_book["crb"], on=["CUSTOMER_ID", "SNAPSHOT_DATE"]).dropna(subset=["CRB_SCORE"])
    assert np.corrcoef(x["LATENT_HEALTH"], x["CRB_SCORE"])[0, 1] > 0.7