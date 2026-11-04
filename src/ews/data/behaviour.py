"""ews.data.behaviour — the hidden story and its visible symptoms.

WHAT:  make_macro()            -> macro_monthly            (table 7: the economy)
       make_sector()           -> sector_monthly           (table 8: sector shocks)
       make_truth()            -> _truth_customer_monthly  (table 9: HIDDEN financial health)
       make_customer_monthly() -> customer_monthly         (table 5: account behaviour, PPC)
       make_crb_monthly()      -> crb_monthly              (table 6: credit bureau)
WHY:   Real risk works like this: a business's true financial health can't be seen
       directly; the bank only sees SYMPTOMS (falling inflows, shrinking balances,
       unpaids, bureau deterioration, and later missed instalments). We simulate the
       hidden health, then derive every symptom from it, with noise.
HOW:   LATENT_HEALTH (roughly -3 bad ... +3 good), per customer per month:

         health = own long-run level              (business age, size, affordability)
                - economy stress  x sensitivity   (a downturn peaking around Sep 2024)
                - sector stress   x sensitivity   (e.g. drought in agriculture)
                + one-off shock                   (a few customers suffer a big hit that fades slowly)
                + month-to-month noise            (AR(1): this month resembles last month)

All values are FICTITIOUS assumptions, chosen to look plausible, not NCBA figures.
"""

import numpy as np
import pandas as pd

from ews.data.loans import PRODUCTS

# --- Planted sector shocks: (first month index, last month index, extra stress) ---
# Month index 0 = Jan 2023, 12 = Jan 2024, 24 = Jan 2025, 35 = Dec 2025.
SECTOR_SHOCKS = {
    "Agriculture":  [(8, 14, 0.45)],    # drought: Sep 2023 – Mar 2024
    "Hospitality":  [(14, 17, 0.25)],   # tourism slump: Mar – Jun 2024
    "Transport":    [(18, 23, 0.35)],   # fuel price spike: Jul – Dec 2024
    "Construction": [(26, 33, 0.30)],   # project slowdown: Mar – Oct 2025 (falls in validation/test!)
}
SECTOR_BASE_STRESS = 0.20
MACRO_NORMAL_STRESS = 0.25

# --- Seasonality of cash inflows by calendar month (December peak, January dip) ---
SEASONALITY = {1: 0.90, 2: 0.95, 12: 1.15}

P_SHOCK = 0.07           # share of customers hit by a one-off shock (illness, lost contract, theft...)
P_NO_CRB_HIT = 0.08      # share of customers with no bureau record (thin file)
P_SEGMENT_MIGRATION = 0.015   # share of customers moving out of CSME (to segment "260") during the window


def _sigmoid(x):
    """Squash any number into 0–1 (used to turn a 'risk score' into a probability)."""
    return 1 / (1 + np.exp(-x))


def make_macro(rng: np.random.Generator, snapshots: pd.DatetimeIndex) -> pd.DataFrame:
    """The economy: one row per month. A downturn builds up and peaks around Sep 2024."""
    n = len(snapshots)
    t = np.arange(n)
    downturn = 0.45 * np.exp(-0.5 * ((t - 20) / 4.5) ** 2)              # a smooth "hill" centred on month 20
    stress = np.clip(MACRO_NORMAL_STRESS + downturn + rng.normal(0, 0.02, n), 0, 1)
    lagged = np.concatenate([stress[:1].repeat(2), stress[:-2]])           # interest rates react ~2 months later
    return pd.DataFrame({
        "SNAPSHOT_DATE": snapshots.strftime("%Y-%m-%d"),
        "INFLATION_RATE": np.clip(4.5 + 6 * stress + rng.normal(0, 0.3, n), 2, 12).round(2),
        "CBK_RATE": np.clip(7.5 + 5 * lagged + rng.normal(0, 0.1, n), 6, 14).round(2),
        "UNEMPLOYMENT_PROXY": np.clip(5 + 8 * stress + rng.normal(0, 0.2, n), 3, 15).round(2),
        "ECON_STRESS_INDEX": stress.round(3),
    })


