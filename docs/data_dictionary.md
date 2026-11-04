<!-- ==================================================================
     docs/data_dictionary.md — every synthetic table and column.
     WHAT: meaning, type, valid range/values, availability class,
           and the real NCBA source each table mirrors.
     WHY:  the single reference for data generation (Stage 2), EDA
           (Stage 3), validation (Stage 4) and features (Stage 5).
     RULE: if the generator changes a column, update this file in the
           SAME commit, so documentation never goes stale.
     LAST UPDATED: Stage 2 complete (Lessons 8–11).
     ================================================================== -->

# Data Dictionary — Synthetic CSME Early Warning Data

> All data is **synthetic** (fictitious): no real customers, RMs or emails.
> `python scripts/generate_data.py` writes CSV files to `data/synthetic/`.
> Snapshots are month-end **extraction ("as at") dates**, Jan 2023 – Dec 2025 (36 months).
> The extracts contain **deliberately planted data problems**: see `docs/planted_issues.md`.

## How to read this document

- **Grain** = what one row means. **PK** = primary key (unique row ID). **FK** = foreign key (link to another table).
- **Type**: text, integer (whole number), number (decimal), date (YYYY-MM-DD).
- **Class** = whether the model may use the column:

| Class | Meaning | Model input? |
|---|---|---|
| KEY | identifies or joins rows | No |
| STATIC | known at or before the snapshot, rarely changes | Yes |
| AS_OF | measured at the snapshot month or earlier | Yes (only same or earlier months) |
| OPERATIONAL | needed to ACT on alerts (who to email) | No |
| PROTECTED | sensitive personal attribute; used for fairness checks | Excluded by default |
| TARGET_SOURCE | future values used only to build the label | Never |
| TRUTH | hidden simulation variable or answer key | Never |

**How a class is decided** (first "yes" wins):
1. Only identifies or links rows? → KEY
2. About the future, or hidden/answer-key data? → TARGET_SOURCE or TRUTH
3. Only needed to act on an alert? → OPERATIONAL
4. A sensitive personal attribute? → PROTECTED
5. Otherwise known at or before the snapshot → STATIC (rarely changes) or AS_OF (changes monthly)

## Table overview

| # | Table (file in data/synthetic/) | Grain (one row =) | Primary key |
|---|---|---|---|
| 1 | relationship_managers | one RM | RM_ID |
| 2 | customers | one customer | CUSTOMER_ID |
| 3 | loans | one loan (terms at booking) | LOAN_ID |
| 4 | loan_monthly | one loan × month-end | LOAN_ID, SNAPSHOT_DATE |
| 5 | customer_monthly | one customer × month-end | CUSTOMER_ID, SNAPSHOT_DATE |
| 6 | crb_monthly | one customer × month-end | CUSTOMER_ID, SNAPSHOT_DATE |
| 7 | macro_monthly | one month-end | SNAPSHOT_DATE |
| 8 | sector_monthly | one sector × month-end | SECTOR, SNAPSHOT_DATE |
| 9 | _truth_customer_monthly | one customer × month-end | CUSTOMER_ID, SNAPSHOT_DATE |
| 10 | _truth_target_customer_month | one customer × month-end | CUSTOMER_ID, SNAPSHOT_DATE |
| 11 | _truth_planted_issues | one planted data problem | (none) |

How they connect: one RM → many customers; one customer → many loans;
one loan → many monthly rows; one customer → many monthly behaviour and CRB rows;
macro joins on SNAPSHOT_DATE; sector joins on SECTOR + SNAPSHOT_DATE.

---

## 1. relationship_managers — one row per RM
PK: `RM_ID`

| Column | Type | Valid values / range | Class | Meaning |
|---|---|---|---|---|
| RM_ID | text | RM001–RM040 | KEY | RM identifier |
| RM_NAME | text | fictitious names | OPERATIONAL | RM full name |
| RM_EMAIL | text | `...@example.com` | OPERATIONAL | Where alert emails go (reserved domain: can never reach a real inbox) |
| BRANCH | text | branch list | OPERATIONAL | RM's branch |
| REGION | text | Nairobi, Central, Coast, Rift Valley, Western, Nyanza, Eastern | OPERATIONAL | RM's region (every region has at least one RM) |

