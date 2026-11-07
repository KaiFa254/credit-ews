<!-- ==================================================================
     README.md — the project's front page (GitHub shows it automatically).
     Lines like this one are COMMENTS: visible in VS Code, hidden on GitHub.
     Update the Progress list at the end of every lesson.
     ================================================================== -->

# Credit Early Warning System (EWS)

<!-- One sentence: WHAT the model predicts. Reviewers should get it in 10 seconds. -->
Predicts whether a performing retail borrower will reach **≥ 30 days past due
(DPD) within the next 90 days**, using a fully synthetic credit portfolio.

<!-- Honesty disclaimer: synthetic results never prove real-world performance. -->
> All data is synthetic. Results do not establish real-world model performance.

## Target definition: `TARGET_DPD30_90D`

<!-- Spell out the target precisely. A vague target is the #1 cause of leakage and confusion. -->
| Item | Definition |
|---|---|
| Bad (1) | Account reaches **DPD ≥ 30** at any point in the **next 90 days** |
| Good (0) | Account stays below 30 DPD for the full 90 days |
| Population | Accounts **current or near-current (DPD ≤ 5)** at the month-end snapshot |
| Excluded | DPD ≥ 30 already (already bad); DPD 6–29 (reported separately) |
| Unlabelled | The last 3 months of data, which don't yet have a full 90-day outcome |

<!-- WHY this target: it ties the model to accounting and regulatory meaning. -->
**Why 30+ DPD in 90 days:**
- It matches the IFRS 9 30-DPD trigger for Stage 2 and the CBK *Watch* category.
- It gives collections teams three instalment cycles to act.
- It filters out technical arrears that cure by themselves.

This is a *delinquency* target, not default (default means 90+ DPD).

## Progress
<!-- [x] = done, [ ] = to do. Tick one box per lesson. -->
- [x] Lesson 1 — Project folder, environment, Git, target decision
- [X] Lesson 2 — Dependencies
- [x] Lesson 3 — Folder structure and config.yaml (grain: customer × month)
- [x] Lesson 4 — ews package, config loader, verification script, first tests (6 passing)
- [x] Stage 2 — Synthetic data: RMs, customers, loans, monthly behaviour, CRB, macro, sector,
      hidden health, DPD paths, target, planted data issues (56 tests passing; bad rate ≈ 5.8%)
- [ ] Stage 3: Data understanding & EDA (in progress: type-safe loader done)