def make_sector(rng: np.random.Generator, snapshots: pd.DatetimeIndex, sectors: list) -> pd.DataFrame:
    """Sector stress: a calm baseline plus the planted shocks (each rises and fades smoothly)."""
    n = len(snapshots)
    rows = []
    for sector in sectors:
        stress = SECTOR_BASE_STRESS + rng.normal(0, 0.02, n)
        for start, end, size in SECTOR_SHOCKS.get(sector, []):
            k = np.arange(end - start + 1)
            stress[start:end + 1] += size * np.sin(np.pi * (k + 1) / (len(k) + 1))   # rise, peak, fade
        rows.append(pd.DataFrame({"SECTOR": sector,
                                  "SNAPSHOT_DATE": snapshots.strftime("%Y-%m-%d"),
                                  "SECTOR_STRESS_INDEX": np.clip(stress, 0, 1).round(3)}))
    return pd.concat(rows, ignore_index=True)


def instalment_to_income_at_start(loans: pd.DataFrame, customers: pd.DataFrame,
                                  first_snapshot: pd.Timestamp) -> pd.Series:
    """Total EMI of loans already on the book at the first snapshot ÷ declared income."""
    booked = pd.to_datetime(loans["BOOKING_DATE"]) <= first_snapshot
    emi = loans[booked].groupby("CUSTOMER_ID")["EMI"].sum()
    income = customers.set_index("CUSTOMER_ID")["DECLARED_MONTHLY_INCOME"]
    return (emi.reindex(income.index).fillna(0) / income).rename("ITI")


def make_truth(rng: np.random.Generator, customers: pd.DataFrame, loans: pd.DataFrame,
               snapshots: pd.DatetimeIndex, macro: pd.DataFrame, sector: pd.DataFrame) -> pd.DataFrame:
    """Hidden financial health per customer per month (returned in LONG format)."""
    n, T = len(customers), len(snapshots)

    # 1) Each customer's long-run level: older businesses, segment 270 and lower
    #    instalment burdens are healthier on average (plus individual variation).
    iti = instalment_to_income_at_start(loans, customers, snapshots[0]).to_numpy()
    level = (rng.normal(0.3, 0.7, n)
             + 0.02 * (customers["BUSINESS_YEARS"].to_numpy() - 10)
             + 0.15 * (customers["SEGMENT"] == "270").to_numpy()
             - 1.5 * np.clip(iti - 0.20, 0, None))

    # 2) How strongly each customer feels the economy and their sector (some are more exposed)
    macro_dev = macro["ECON_STRESS_INDEX"].to_numpy() - MACRO_NORMAL_STRESS          # (T,)
    sector_wide = sector.pivot(index="SECTOR", columns="SNAPSHOT_DATE", values="SECTOR_STRESS_INDEX")
    sector_dev = sector_wide.loc[customers["SECTOR"]].to_numpy() - SECTOR_BASE_STRESS  # (n, T)
    macro_sens = rng.uniform(0.5, 1.5, n)
    sector_sens = rng.uniform(0.5, 1.5, n)

    # 3) One-off shocks: a big drop in a random month that fades slowly (90% stays each month)
    shocked = rng.random(n) < P_SHOCK
    shock_month = rng.integers(0, T, n)
    shock_size = rng.uniform(1.5, 2.8, n)

    # 4) Month-to-month noise with memory (AR(1)): z_t = 0.8 * z_(t-1) + new noise
    health = np.zeros((n, T))
    z = rng.normal(0, 0.5, n)
    shock = np.zeros(n)
    for t in range(T):
        z = 0.8 * z + rng.normal(0, 0.3, n)
        shock = 0.9 * shock - np.where(shocked & (shock_month == t), shock_size, 0.0)
        health[:, t] = (level - 2.0 * macro_sens * macro_dev[t] - 2.5 * sector_sens * sector_dev[:, t]
                        + shock + z)
    health = np.clip(health, -4, 4)

    return pd.DataFrame({
        "CUSTOMER_ID": np.repeat(customers["CUSTOMER_ID"].to_numpy(), T),
        "SNAPSHOT_DATE": np.tile(snapshots.strftime("%Y-%m-%d"), n),
        "LATENT_HEALTH": health.ravel().round(4),
    })


