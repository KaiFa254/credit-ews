"""ews.data.customers — generate relationship managers (RMs) and CSME customers.

WHAT:  make_relationship_managers() -> table 1 of the data dictionary
       make_customers()             -> table 2 of the data dictionary
WHY:   These are the "static" tables every other table links to:
       loans belong to customers, customers belong to RMs.
HOW:   Every random choice uses ONE random generator (rng) passed in from the
       script, so the same seed always produces exactly the same data.

All names, emails and customers are FICTITIOUS. Emails use example.com,
a domain reserved for documentation that can never reach a real inbox.
"""

import numpy as np
import pandas as pd

# =============================================================================
# Reference data: the "menus" we draw from, with realistic weights.
# Weights are ASSUMPTIONS for a plausible CSME book, not NCBA figures.
# Each set of weights must add up to 1.0 (100%).
# =============================================================================

# Region -> share of customers. Nairobi dominates SME banking in Kenya.
REGIONS = {
    "Nairobi": 0.45, "Central": 0.13, "Coast": 0.12, "Rift Valley": 0.14,
    "Western": 0.05, "Nyanza": 0.06, "Eastern": 0.05,
}

# Region -> towns in that region (a customer's town must match its region)
TOWNS = {
    "Nairobi": ["Nairobi CBD", "Westlands", "Industrial Area", "Eastleigh", "Karen"],
    "Central": ["Thika", "Nyeri", "Murang'a", "Kiambu"],
    "Coast": ["Mombasa", "Malindi", "Kilifi"],
    "Rift Valley": ["Nakuru", "Eldoret", "Naivasha", "Kericho", "Ol Kalou"],
    "Western": ["Kakamega", "Bungoma"],
    "Nyanza": ["Kisumu", "Kisii"],
    "Eastern": ["Machakos", "Meru", "Embu"],
}

# Region -> branches (RMs sit in a branch)
BRANCHES = {
    "Nairobi": ["Wabera Street", "Westlands", "Industrial Area", "Yaya Centre"],
    "Central": ["Thika", "Nyeri"],
    "Coast": ["Mombasa", "Malindi"],
    "Rift Valley": ["Nakuru", "Eldoret"],
    "Western": ["Kakamega"],
    "Nyanza": ["Kisumu"],
    "Eastern": ["Machakos", "Meru"],
}

# Sector -> share of customers, and an income multiplier (some sectors are larger businesses)
SECTORS = {
    #  name            share  income multiplier
    "Trade":          (0.32, 1.00),
    "Services":       (0.20, 0.90),
    "Agriculture":    (0.12, 0.85),
    "Transport":      (0.12, 1.10),
    "Manufacturing":  (0.08, 1.60),
    "Construction":   (0.09, 1.30),
    "Hospitality":    (0.07, 0.95),
}

BUSINESS_TYPES = {"Sole proprietor": 0.55, "Partnership": 0.15, "Limited company": 0.30}

# Segment -> share and median declared monthly income (KES).
# Assumption: segment "270" holds larger businesses than "250".
SEGMENTS = {"250": (0.60, 300_000), "270": (0.40, 900_000)}

# Fictitious name lists for RMs
FIRST_NAMES = ["Wanjiru", "Otieno", "Achieng", "Kamau", "Njeri", "Mwangi", "Akinyi", "Kiprono",
               "Wambui", "Ochieng", "Nyambura", "Mutua", "Chebet", "Kariuki", "Atieno", "Kibet",
               "Muthoni", "Omondi", "Jeptoo", "Gitau"]
LAST_NAMES = ["Kariuki", "Odhiambo", "Wekesa", "Njoroge", "Mutiso", "Cheruiyot", "Owino", "Macharia",
              "Barasa", "Kimani", "Onyango", "Ndungu", "Kosgei", "Mbugua", "Wafula", "Korir"]


def _pick(rng: np.random.Generator, options: dict, size: int) -> np.ndarray:
    """Draw `size` items from a {option: weight} dictionary, respecting the weights."""
    names = list(options.keys())
    weights = np.array(list(options.values()), dtype=float)
    return rng.choice(names, size=size, p=weights / weights.sum())   # p = probability of each option


