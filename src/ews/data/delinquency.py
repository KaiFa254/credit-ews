"""ews.data.delinquency — turn each loan's contractual life into a REAL repayment history.

WHAT:  apply_delinquency() takes loan_monthly from Lesson 7 (perfect, on-time payment) and
       adds DPD, ARREARS_AMOUNT, MISSED_INSTALMENT_FLAG, RESTRUCTURED_FLAG, restructures
       and write-offs, driven by the customer's hidden health each month.
WHY:   Days past due is the outcome the model predicts. Making it depend on health means
       the earlier symptoms (falling turnover, unpaids, bureau stress) genuinely precede it.
HOW:   Each loan, month by month, is a small "state machine":

         current (DPD 0) ──miss──► 1–29 DPD ──miss again──► +30 DPD each month ... ──► write-off (180+)
              ▲                        │                          │
              └────────── cure (pays all arrears) ◄───────────────┘     restructure (60–150 DPD) resets DPD to 0

       - chance of a miss rises as health falls and the instalment burden rises
       - chance of curing rises with health
       - "technical" arrears: a few healthy customers pay a few days late and cure next month
       Simplification (documented): a loan that reaches its contractual closure while in
       arrears is treated as settled at closure.
"""

import numpy as np
import pandas as pd

from ews.data.behaviour import instalment_to_income_at_start, revolving_products

P_TECHNICAL = 0.02         # monthly chance of a short "technical" late payment (any customer)
P_RESTRUCTURE = 0.12       # monthly chance a 60–150 DPD loan is restructured instead of rolling
WRITE_OFF_DPD = 180        # at or beyond this DPD the loan may be written off
P_WRITE_OFF = 0.5          # monthly chance of write-off once at or beyond WRITE_OFF_DPD


def _sigmoid(x):
    return 1 / (1 + np.exp(-x))


def apply_delinquency(rng: np.random.Generator, loans: pd.DataFrame, loan_monthly: pd.DataFrame,
                      truth: pd.DataFrame, customers: pd.DataFrame,
                      first_snapshot: pd.Timestamp) -> pd.DataFrame:
    """Return loan_monthly with arrears columns added (and rows after a write-off removed)."""
    lm = loan_monthly.merge(loans[["LOAN_ID", "CUSTOMER_ID", "PRODUCT", "EMI", "LOAN_AMOUNT"]],
                            on="LOAN_ID", how="left", validate="many_to_one")
    lm = lm.merge(truth, on=["CUSTOMER_ID", "SNAPSHOT_DATE"], how="left", validate="many_to_one")
    iti = instalment_to_income_at_start(loans, customers, first_snapshot)
    lm["ITI"] = lm["CUSTOMER_ID"].map(iti).fillna(0)
    lm = lm.sort_values(["LOAN_ID", "SNAPSHOT_DATE"]).reset_index(drop=True)

    revolving = set(revolving_products())
    n = len(lm)
    dpd_out = np.zeros(n, dtype=int)
    missed_out = np.zeros(n, dtype=int)
    restr_out = np.zeros(n, dtype=int)
    keep = np.ones(n, dtype=bool)
    status = lm["ACCOUNT_STATUS"].to_numpy(dtype=object).copy()
    reason = lm["CLOSURE_REASON"].to_numpy(dtype=object).copy()

    health = lm["LATENT_HEALTH"].to_numpy()
    iti_arr = lm["ITI"].to_numpy()
    loan_ids = lm["LOAN_ID"].to_numpy()

    # Process each loan's months in order (rows for one loan are next to each other)
    starts = np.flatnonzero(np.r_[True, loan_ids[1:] != loan_ids[:-1]])
    ends = np.r_[starts[1:], n]
    for s, e in zip(starts, ends):
        dpd, technical, written_off = 0, False, False
        for j in range(s, e):
            if written_off:                                   # nothing after a write-off
                keep[j] = False
                continue
            if status[j] == "CLOSED":                         # contractual closure: settled
                dpd = 0
                dpd_out[j] = 0
                continue
            h = health[j]
            if dpd == 0:
                p_miss = _sigmoid(-4.0 - 1.5 * h + 2.0 * (iti_arr[j] - 0.25))
                u = rng.random()
                if u < p_miss:                                # genuine miss: 1–29 DPD at month-end
                    dpd, technical = int(rng.integers(1, 30)), False
                    missed_out[j] = 1
                elif u < p_miss + P_TECHNICAL:                # technical: a few days late
                    dpd, technical = int(rng.integers(1, 8)), True
            else:
                p_cure = 0.9 if technical else _sigmoid(0.3 + 1.5 * h)
                if rng.random() < p_cure:
                    dpd, technical = 0, False                 # pays everything owed
                else:
                    dpd = min(dpd + 30, 360)                  # another month unpaid
                    missed_out[j] = 1
                    technical = False
            # Restructure: the bank reschedules a struggling loan; DPD resets to 0
            if 60 <= dpd <= 150 and rng.random() < P_RESTRUCTURE:
                dpd = 0
                restr_out[j] = 1
                status[j] = "RESTRUCTURED"
            # Write-off: the bank gives up on a long-overdue loan
            if dpd >= WRITE_OFF_DPD and rng.random() < P_WRITE_OFF:
                status[j], reason[j] = "WRITTEN_OFF", "WRITTEN_OFF"
                written_off = True
            dpd_out[j] = dpd

    lm["DPD"] = dpd_out
    lm["MISSED_INSTALMENT_FLAG"] = missed_out
    lm["RESTRUCTURED_FLAG"] = restr_out
    lm["ACCOUNT_STATUS"] = status
    lm["CLOSURE_REASON"] = reason

    # Arrears amount and balances
    months_overdue = np.ceil(lm["DPD"] / 30)
    is_rev = lm["PRODUCT"].isin(revolving).to_numpy()
    # instalment: unpaid instalments pile up on top of the scheduled balance
    inst_arrears = months_overdue * lm["EMI"]
    # revolving: stress pushes utilisation up (even beyond the limit), arrears = missed minimum payments
    util = lm["LIMIT_UTILISATION"].fillna(0) + 0.15 * np.clip(-lm["LATENT_HEALTH"], 0, None) + 0.15 * (lm["DPD"] > 0)
    util = np.clip(util, 0, 1.3)
    rev_balance = util * lm["LOAN_AMOUNT"]
    rev_arrears = months_overdue * np.maximum(0.05 * rev_balance, 1_000)

    lm["ARREARS_AMOUNT"] = np.where(is_rev, rev_arrears, inst_arrears).round(2)
    lm["LIMIT_UTILISATION"] = np.where(is_rev, util.round(3), np.nan)
    lm["OUTSTANDING_BALANCE"] = np.where(
        is_rev, rev_balance, lm["OUTSTANDING_BALANCE"] + np.where(lm["DPD"] > 0, inst_arrears, 0)).round(2)
    closed = lm["ACCOUNT_STATUS"] == "CLOSED"
    lm.loc[closed, ["OUTSTANDING_BALANCE", "ARREARS_AMOUNT"]] = 0.0

    cols = ["LOAN_ID", "SNAPSHOT_DATE", "MOB", "OUTSTANDING_BALANCE", "LIMIT_UTILISATION", "DPD",
            "ARREARS_AMOUNT", "MISSED_INSTALMENT_FLAG", "RESTRUCTURED_FLAG", "ACCOUNT_STATUS", "CLOSURE_REASON"]
    return lm.loc[keep, cols].reset_index(drop=True)