def _wide(truth: pd.DataFrame, n: int, T: int) -> np.ndarray:
    """Health as an (n customers x T months) grid, in the same order as the customers table."""
    return truth["LATENT_HEALTH"].to_numpy().reshape(n, T)


def make_customer_monthly(rng: np.random.Generator, customers: pd.DataFrame, truth: pd.DataFrame,
                          snapshots: pd.DatetimeIndex) -> pd.DataFrame:
    """Account behaviour (turnover, balances, unpaids) and product holdings, driven by health."""
    n, T = len(customers), len(snapshots)
    h = _wide(truth, n, T)
    income = customers["DECLARED_MONTHLY_INCOME"].to_numpy(dtype=float)[:, None]   # (n, 1) column
    season = np.array([SEASONALITY.get(d.month, 1.0) for d in snapshots])[None, :]  # (1, T) row

    # Cash inflows (CTO) rise and fall with health; outflows (DTO) exceed inflows when stressed
    cto = income * np.exp(0.25 * h) * season * rng.lognormal(0, 0.15, (n, T))
    dto = cto * rng.uniform(0.92, 1.04, (n, T)) * np.exp(-0.05 * h)
    credit_count = rng.poisson(np.clip(15 * cto / income, 1, None))
    debit_count = rng.poisson(np.clip(20 * dto / income, 1, None))

    # Balances: comfortable when healthy, overdrawn (negative) when health is very poor
    avg_bal = income * (0.35 + 0.30 * h) + rng.normal(0, 0.10, (n, T)) * income
    min_bal = avg_bal - np.abs(rng.normal(0.30, 0.15, (n, T))) * income
    days_od = np.where(min_bal < 0, np.clip(np.round(31 * _sigmoid(-avg_bal / (0.2 * income))), 1, 31), 0)

    # Unpaid items (returned debit orders / cheques): rare when healthy, frequent when stressed
    unpaid_count = rng.poisson(np.exp(-2.5 - 1.3 * h))
    unpaid_amount = unpaid_count * income * rng.uniform(0.03, 0.15, (n, T))

    # Product holdings (PPC): mostly stable; healthier customers keep term deposits,
    # and a term deposit is broken (closed) if health falls below -1.5 — a classic stress sign
    current_acc = 1 + (rng.random(n) < 0.25)
    savings_acc = rng.poisson(0.6, n)
    debit_cards = rng.binomial(current_acc, 0.8)
    has_td = rng.random(n) < _sigmoid(-1.0 + 0.8 * h[:, 0])
    td_broken = np.cumsum(h < -1.5, axis=1) > 0                              # once broken, stays closed
    term_deposits = np.where(has_td[:, None] & ~td_broken, 1, 0)

    # Segment migration: a few customers move out of CSME (to "260") from a random month onward
    seg = np.repeat(customers["SEGMENT"].to_numpy()[:, None], T, axis=1).astype(object)
    movers = np.where(rng.random(n) < P_SEGMENT_MIGRATION)[0]
    for i in movers:
        seg[i, rng.integers(1, T):] = "260"

    return pd.DataFrame({
        "CUSTOMER_ID": np.repeat(customers["CUSTOMER_ID"].to_numpy(), T),
        "SNAPSHOT_DATE": np.tile(snapshots.strftime("%Y-%m-%d"), n),
        "SEGMENT_AT_SNAPSHOT": seg.ravel(),
        "CREDIT_TURNOVER": cto.ravel().round(2),
        "CREDIT_COUNT": credit_count.ravel(),
        "DEBIT_TURNOVER": dto.ravel().round(2),
        "DEBIT_COUNT": debit_count.ravel(),
        "AVG_BALANCE": avg_bal.ravel().round(2),
        "MIN_BALANCE": min_bal.ravel().round(2),
        "DAYS_OVERDRAWN": days_od.ravel().astype(int),
        "UNPAID_COUNT": unpaid_count.ravel(),
        "UNPAID_AMOUNT": unpaid_amount.ravel().round(2),
        "CURRENT_ACCOUNTS": np.repeat(current_acc, T),
        "SAVINGS_ACCOUNTS": np.repeat(savings_acc, T),
        "TERM_DEPOSITS": term_deposits.ravel(),
        "DEBIT_CARDS": np.repeat(debit_cards, T),
    })