## 2. customers — one row per customer
PK: `CUSTOMER_ID` · FK: `RM_ID` → relationship_managers (RM is in the customer's region)

| Column | Type | Valid values / range | Class | Meaning |
|---|---|---|---|---|
| CUSTOMER_ID | text | C000001–C005000 | KEY | Customer identifier |
| RM_ID | text | must exist in relationship_managers | KEY | Assigned RM |
| SEGMENT | text | "250", "270" | STATIC | CSME business segment at onboarding (a code, NOT a number: read as text) |
| SECTOR | text | Trade, Agriculture, Transport, Manufacturing, Services, Construction, Hospitality | STATIC | Business sector |
| BUSINESS_TYPE | text | Sole proprietor, Partnership, Limited company | STATIC | Legal form |
| REGION | text | as RM regions | STATIC | Business location region |
| TOWN | text | town list (always inside REGION) | STATIC | Business town |
| AGE | integer | 21–75 | PROTECTED | Owner/main director age at Jan 2023 |
| GENDER | text | M, F | PROTECTED | Owner/main director gender |
| CUSTOMER_SINCE | date | 2005-01-01 to 2023-01-31 | STATIC | Relationship start date (all customers exist at the first snapshot) |
| BUSINESS_YEARS | integer | 0–40 | STATIC | Years the business has operated at Jan 2023 (≥ relationship years) |
| DECLARED_MONTHLY_INCOME | number (KES) | > 0 (right-skewed) | STATIC | Income declared at onboarding |

## 3. loans — one row per loan (terms at booking)
PK: `LOAN_ID` · FK: `CUSTOMER_ID` → customers · FK: `REFINANCED_FROM_LOAN_ID` → loans

Products are **instalment** (ASSET_FINANCE, MORTGAGE, UNSECURED_BL: fixed EMI, tenor, maturity)
or **revolving** (OVERDRAFT, CREDIT_CARD, MOBILE_LOAN: a limit; no tenor, EMI or maturity).

| Column | Type | Valid values / range | Class | Meaning |
|---|---|---|---|---|
| LOAN_ID | text | L0000001… | KEY | Loan/facility identifier |
| CUSTOMER_ID | text | must exist in customers | KEY | Borrower |
| PRODUCT | text | ASSET_FINANCE, MORTGAGE, UNSECURED_BL, OVERDRAFT, CREDIT_CARD, MOBILE_LOAN | STATIC | Product type |
| SECURED_FLAG | integer | 0, 1 | STATIC | 1 = secured (asset finance, mortgage) |
| BOOKING_DATE | date | 2015-01-01 to 2025-12-31 | STATIC | Date the loan was booked |
| LOAN_AMOUNT | number (KES) | ≥ 5,000 | STATIC | Amount disbursed (instalment) or LIMIT (revolving) |
| INTEREST_RATE | number (%) | 12–36 | STATIC | Annual interest rate |
| TENOR_MONTHS | integer | 12–240 (blank for revolving) | STATIC | Contractual term |
| EMI | number (KES) | > 0 instalment; 0 revolving | STATIC | Scheduled monthly instalment (annuity formula) |
| REPAYMENT_FREQUENCY | text | MONTHLY | STATIC | Repayment frequency |
| MATURITY_DATE | date | after BOOKING_DATE (blank for revolving) | STATIC | Contractual end date |
| REFINANCED_FROM_LOAN_ID | text | blank, or an existing LOAN_ID | STATIC | The old loan this one replaced (top-up/refinance, same month) |

## 4. loan_monthly — one row per loan per month-end
PK: `LOAN_ID, SNAPSHOT_DATE` · FK: `LOAN_ID` → loans

> A loan has a row for every month-end from booking until (and including) the month it closes
> or is written off. DPD follows a state machine: current → 1–29 → +30 each unpaid month →
> write-off possible from 180; restructures (at 60–150 DPD) reset DPD to 0.

| Column | Type | Valid values / range | Class | Meaning |
|---|---|---|---|---|
| LOAN_ID | text | must exist in loans | KEY | Loan |
| SNAPSHOT_DATE | date | month-ends 2023-01-31 to 2025-12-31 (not before booking) | KEY | Extraction ("as at") date |
| MOB | integer | ≥ 0, rises by 1 each month | AS_OF | Months on book at the snapshot |
| OUTSTANDING_BALANCE | number (KES) | ≥ 0 (0 when CLOSED) | AS_OF | Balance owed (scheduled balance + arrears) |
| LIMIT_UTILISATION | number | 0–1.3 (revolving only; blank for instalment) | AS_OF | Balance ÷ limit; > 1 = over the limit |
| DPD | integer | 0–360 | AS_OF | Days past due at the snapshot |
| ARREARS_AMOUNT | number (KES) | ≥ 0; > 0 exactly when DPD > 0 | AS_OF | Overdue amount |
| MISSED_INSTALMENT_FLAG | integer | 0, 1 | AS_OF | A genuine instalment miss this month |
| RESTRUCTURED_FLAG | integer | 0, 1 | AS_OF | Loan restructured this month (DPD reset to 0) |
| ACCOUNT_STATUS | text | ACTIVE, RESTRUCTURED, CLOSED, WRITTEN_OFF | AS_OF | Status at the snapshot |
| CLOSURE_REASON | text | blank, PAID_OFF, MATURED, REFINANCED, WRITTEN_OFF | AS_OF | Why the loan ended (only in its final month) |

## 5. customer_monthly — one row per customer per month-end (account behaviour and products)
PK: `CUSTOMER_ID, SNAPSHOT_DATE` · FK: `CUSTOMER_ID` → customers

| Column | Type | Valid values / range | Class | Meaning |
|---|---|---|---|---|
| CUSTOMER_ID | text | must exist in customers | KEY | Customer |
| SNAPSHOT_DATE | date | month-ends | KEY | Extraction date |
| SEGMENT_AT_SNAPSHOT | text | "250", "270", "260" (migrated out of CSME) | AS_OF | Segment this month |
| CREDIT_TURNOVER | number (KES) | ≥ 0 (seasonal: Dec peak, Jan dip) | AS_OF | Customer-initiated inflows in the month (CTO) |
| CREDIT_COUNT | integer | ≥ 0 | AS_OF | Number of inflow transactions |
| DEBIT_TURNOVER | number (KES) | ≥ 0 | AS_OF | Outflows in the month (DTO) |
| DEBIT_COUNT | integer | ≥ 0 | AS_OF | Number of outflow transactions |
| AVG_BALANCE | number (KES) | any (negative = overdrawn) | AS_OF | Average current-account balance in the month |
| MIN_BALANCE | number (KES) | ≤ AVG_BALANCE | AS_OF | Lowest balance in the month |
| DAYS_OVERDRAWN | integer | 0–31 | AS_OF | Days with a negative balance |
| UNPAID_COUNT | integer | ≥ 0 | AS_OF | Returned/unpaid items (debit orders, cheques) |
| UNPAID_AMOUNT | number (KES) | ≥ 0 | AS_OF | Value of unpaid items |
| CURRENT_ACCOUNTS | integer | 1–2 | AS_OF | Active current accounts (PPC) |
| SAVINGS_ACCOUNTS | integer | ≥ 0 | AS_OF | Savings accounts held (PPC) |
| TERM_DEPOSITS | integer | 0, 1 (broken when under stress) | AS_OF | Term deposits with a balance (PPC) |
| DEBIT_CARDS | integer | ≥ 0 | AS_OF | Debit cards held (PPC) |

## 6. crb_monthly — one row per customer per month-end (credit bureau)
PK: `CUSTOMER_ID, SNAPSHOT_DATE` · FK: `CUSTOMER_ID` → customers

| Column | Type | Valid values / range | Class | Meaning |
|---|---|---|---|---|
| CUSTOMER_ID | text | must exist in customers | KEY | Customer |
| SNAPSHOT_DATE | date | month-ends | KEY | Extraction date |
| CRB_SCORE | integer | 200–900 (blank = no bureau record, ~8% of customers) | AS_OF | Bureau score |
| ENQUIRIES_30D | integer | ≥ 0 | AS_OF | Credit enquiries in the last 30 days |
| ENQUIRIES_90D | integer | ≥ ENQUIRIES_30D | AS_OF | Credit enquiries in the last 90 days |
| CREDIT_APPLICATIONS | integer | ≥ 0 | AS_OF | Credit applications made |
| OTHER_LENDER_ACCOUNTS | integer | ≥ 0 | AS_OF | Open accounts at other lenders |
| OTHER_LENDER_CLOSED_ACCOUNTS | integer | ≥ 0 | AS_OF | Closed accounts at other lenders |
| OTHER_LENDER_NPL | integer | 0, 1 | AS_OF | Non-performing account at another lender this month |
| OTHER_LENDER_MONTHLY_COMMITMENT | number (KES) | ≥ 0 | AS_OF | Instalments owed to other lenders |
| OTHER_LENDER_PAST_DUE_AMOUNT | number (KES) | ≥ 0 | AS_OF | Overdue amount at other lenders |
| MAX_ARREARS_OTHER_12M | integer | 0–150 | AS_OF | Worst DPD at other lenders, last 12 months |
| MOBILE_LOANS_ACTIVE | integer | ≥ 0 | AS_OF | Active mobile/digital loans |
| MOBILE_LOANS_NPL | integer | ≤ MOBILE_LOANS_ACTIVE | AS_OF | Non-performing mobile/digital loans |
| TU_LISTED_FLAG | integer | 0, 1 | AS_OF | Negatively listed (TU "on") at the snapshot |

## 7. macro_monthly — one row per month-end
PK: `SNAPSHOT_DATE`

| Column | Type | Valid values / range | Class | Meaning |
|---|---|---|---|---|
| SNAPSHOT_DATE | date | month-ends | KEY | Month |
| INFLATION_RATE | number (%) | 2–12 | AS_OF | Year-on-year inflation proxy |
| CBK_RATE | number (%) | 6–14 | AS_OF | Central bank rate proxy (reacts ~2 months after stress) |
| UNEMPLOYMENT_PROXY | number (%) | 3–15 | AS_OF | Unemployment proxy |
| ECON_STRESS_INDEX | number | 0–1 | AS_OF | Economic stress (planted downturn peaking ~Sep 2024) |

## 8. sector_monthly — one row per sector per month-end
PK: `SECTOR, SNAPSHOT_DATE`

| Column | Type | Valid values / range | Class | Meaning |
|---|---|---|---|---|
| SECTOR | text | sector list | KEY | Sector |
| SNAPSHOT_DATE | date | month-ends | KEY | Month |
| SECTOR_STRESS_INDEX | number | 0–1 | AS_OF | Sector stress: drought (Agriculture, Sep 23–Mar 24), tourism (Hospitality, Mar–Jun 24), fuel (Transport, Jul–Dec 24), slowdown (Construction, Mar–Oct 25) |

## 9. _truth_customer_monthly — HIDDEN health
PK: `CUSTOMER_ID, SNAPSHOT_DATE`

| Column | Type | Valid values / range | Class | Meaning |
|---|---|---|---|---|
| CUSTOMER_ID | text | must exist in customers | KEY | Customer |
| SNAPSHOT_DATE | date | month-ends | KEY | Month |
| LATENT_HEALTH | number | −4 to +4 | TRUTH | Hidden financial health that drives behaviour |

## 10. _truth_target_customer_month — reference target from CLEAN data
PK: `CUSTOMER_ID, SNAPSHOT_DATE`

| Column | Type | Valid values / range | Class | Meaning |
|---|---|---|---|---|
| CUSTOMER_ID | text | must exist in customers | KEY | Customer |
| SNAPSHOT_DATE | date | month-ends | KEY | Snapshot |
| DPD_NOW | integer | 0–360 | AS_OF | Worst DPD across the customer's loans at the snapshot |
| WORST_DPD_NEXT_3M | number | 0–360 (blank if immature) | TARGET_SOURCE | Worst DPD in the next 3 months |
| TARGET_STATUS | text | LABELLED, EXCLUDED_NO_LOANS, EXCLUDED_NOT_CSME, EXCLUDED_DPD, IMMATURE, INDETERMINATE | TRUTH | Why the row has (or lacks) a label |
| TARGET_DPD30_90D | integer | 0, 1 (blank unless LABELLED) | TARGET_SOURCE | The label |

## 11. _truth_planted_issues — answer key for data cleaning
One row per planted problem: TABLE, ISSUE_TYPE, COLUMN, ROW_KEY, ORIGINAL_VALUE, PLANTED_VALUE, DESCRIPTION.
Class: TRUTH. Open it only AFTER your own EDA and cleaning (see `docs/planted_issues.md`).

> ⚠ `_truth_*` files must NEVER be model inputs. They exist only to check our work.

---

## Target and outcome rules (`src/ews/data/target.py`)

**Target `TARGET_DPD30_90D`**, per (CUSTOMER_ID, SNAPSHOT_DATE), checked in this order:

| TARGET_STATUS | Rule | Label |
|---|---|---|
| EXCLUDED_NO_LOANS | no ACTIVE or RESTRUCTURED loan at the snapshot | none |
| EXCLUDED_NOT_CSME | SEGMENT_AT_SNAPSHOT not in 250/270 | none |
| EXCLUDED_DPD | worst DPD at the snapshot > 5 | none |
| IMMATURE | fewer than 3 future months in the data (Oct–Dec 2025) | none |
| INDETERMINATE | customer leaves 250/270 within the next 3 months | none (counted) |
| LABELLED | otherwise | 1 if in the next 3 months worst DPD ≥ 30, or any restructure or write-off; else 0 |

Loans that close in the window (paid off, matured, refinanced) stop having rows; because closures
are recorded, "no future rows" means "no arrears" (good). Refinancing is followed at customer level.

## Features derivable from these tables (built in Stage 5)

| Family | Features |
|---|---|
| Delinquency | MAX_DPD_1M/3M/6M/12M, AVG_DPD_3M, DPD_TREND_6M, MONTHS_SINCE_LAST_DPD |
| Payment stress | UNPAID_COUNT_3M/12M, UNPAID_AMOUNT_RATIO, FIRST_INSTALMENT_DEFAULT_FLAG, MISSED_EMI_COUNT_6M |
| Affordability | LOAN_TO_INCOME, INSTALMENT_TO_INCOME (active loans), TOTAL_COMMITMENTS_TO_INCOME, NO_OF_ACTIVE_LOANS |
| Revolving use | OD/card/mobile UTILISATION now, UTILISATION_TREND_3M/6M, MONTHS_ABOVE_90PCT_UTIL |
| Cash flow | CTO/DTO quarterly values and slopes, % change vs 6-month average, turnover volatility, DTO ÷ CTO |
| Balances | AVG_BALANCE_3M/12M, BALANCE_VOLATILITY, BALANCE_TREND, NEG_MONTHS_6M, DAYS_OVERDRAWN_3M |
| Bureau | CRB_SCORE, CRB_SCORE_CHANGE, NO_CRB_HIT flag, ENQUIRIES_6M, OTHER_LENDER_NPL, TU_ON_OFF_FREQUENCY |
| Products | PPC, HAS_* product flags, TERM_DEPOSIT_BROKEN flag |
| History | MIN_MOB, HISTORY_MONTHS_AVAILABLE, REFINANCED_EVER, RESTRUCTURED_EVER, MONTHS_SINCE_RESTRUCTURE |
| Context | macro and sector stress, month of year (seasonality) |

## Known simplifications (for the model card)
- A loan reaching contractual closure while in arrears is treated as settled at closure.
- All customers exist at Jan 2023; no new-to-bank customers join later.
- One script generates every table; real tables come from separate systems.

## Real-source mapping (for the rebuild on real CSME data)

<!-- On real data: write one SQL extract per synthetic table that outputs EXACTLY
     these columns. Everything downstream then runs unchanged. -->

| Synthetic table | Real NCBA source | Notes |
|---|---|---|
| relationship_managers | RM / portfolio allocation list | Real RM emails only inside the bank |
| customers | KE_Customer_Master; customer static details | Filter BUSINESS_SEGMENT IN ('250','270') |
| loans | KE_Accounts_List / KE_Accounts_Master (PRODUCT_LINE = 'LENDING'); EMI file | Map CATEGORY codes to PRODUCT |
| loan_monthly | STG_AA_ARREARS, STG_AA_BILL_ARREARS; accounts master balances and status | LEFT JOIN arrears: no arrears row ≠ missing customer |
| customer_monthly | KE_ACCOUNT_TRANSACTIONS (DTO, CTO, unpaid codes); STG_AVERAGE_BALANCE; deposit and card PPC queries; monthly segment | Same transaction-code exclusions as the notebook |
| crb_monthly | LEND_FOR_ALL_CRB (latest LOAD_DATE ≤ snapshot); TU on/off | SCORE, ENQUIRIES30/90DAYS, SCHEDULEDPAYMENTAMT, PASTDUEAMOUNT, NONPERFORMING, MOBILE_* |
| macro_monthly | Public data (KNBS, CBK) | Same for every customer in a month |
| sector_monthly | Internal sector NPL trends or external data | Optional on real data |
| _truth_* | **None**: synthetic only | Don't exist in reality |