def make_relationship_managers(rng: np.random.Generator, n_rms: int) -> pd.DataFrame:
    """Create the relationship_managers table (one row per RM).

    Every region gets at least one RM; the rest are spread by region size,
    so Nairobi has the most RMs, as it has the most customers.
    """
    regions = list(REGIONS.keys())
    # 1) one RM per region guaranteed, 2) remaining RMs drawn by region weight
    extra = _pick(rng, REGIONS, n_rms - len(regions))
    rm_regions = np.concatenate([regions, extra])

    rows, used_emails = [], set()
    for i, region in enumerate(rm_regions, start=1):
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        email = f"{first}.{last}".lower().replace("'", "")
        k = 2
        while email in used_emails:                    # two RMs with the same name -> add a number
            email = f"{first}.{last}{k}".lower().replace("'", "")
            k += 1
        used_emails.add(email)
        rows.append({
            "RM_ID": f"RM{i:03d}",                     # RM001, RM002, ... (:03d = pad to 3 digits)
            "RM_NAME": f"{first} {last}",
            "RM_EMAIL": f"{email}@example.com",        # reserved domain: can never reach a real inbox
            "BRANCH": rng.choice(BRANCHES[region]),
            "REGION": region,
        })
    return pd.DataFrame(rows)


def make_customers(rng: np.random.Generator, n_customers: int,
                   rms: pd.DataFrame, reference_date: str) -> pd.DataFrame:
    """Create the customers table (one row per customer).

    Args:
        rng:            the shared random generator (from the seed)
        n_customers:    how many customers to create
        rms:            the relationship_managers table (customers are assigned to an RM in their region)
        reference_date: the "as at" date for age and business years (the first snapshot, e.g. 2023-01-31)
    """
    n = n_customers
    ref = pd.Timestamp(reference_date)

    # --- IDs: C000001, C000002, ... (text, so leading zeros are kept) ---
    customer_id = [f"C{i:06d}" for i in range(1, n + 1)]

    # --- Categories drawn with realistic weights ---
    region = _pick(rng, REGIONS, n)
    town = np.array([rng.choice(TOWNS[r]) for r in region])          # town always matches region
    sector = _pick(rng, {s: w for s, (w, _) in SECTORS.items()}, n)
    business_type = _pick(rng, BUSINESS_TYPES, n)
    segment = _pick(rng, {s: w for s, (w, _) in SEGMENTS.items()}, n)
    gender = _pick(rng, {"M": 0.62, "F": 0.38}, n)

    # --- RM assignment: a random RM from the customer's own region ---
    rm_by_region = rms.groupby("REGION")["RM_ID"].apply(list).to_dict()
    rm_id = np.array([rng.choice(rm_by_region[r]) for r in region])

    # --- AGE: bell-shaped around 44, clipped to the allowed 21–75 ---
    # Normal distribution: most owners are middle-aged, few are very young or very old.
    age = np.clip(np.round(rng.normal(loc=44, scale=10, size=n)), 21, 75).astype(int)

    # --- CUSTOMER_SINCE: relationship start date, between 2005-01-01 and 2023-01-31 ---
    start, end = pd.Timestamp("2005-01-01"), ref
    days = rng.integers(0, (end - start).days + 1, size=n)            # random number of days after start
    customer_since = start + pd.to_timedelta(days, unit="D")

    # --- BUSINESS_YEARS: the business is at least as old as the bank relationship ---
    relationship_years = ((ref - customer_since).days / 365.25).astype(int)
    business_years = np.clip(relationship_years + rng.integers(0, 11, size=n), 0, 40)

    # --- DECLARED_MONTHLY_INCOME: right-skewed (log-normal) ---
    # Most businesses earn a moderate amount; a few earn far more. Log-normal captures
    # that long right tail, which is why money is almost never "normal" (bell-shaped).
    median_income = np.array([SEGMENTS[s][1] for s in segment])
    sector_mult = np.array([SECTORS[s][1] for s in sector])
    income = median_income * sector_mult * rng.lognormal(mean=0.0, sigma=0.7, size=n)
    income = (np.round(income / 1_000) * 1_000).astype(int)          # round to the nearest KES 1,000

    return pd.DataFrame({
        "CUSTOMER_ID": customer_id,
        "RM_ID": rm_id,
        "SEGMENT": segment,
        "SECTOR": sector,
        "BUSINESS_TYPE": business_type,
        "REGION": region,
        "TOWN": town,
        "AGE": age,
        "GENDER": gender,
        "CUSTOMER_SINCE": customer_since.strftime("%Y-%m-%d"),      # dates written as YYYY-MM-DD text
        "BUSINESS_YEARS": business_years,
        "DECLARED_MONTHLY_INCOME": income,
    })