def make_crb_monthly(rng: np.random.Generator, customers: pd.DataFrame, truth: pd.DataFrame,
                     snapshots: pd.DatetimeIndex) -> pd.DataFrame:
    """Credit bureau signals, driven by health. ~8% of customers have no bureau record."""
    n, T = len(customers), len(snapshots)
    h = _wide(truth, n, T)
    income = customers["DECLARED_MONTHLY_INCOME"].to_numpy(dtype=float)[:, None]
    no_hit = rng.random(n) < P_NO_CRB_HIT

    score = np.clip(np.round(620 + 70 * h + rng.normal(0, 25, (n, T))), 200, 900)
    score = np.where(no_hit[:, None], np.nan, score)                         # no record -> blank score

    # Enquiries: stressed businesses shop around for credit
    enq_month = rng.poisson(np.exp(-1.2 - 0.6 * h))
    enq_30 = enq_month
    enq_90 = enq_month + np.pad(enq_month, ((0, 0), (1, 0)))[:, :-1] + np.pad(enq_month, ((0, 0), (2, 0)))[:, :-2]
    applications = enq_90 + rng.poisson(0.2, (n, T))

    # Other lenders: accounts, commitments, arrears (arrears appear when health is poor)
    other_acc = rng.poisson(1.0, n)[:, None] * np.ones((1, T), dtype=int)
    other_closed = rng.poisson(1.5, n)[:, None] * np.ones((1, T), dtype=int)
    commitment = other_acc * income * rng.uniform(0.04, 0.12, (n, 1))
    other_dpd = np.where((h < -1.2) & (other_acc > 0), rng.integers(0, 150, (n, T)), 0)
    max_arrears_12m = pd.DataFrame(other_dpd).T.rolling(12, min_periods=1).max().T.to_numpy()
    other_npl = np.where(other_dpd >= 90, 1, 0)
    past_due = np.where(other_dpd > 0, commitment * other_dpd / 30, 0.0)

    mobile_active = rng.poisson(np.exp(-0.5 - 0.4 * h))
    mobile_npl = rng.binomial(mobile_active, _sigmoid(-3.0 - 1.2 * h))
    tu_listed = ((other_npl > 0) | (mobile_npl > 0)).astype(int)

    # No bureau record: nothing reported anywhere
    blank = no_hit[:, None]
    def zero_if_no_hit(a):
        return np.where(blank, 0, a)

    return pd.DataFrame({
        "CUSTOMER_ID": np.repeat(customers["CUSTOMER_ID"].to_numpy(), T),
        "SNAPSHOT_DATE": np.tile(snapshots.strftime("%Y-%m-%d"), n),
        "CRB_SCORE": score.ravel(),
        "ENQUIRIES_30D": zero_if_no_hit(enq_30).ravel(),
        "ENQUIRIES_90D": zero_if_no_hit(enq_90).ravel(),
        "CREDIT_APPLICATIONS": zero_if_no_hit(applications).ravel(),
        "OTHER_LENDER_ACCOUNTS": zero_if_no_hit(other_acc).ravel(),
        "OTHER_LENDER_CLOSED_ACCOUNTS": zero_if_no_hit(other_closed).ravel(),
        "OTHER_LENDER_NPL": zero_if_no_hit(other_npl).ravel(),
        "OTHER_LENDER_MONTHLY_COMMITMENT": zero_if_no_hit(commitment).ravel().round(2),
        "OTHER_LENDER_PAST_DUE_AMOUNT": zero_if_no_hit(past_due).ravel().round(2),
        "MAX_ARREARS_OTHER_12M": zero_if_no_hit(max_arrears_12m).ravel().astype(int),
        "MOBILE_LOANS_ACTIVE": zero_if_no_hit(mobile_active).ravel(),
        "MOBILE_LOANS_NPL": zero_if_no_hit(mobile_npl).ravel(),
        "TU_LISTED_FLAG": zero_if_no_hit(tu_listed).ravel(),
    })


def revolving_products() -> list:
    """Products that work as a limit (used by the delinquency step)."""
    return [p for p, s in PRODUCTS.items() if s["kind"] == "revolving"]