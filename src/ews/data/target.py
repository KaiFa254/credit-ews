"""ews.data.target — build the target TARGET_DPD30_90D per customer per month.

WHAT:  build_target() returns one row per (CUSTOMER_ID, SNAPSHOT_DATE) with the customer's
       worst DPD now, the worst DPD in the next 3 months, a TARGET_STATUS and the label.
WHY:   The label is the answer the model learns. Getting it exactly right (population,
       future window, exits, immature months) matters more than any modelling trick.
HOW:   For each customer and snapshot, following the rules in docs/data_dictionary.md:

         EXCLUDED_NO_LOANS   no active loan at the snapshot (nothing to warn about)
         EXCLUDED_NOT_CSME   customer not in segments 250/270 at the snapshot
         EXCLUDED_DPD        worst DPD now > 5 (already slipping or bad)
         IMMATURE            fewer than 3 future months exist in the data
         INDETERMINATE       customer left segments 250/270 within the window
         LABELLED            label = 1 if, in the NEXT 3 months, worst DPD >= 30, or any
                             loan is restructured or written off; otherwise 0

       Loans that close in the window (paid off / matured / refinanced) simply stop having
       rows. Because every closure is RECORDED, "no future rows" means "no arrears" -> 0.
       Refinancing is followed automatically: the new loan belongs to the same customer.
"""

import numpy as np
import pandas as pd

CSME_SEGMENTS = {"250", "270"}


def build_target(loan_monthly: pd.DataFrame, loans: pd.DataFrame, customer_monthly: pd.DataFrame,
                 snapshots: pd.DatetimeIndex, dpd_threshold: int = 30, horizon_months: int = 3,
                 max_dpd_at_snapshot: int = 5) -> pd.DataFrame:
    snap_text = list(snapshots.strftime("%Y-%m-%d"))
    snap_idx = {s: i for i, s in enumerate(snap_text)}

    # --- Customer x month facts from loans (rolled up: worst across ALL the customer's loans) ---
    lm = loan_monthly.merge(loans[["LOAN_ID", "CUSTOMER_ID"]], on="LOAN_ID", how="left", validate="many_to_one")
    lm["ACTIVE"] = lm["ACCOUNT_STATUS"].isin(["ACTIVE", "RESTRUCTURED"])
    lm["BAD_EVENT"] = (lm["DPD"] >= dpd_threshold) | (lm["RESTRUCTURED_FLAG"] == 1) | \
                      (lm["ACCOUNT_STATUS"] == "WRITTEN_OFF")
    cm = (lm.groupby(["CUSTOMER_ID", "SNAPSHOT_DATE"])
            .agg(DPD_NOW=("DPD", "max"), HAS_ACTIVE_LOAN=("ACTIVE", "any"), BAD_EVENT=("BAD_EVENT", "any"))
            .reset_index())

    # --- Full customer x month grid (every customer, every month), filled where no loan rows ---
    grid = customer_monthly[["CUSTOMER_ID", "SNAPSHOT_DATE", "SEGMENT_AT_SNAPSHOT"]].drop_duplicates(
        ["CUSTOMER_ID", "SNAPSHOT_DATE"])
    df = grid.merge(cm, on=["CUSTOMER_ID", "SNAPSHOT_DATE"], how="left", validate="one_to_one")
    df["DPD_NOW"] = df["DPD_NOW"].fillna(0).astype(int)
    # customers with no loan rows this month: no active loan, no bad event
    df["HAS_ACTIVE_LOAN"] = df["HAS_ACTIVE_LOAN"].astype("boolean").fillna(False).astype(bool)
    df["BAD_EVENT"] = df["BAD_EVENT"].astype("boolean").fillna(False).astype(bool)
    df["IN_CSME"] = df["SEGMENT_AT_SNAPSHOT"].isin(CSME_SEGMENTS)
    df["T"] = df["SNAPSHOT_DATE"].map(snap_idx)
    df = df.sort_values(["CUSTOMER_ID", "T"]).reset_index(drop=True)

    # --- Look ahead 1..horizon months within each customer (shift(-k) = value k months later) ---
    g = df.groupby("CUSTOMER_ID")
    future_bad = np.zeros(len(df), dtype=bool)
    future_dpd = np.zeros(len(df))
    left_csme = np.zeros(len(df), dtype=bool)
    for k in range(1, horizon_months + 1):
        future_bad |= g["BAD_EVENT"].shift(-k, fill_value=False).to_numpy(dtype=bool)
        future_dpd = np.maximum(future_dpd, g["DPD_NOW"].shift(-k, fill_value=0).to_numpy())
        left_csme |= ~g["IN_CSME"].shift(-k, fill_value=True).to_numpy(dtype=bool)

    mature = df["T"] <= len(snapshots) - 1 - horizon_months
    status = np.select(
        [~df["HAS_ACTIVE_LOAN"],
         ~df["IN_CSME"],
         df["DPD_NOW"] > max_dpd_at_snapshot,
         ~mature,
         left_csme],
        ["EXCLUDED_NO_LOANS", "EXCLUDED_NOT_CSME", "EXCLUDED_DPD", "IMMATURE", "INDETERMINATE"],
        default="LABELLED")

    out = df[["CUSTOMER_ID", "SNAPSHOT_DATE", "DPD_NOW"]].copy()
    out["WORST_DPD_NEXT_3M"] = np.where(mature, future_dpd, np.nan)
    out["TARGET_STATUS"] = status
    # label only for LABELLED rows; every other row gets a blank (<NA>), never a 0
    out["TARGET_DPD30_90D"] = pd.array(future_bad.astype(int), dtype="Int64")
    out.loc[out["TARGET_STATUS"] != "LABELLED", "TARGET_DPD30_90D"] = pd.NA
    return out