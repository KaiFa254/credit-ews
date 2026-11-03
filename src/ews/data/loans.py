"""ews.data.loans — generate loans (table 3) and their month-by-month life (table 4).

WHAT:  make_loans()        -> loans: one row per loan, terms at booking
       make_loan_monthly() -> loan_monthly: one row per loan per month-end snapshot
WHY:   Loans are what the bank lends and what can go into arrears. This lesson builds
       their CONTRACTUAL life (balances, utilisation, closures). Days past due and
       arrears are added in Lesson 9, driven by each customer's hidden health (Lesson 8).
HOW:   Two kinds of product:
         - INSTALMENT (asset finance, mortgage, unsecured business loan): a fixed monthly
           instalment (EMI) that pays the balance down to zero by maturity.
         - REVOLVING (overdraft, credit card, mobile loan): a LIMIT the customer draws on;
           the balance goes up and down; no fixed end date.
       Loan sizes are tied to each customer's income, so affordability is realistic.

All values are FICTITIOUS assumptions for a plausible CSME book, not NCBA terms.
"""

import numpy as np
import pandas as pd

# =============================================================================
# Product menu (ASSUMPTIONS). For each product:
#   p_hold       chance a customer holds one at the start (Jan 2023)
#   kind         "instalment" or "revolving"
#   income_mult  typical loan size (or limit) as a multiple of monthly income
#   rate         annual interest rate range (%)
#   tenor        contractual term range in months (instalment products only)
#   secured      1 = backed by an asset (vehicle, property)
# =============================================================================
PRODUCTS = {
    "ASSET_FINANCE": {"p_hold": 0.30, "kind": "instalment", "income_mult": 4.0,
                      "rate": (13.0, 17.0), "tenor": (36, 60), "secured": 1},
    "MORTGAGE":      {"p_hold": 0.12, "kind": "instalment", "income_mult": 12.0,
                      "rate": (12.0, 15.0), "tenor": (120, 240), "secured": 1},
    "UNSECURED_BL":  {"p_hold": 0.45, "kind": "instalment", "income_mult": 2.0,
                      "rate": (15.0, 20.0), "tenor": (12, 48), "secured": 0},
    "OVERDRAFT":     {"p_hold": 0.40, "kind": "revolving", "income_mult": 1.0,
                      "rate": (14.0, 18.0), "tenor": None, "secured": 0},
    "CREDIT_CARD":   {"p_hold": 0.25, "kind": "revolving", "income_mult": 0.4,
                      "rate": (24.0, 30.0), "tenor": None, "secured": 0},
    "MOBILE_LOAN":   {"p_hold": 0.15, "kind": "revolving", "income_mult": 0.1,
                      "rate": (28.0, 36.0), "tenor": None, "secured": 0},
}
INSTALMENT = [p for p, s in PRODUCTS.items() if s["kind"] == "instalment"]

P_NEW_LOAN = 0.25        # chance a customer takes ONE extra instalment loan during the 36 months
P_REFINANCE = 0.08       # chance an unsecured business loan is refinanced (topped up) in the window
P_EARLY_PAYOFF = 0.10    # chance an instalment loan is settled early in the window
EARLIEST_BOOKING = pd.Timestamp("2015-01-01")   # matches the data dictionary

# Helper columns used only inside generation (dropped before saving: a real loan
# table never knows in advance when a loan will be settled or refinanced).
PLAN_COLUMNS = ["PLANNED_EXIT_SNAPSHOT", "PLANNED_EXIT_REASON"]


def calc_emi(principal: float, annual_rate_pct: float, tenor_months: int) -> float:
    """Monthly instalment (EMI) for a fully-amortising loan: the "annuity" formula banks use.

        EMI = P * r / (1 - (1 + r) ** -n)
        P = amount borrowed, r = monthly interest rate (annual % / 12 / 100), n = months

    Example: 1,000,000 at 12% for 12 months -> 88,848.79 per month.
    """
    r = annual_rate_pct / 12 / 100
    return principal * r / (1 - (1 + r) ** -tenor_months)


def balance_after(principal: float, annual_rate_pct: float, emi: float, months_paid: int) -> float:
    """Outstanding balance after `months_paid` instalments (never below zero).

    Each month interest is added to the balance, then the EMI is subtracted. Early on most
    of the EMI is interest; later most of it repays principal, so the balance falls faster.
    """
    r = annual_rate_pct / 12 / 100
    growth = (1 + r) ** months_paid
    return max(principal * growth - emi * (growth - 1) / r, 0.0)


def months_between(earlier: pd.Timestamp, later: pd.Timestamp) -> int:
    """Whole calendar months from `earlier` to `later` (30 Dec -> 31 Dec = 0; -> 31 Jan = 1)."""
    return (later.year - earlier.year) * 12 + (later.month - earlier.month)


