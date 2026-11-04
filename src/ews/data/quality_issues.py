"""ews.data.quality_issues — deliberately plant realistic data problems, and log every one.

WHAT:  plant_issues() takes the CLEAN tables and returns DIRTY copies plus a log (a table)
       listing exactly what was changed, where, and from what to what.
WHY:   Real extracts are messy. Stage 3 (EDA) and Stage 4 (validation and cleaning) teach you
       to find and fix problems; the log lets you check your cleaning caught everything.
HOW:   Each planted issue is small and realistic. The clean originals are never modified
       (we work on copies). The log is saved as a _truth_ file: never a model input.

Planted (see docs/planted_issues.md): missing values, a partly missing monthly extract,
exact and key duplicates, invalid values, outliers (fat-finger errors), inconsistent and
unexpected categories, mixed date formats, and orphan loans.
NOT planted (these are REAL structure, not errors): blank LIMIT_UTILISATION on instalment
loans, blank TENOR/MATURITY on revolving products, blank CRB_SCORE for no-hit customers.
"""

import numpy as np
import pandas as pd


def plant_issues(rng: np.random.Generator, tables: dict) -> tuple[dict, pd.DataFrame]:
    t = {name: df.copy() for name, df in tables.items()}     # work on COPIES only
    log = []

    def note(table, issue, column, key, before, after, description):
        log.append({"TABLE": table, "ISSUE_TYPE": issue, "COLUMN": column, "ROW_KEY": key,
                    "ORIGINAL_VALUE": before, "PLANTED_VALUE": after, "DESCRIPTION": description})

    def sample(df, k):                                        # k random row positions
        return rng.choice(len(df), size=min(k, len(df)), replace=False)

    # ---------------- customers ----------------
    c = t["customers"]
    c["SEGMENT"] = c["SEGMENT"].astype(object)
    for i in sample(c, int(0.02 * len(c))):                  # missing income (2%)
        note("customers", "MISSING_VALUE", "DECLARED_MONTHLY_INCOME", c.at[i, "CUSTOMER_ID"],
             c.at[i, "DECLARED_MONTHLY_INCOME"], None, "income not captured at onboarding")
        c.at[i, "DECLARED_MONTHLY_INCOME"] = np.nan
    for i in sample(c, int(0.01 * len(c))):                  # missing town (1%)
        note("customers", "MISSING_VALUE", "TOWN", c.at[i, "CUSTOMER_ID"], c.at[i, "TOWN"], None,
             "town left blank")
        c.at[i, "TOWN"] = None
    for i, bad in zip(sample(c, 10), [150, 150, 150, 150, 150, 150, -3, -3, -3, -3]):   # impossible ages
        note("customers", "INVALID_VALUE", "AGE", c.at[i, "CUSTOMER_ID"], c.at[i, "AGE"], bad,
             "age outside 21–75 (typing error)")
        c.at[i, "AGE"] = bad
    variants = {"Nairobi": ["NAIROBI ", "nairobi", "Nrb"], "Coast": ["COAST", "coast "],
                "Rift Valley": ["Rift valley", "RIFT VALLEY"]}
    for i in sample(c, int(0.03 * len(c))):                  # inconsistent region spellings (3%)
        orig = c.at[i, "REGION"]
        if orig in variants:
            new = rng.choice(variants[orig])
            note("customers", "INCONSISTENT_CATEGORY", "REGION", c.at[i, "CUSTOMER_ID"], orig, new,
                 "same region, different spelling/case/spaces")
            c.at[i, "REGION"] = new
    sector_variants = {"Trade": "trade", "Agriculture": "Agri", "Transport": "TRANSPORT "}
    for i in sample(c, int(0.02 * len(c))):                  # inconsistent sector spellings (2%)
        orig = c.at[i, "SECTOR"]
        if orig in sector_variants:
            note("customers", "INCONSISTENT_CATEGORY", "SECTOR", c.at[i, "CUSTOMER_ID"], orig,
                 sector_variants[orig], "same sector, different spelling")
            c.at[i, "SECTOR"] = sector_variants[orig]
    for i in sample(c, int(0.02 * len(c))):                  # inconsistent gender codes (2%)
        orig = c.at[i, "GENDER"]
        new = {"M": "Male", "F": "F "}[orig]
        note("customers", "INCONSISTENT_CATEGORY", "GENDER", c.at[i, "CUSTOMER_ID"], orig, new,
             "gender coded differently")
        c.at[i, "GENDER"] = new
    for i in sample(c, 5):                                   # unexpected segment code
        note("customers", "UNEXPECTED_CATEGORY", "SEGMENT", c.at[i, "CUSTOMER_ID"], c.at[i, "SEGMENT"], "999",
             "segment code not in the allowed list")
        c.at[i, "SEGMENT"] = "999"
    for i in sample(c, int(0.03 * len(c))):                  # mixed date format (3%): DD/MM/YYYY
        orig = c.at[i, "CUSTOMER_SINCE"]
        new = pd.Timestamp(orig).strftime("%d/%m/%Y")
        note("customers", "MIXED_DATE_FORMAT", "CUSTOMER_SINCE", c.at[i, "CUSTOMER_ID"], orig, new,
             "date written DD/MM/YYYY instead of YYYY-MM-DD")
        c.at[i, "CUSTOMER_SINCE"] = new

    # ---------------- loans ----------------
    ln = t["loans"]
    for i in sample(ln, 3):                                  # fat-finger outlier amount
        note("loans", "OUTLIER", "LOAN_AMOUNT", ln.at[i, "LOAN_ID"], ln.at[i, "LOAN_AMOUNT"], 9_999_999_999.0,
             "absurd loan amount (typing error)")
        ln.at[i, "LOAN_AMOUNT"] = 9_999_999_999.0
    for i in sample(ln, 5):                                  # unexpected product code
        note("loans", "UNEXPECTED_CATEGORY", "PRODUCT", ln.at[i, "LOAN_ID"], ln.at[i, "PRODUCT"], "LEASE",
             "product code not in the allowed list")
        ln.at[i, "PRODUCT"] = "LEASE"
    orphans = ln.iloc[sample(ln, 12)].copy()                 # orphan loans: customer doesn't exist
    orphans["LOAN_ID"] = [f"L9{k:06d}" for k in range(len(orphans))]
    orphans["CUSTOMER_ID"] = [f"C9{k:05d}" for k in range(len(orphans))]
    for row in orphans.itertuples(index=False):
        note("loans", "ORPHAN_RECORD", "CUSTOMER_ID", row.LOAN_ID, None, row.CUSTOMER_ID,
             "loan whose customer is not in the customers table")
    t["loans"] = pd.concat([ln, orphans], ignore_index=True)

    # ---------------- loan_monthly ----------------
    lm = t["loan_monthly"]
    for i in sample(lm, 10):                                 # impossible negative DPD
        note("loan_monthly", "INVALID_VALUE", "DPD", f"{lm.at[i, 'LOAN_ID']}|{lm.at[i, 'SNAPSHOT_DATE']}",
             lm.at[i, "DPD"], -5, "negative days past due")
        lm.at[i, "DPD"] = -5
    dup = lm.iloc[sample(lm, 25)].copy()                     # key duplicates with a different balance
    dup["OUTSTANDING_BALANCE"] = (dup["OUTSTANDING_BALANCE"] * 1.1).round(2)
    for row in dup.itertuples(index=False):
        note("loan_monthly", "DUPLICATE_KEY", "LOAN_ID+SNAPSHOT_DATE", f"{row.LOAN_ID}|{row.SNAPSHOT_DATE}",
             None, None, "same loan and month appears twice with a different balance")
    t["loan_monthly"] = pd.concat([lm, dup], ignore_index=True)

    # ---------------- customer_monthly ----------------
    cmo = t["customer_monthly"]
    for i in sample(cmo, int(0.01 * len(cmo))):              # random missing balance (1%)
        note("customer_monthly", "MISSING_VALUE", "AVG_BALANCE",
             f"{cmo.at[i, 'CUSTOMER_ID']}|{cmo.at[i, 'SNAPSHOT_DATE']}", cmo.at[i, "AVG_BALANCE"], None,
             "balance missing (random gap in the extract)")
        cmo.at[i, "AVG_BALANCE"] = np.nan
    for i in sample(cmo, 30):                                # impossible negative turnover
        note("customer_monthly", "INVALID_VALUE", "CREDIT_TURNOVER",
             f"{cmo.at[i, 'CUSTOMER_ID']}|{cmo.at[i, 'SNAPSHOT_DATE']}", cmo.at[i, "CREDIT_TURNOVER"],
             -abs(cmo.at[i, "CREDIT_TURNOVER"]), "turnover cannot be negative (sign error)")
        cmo.at[i, "CREDIT_TURNOVER"] = -abs(cmo.at[i, "CREDIT_TURNOVER"])
    for i in sample(cmo, 10):                                # fat-finger outlier turnover (x100)
        note("customer_monthly", "OUTLIER", "CREDIT_TURNOVER",
             f"{cmo.at[i, 'CUSTOMER_ID']}|{cmo.at[i, 'SNAPSHOT_DATE']}", cmo.at[i, "CREDIT_TURNOVER"],
             cmo.at[i, "CREDIT_TURNOVER"] * 100, "turnover 100x too large (extra zeros)")
        cmo.at[i, "CREDIT_TURNOVER"] = cmo.at[i, "CREDIT_TURNOVER"] * 100
    for i in sample(cmo, 10):                                # impossible days overdrawn
        note("customer_monthly", "INVALID_VALUE", "DAYS_OVERDRAWN",
             f"{cmo.at[i, 'CUSTOMER_ID']}|{cmo.at[i, 'SNAPSHOT_DATE']}", cmo.at[i, "DAYS_OVERDRAWN"], 45,
             "more days overdrawn than days in a month")
        cmo.at[i, "DAYS_OVERDRAWN"] = 45
    dup = cmo.iloc[sample(cmo, int(0.003 * len(cmo)))].copy()   # exact duplicate rows (0.3%)
    for row in dup.itertuples(index=False):
        note("customer_monthly", "EXACT_DUPLICATE", "ALL", f"{row.CUSTOMER_ID}|{row.SNAPSHOT_DATE}", None, None,
             "the same row extracted twice")
    t["customer_monthly"] = pd.concat([cmo, dup], ignore_index=True)

    # ---------------- crb_monthly ----------------
    crb = t["crb_monthly"]
    scored = crb.index[crb["CRB_SCORE"].notna()].to_numpy()
    for i in rng.choice(scored, size=15, replace=False):     # out-of-range score
        note("crb_monthly", "INVALID_VALUE", "CRB_SCORE", f"{crb.at[i, 'CUSTOMER_ID']}|{crb.at[i, 'SNAPSHOT_DATE']}",
             crb.at[i, "CRB_SCORE"], 999, "score above the 900 maximum")
        crb.at[i, "CRB_SCORE"] = 999
    june = crb.index[crb["SNAPSHOT_DATE"] == "2024-06-30"].to_numpy()        # partly failed monthly feed
    drop = rng.choice(june, size=int(0.4 * len(june)), replace=False)
    note("crb_monthly", "ROWS_MISSING", "ALL", "2024-06-30", len(june), len(june) - len(drop),
         "bureau feed failed for 40% of customers in June 2024")
    t["crb_monthly"] = crb.drop(index=drop).reset_index(drop=True)

    return t, pd.DataFrame(log)