<!-- docs/planted_issues.md — what data problems the generator plants, and why.
     The exact rows are in data/synthetic/_truth_planted_issues.csv (the "answer key").
     Don't open the answer key until you've done your own EDA and cleaning (Stages 3–4). -->

# Planted Data-Quality Issues

| # | Table | Issue type | What was done | Approx. count | Real-world cause it mimics |
|---|---|---|---|---|---|
| 1 | customers | MISSING_VALUE | DECLARED_MONTHLY_INCOME blanked | 2% | field not captured at onboarding |
| 2 | customers | MISSING_VALUE | TOWN blanked | 1% | optional field skipped |
| 3 | customers | INVALID_VALUE | AGE set to 150 or −3 | 10 rows | typing error |
| 4 | customers | INCONSISTENT_CATEGORY | REGION as "NAIROBI ", "nairobi", "Nrb", "COAST", … | ~2% | free-text capture, trailing spaces |
| 5 | customers | INCONSISTENT_CATEGORY | SECTOR as "trade", "Agri", "TRANSPORT " | ~1% | different systems' codes |
| 6 | customers | INCONSISTENT_CATEGORY | GENDER as "Male", "F " | 2% | mixed coding standards |
| 7 | customers | UNEXPECTED_CATEGORY | SEGMENT "999" | 5 rows | code not in the reference list |
| 8 | customers | MIXED_DATE_FORMAT | CUSTOMER_SINCE as DD/MM/YYYY | 3% | export from another system / Excel |
| 9 | loans | OUTLIER | LOAN_AMOUNT 9,999,999,999 | 3 rows | fat-finger error |
| 10 | loans | UNEXPECTED_CATEGORY | PRODUCT "LEASE" | 5 rows | new product not yet mapped |
| 11 | loans | ORPHAN_RECORD | loans for customers that don't exist | 12 rows | extracts filtered differently |
| 12 | loan_monthly | INVALID_VALUE | DPD −5 | 10 rows | calculation bug upstream |
| 13 | loan_monthly | DUPLICATE_KEY | same loan + month twice, different balance | 25 rows | duplicate extract run |
| 14 | customer_monthly | MISSING_VALUE | AVG_BALANCE blanked | 1% | random extract gap |
| 15 | customer_monthly | INVALID_VALUE | CREDIT_TURNOVER negative | 30 rows | sign error |
| 16 | customer_monthly | OUTLIER | CREDIT_TURNOVER × 100 | 10 rows | extra zeros typed |
| 17 | customer_monthly | INVALID_VALUE | DAYS_OVERDRAWN 45 | 10 rows | more days than a month has |
| 18 | customer_monthly | EXACT_DUPLICATE | identical rows repeated | 0.3% | same row extracted twice |
| 19 | crb_monthly | INVALID_VALUE | CRB_SCORE 999 | 15 rows | score above the 900 maximum |
| 20 | crb_monthly | ROWS_MISSING | 40% of June 2024 rows missing | 1 month | bureau feed failure |

## Not errors (real structure that looks like missing data)
- `LIMIT_UTILISATION` blank for instalment loans: utilisation only applies to limits.
- `TENOR_MONTHS`, `MATURITY_DATE` blank and `EMI` = 0 for revolving products.
- `CRB_SCORE` blank for ~8% of customers: no bureau record (thin file). Test whether this is a risk signal; don't assume it is.
- Customers with no loan rows in some months: all their loans have closed.

## How to use this
1. In Stage 3 (EDA), find as many issues as you can **without** looking at the answer key.
2. In Stage 4, write validation rules and cleaning code.
3. Then compare what you found with `_truth_planted_issues.csv`.