def _random_day_in_month(rng: np.random.Generator, month_end: pd.Timestamp) -> pd.Timestamp:
    """A random calendar day inside the month that ends on `month_end`."""
    return month_end - pd.DateOffset(days=int(rng.integers(0, month_end.day)))


def _new_loan(rng, customer_id, income, product, booking_date, amount=None, refinanced_from=None):
    """Build one loan row (a dictionary) with its terms at booking."""
    spec = PRODUCTS[product]
    if amount is None:   # size tied to income, with a right-skewed spread (log-normal)
        amount = income * spec["income_mult"] * rng.lognormal(0, 0.4)
    amount = float(max(round(amount / 1_000) * 1_000, 5_000))     # whole thousands, at least 5,000
    rate = round(float(rng.uniform(*spec["rate"])), 2)

    row = {
        "CUSTOMER_ID": customer_id, "PRODUCT": product, "SECURED_FLAG": spec["secured"],
        "BOOKING_DATE": booking_date, "LOAN_AMOUNT": amount, "INTEREST_RATE": rate,
        "TENOR_MONTHS": np.nan, "EMI": 0.0, "REPAYMENT_FREQUENCY": "MONTHLY",
        "MATURITY_DATE": pd.NaT, "REFINANCED_FROM_LOAN_ID": refinanced_from,
        "PLANNED_EXIT_SNAPSHOT": pd.NaT, "PLANNED_EXIT_REASON": None,
    }
    if spec["kind"] == "instalment":                  # revolving products have no tenor/EMI/maturity
        tenor = int(rng.integers(spec["tenor"][0], spec["tenor"][1] + 1))
        row["TENOR_MONTHS"] = tenor
        row["EMI"] = round(calc_emi(amount, rate, tenor), 2)
        row["MATURITY_DATE"] = booking_date + pd.DateOffset(months=tenor)
    return row


def make_loans(rng: np.random.Generator, customers: pd.DataFrame,
               snapshots: pd.DatetimeIndex) -> pd.DataFrame:
    """Create the loans table in four steps:
       1) loans already on the book at the first snapshot
       2) one new instalment loan for some customers during the window
       3) plan which instalment loans are paid off early or refinanced (and when)
       4) add the replacement loan for each refinanced loan
    """
    first = snapshots[0]
    rows = []

    for cust in customers.itertuples(index=False):
        since = pd.Timestamp(cust.CUSTOMER_SINCE)

        # --- 1) Loans already on the book at the first snapshot ---
        held = [p for p, s in PRODUCTS.items() if rng.random() < s["p_hold"]]
        if not held:                                   # every customer holds at least one loan
            held = ["UNSECURED_BL"]
        for product in held:
            spec = PRODUCTS[product]
            # Loan age (months) at the first snapshot: booked after the customer joined and after
            # 2015; instalment loans must be younger than their tenor so they are still running.
            max_age = min(months_between(max(since, EARLIEST_BOOKING), first), 120)
            if spec["kind"] == "instalment":
                max_age = min(max_age, spec["tenor"][0] - 1)
            age = int(rng.integers(0, max(max_age, 0) + 1))
            booking_month_end = first - pd.offsets.MonthEnd(age) if age else first
            booking = max(_random_day_in_month(rng, booking_month_end), since)
            rows.append(_new_loan(rng, cust.CUSTOMER_ID, cust.DECLARED_MONTHLY_INCOME, product, booking))

        # --- 2) Some customers take one NEW instalment loan during the window ---
        if rng.random() < P_NEW_LOAN:
            product = rng.choice(INSTALMENT, p=[0.35, 0.10, 0.55])     # AF, mortgage, unsecured
            month_end = snapshots[int(rng.integers(1, len(snapshots)))]
            rows.append(_new_loan(rng, cust.CUSTOMER_ID, cust.DECLARED_MONTHLY_INCOME,
                                  product, _random_day_in_month(rng, month_end)))

    loans = pd.DataFrame(rows)
    loans.insert(0, "LOAN_ID", [f"L{i:07d}" for i in range(1, len(loans) + 1)])   # L0000001, ...

    # --- 3) Plan early payoffs and refinancing (instalment loans, at least 6 months on book) ---
    for i, loan in loans.iterrows():
        if PRODUCTS[loan.PRODUCT]["kind"] != "instalment":
            continue
        start_idx = max(months_between(first, loan.BOOKING_DATE) + 6, 1)
        end_idx = min(months_between(first, loan.MATURITY_DATE) - 1, len(snapshots) - 1)
        if start_idx > end_idx:                        # loan doesn't live long enough in the window
            continue
        u = rng.random()
        if loan.PRODUCT == "UNSECURED_BL" and u < P_REFINANCE:
            reason = "REFINANCED"
        elif u < P_REFINANCE + P_EARLY_PAYOFF:
            reason = "PAID_OFF"
        else:
            continue
        loans.at[i, "PLANNED_EXIT_SNAPSHOT"] = snapshots[int(rng.integers(start_idx, end_idx + 1))]
        loans.at[i, "PLANNED_EXIT_REASON"] = reason

    # --- 4) Each refinanced loan is replaced by a NEW, larger loan booked in the same month ---
    income = customers.set_index("CUSTOMER_ID")["DECLARED_MONTHLY_INCOME"]
    refi_rows = []
    for loan in loans[loans["PLANNED_EXIT_REASON"] == "REFINANCED"].itertuples(index=False):
        months_paid = months_between(loan.BOOKING_DATE, loan.PLANNED_EXIT_SNAPSHOT)
        remaining = balance_after(loan.LOAN_AMOUNT, loan.INTEREST_RATE, loan.EMI, months_paid)
        refi_rows.append(_new_loan(
            rng, loan.CUSTOMER_ID, income[loan.CUSTOMER_ID], "UNSECURED_BL",
            booking_date=loan.PLANNED_EXIT_SNAPSHOT - pd.DateOffset(days=1),   # same month as the closure
            amount=remaining * 1.5,                                          # top-up: 50% more than owed
            refinanced_from=loan.LOAN_ID))
    loans = _dates_to_text(loans)
    if refi_rows:
        refi = pd.DataFrame(refi_rows)
        start = len(loans) + 1
        refi.insert(0, "LOAN_ID", [f"L{i:07d}" for i in range(start, start + len(refi))])
        loans = pd.concat([loans, _dates_to_text(refi)], ignore_index=True)   # stack the two tables

    loans["TENOR_MONTHS"] = loans["TENOR_MONTHS"].astype("Int64")   # whole numbers, blanks allowed
    return loans


def _dates_to_text(df: pd.DataFrame) -> pd.DataFrame:
    """Write date columns as YYYY-MM-DD text (blank stays blank), like the customers table."""
    df = df.copy()
    for col in ["BOOKING_DATE", "MATURITY_DATE", "PLANNED_EXIT_SNAPSHOT"]:
        df[col] = pd.to_datetime(df[col]).dt.strftime("%Y-%m-%d")
    return df


def make_loan_monthly(rng: np.random.Generator, loans: pd.DataFrame,
                      snapshots: pd.DatetimeIndex) -> pd.DataFrame:
    """Create loan_monthly: one row per loan for every month-end it is on the book.

    A loan appears from the first month-end on/after booking and disappears after the
    month it closes. The closing month has ACCOUNT_STATUS = CLOSED and a CLOSURE_REASON.
    DPD, arrears, missed instalments and restructures are added in Lesson 9.
    """
    last = snapshots[-1]
    out = []

    for loan in loans.itertuples(index=False):
        booking = pd.Timestamp(loan.BOOKING_DATE)
        is_instalment = PRODUCTS[loan.PRODUCT]["kind"] == "instalment"

        # When does this loan leave the book (if within the window), and why?
        exit_snap, exit_reason = pd.NaT, None
        if pd.notna(loan.PLANNED_EXIT_SNAPSHOT):                     # early payoff or refinance
            exit_snap, exit_reason = pd.Timestamp(loan.PLANNED_EXIT_SNAPSHOT), loan.PLANNED_EXIT_REASON
        elif is_instalment:                                          # natural maturity
            maturity_snap = pd.Timestamp(loan.MATURITY_DATE) + pd.offsets.MonthEnd(0)
            if maturity_snap <= last:
                exit_snap, exit_reason = maturity_snap, "MATURED"

        # Revolving: a starting utilisation per loan. Beta(2, 3) gives values between 0 and 1,
        # mostly 20–60% (a typical overdraft is partly drawn, rarely empty or maxed out).
        util = float(rng.beta(2, 3)) if not is_instalment else np.nan

        for snap in snapshots:
            if snap < booking + pd.offsets.MonthEnd(0):               # not booked yet
                continue
            if pd.notna(exit_snap) and snap > exit_snap:             # already closed: no more rows
                break
            mob = months_between(booking, snap)                      # months on book
            closing = pd.notna(exit_snap) and snap == exit_snap

            if is_instalment:
                balance = 0.0 if closing else balance_after(loan.LOAN_AMOUNT, loan.INTEREST_RATE,
                                                            loan.EMI, mob)
                utilisation = np.nan                                 # not applicable
            else:
                util = float(np.clip(util + rng.normal(0, 0.05), 0.0, 1.0))   # small monthly wiggle
                utilisation = round(util, 3)
                balance = util * loan.LOAN_AMOUNT

            out.append({
                "LOAN_ID": loan.LOAN_ID,
                "SNAPSHOT_DATE": snap.strftime("%Y-%m-%d"),
                "MOB": mob,
                "OUTSTANDING_BALANCE": round(balance, 2),
                "LIMIT_UTILISATION": utilisation,
                "ACCOUNT_STATUS": "CLOSED" if closing else "ACTIVE",
                "CLOSURE_REASON": exit_reason if closing else None,
            })

    return pd.DataFrame(out)