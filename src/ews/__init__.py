"""ews — the Credit Early Warning System package (all reusable project code).

WHAT:  The root of our own Python package. Its presence makes src/ews/ a
       package, so code can do `import ews` or `from ews.config import ...`.
WHY:   Logic is written ONCE here and imported everywhere (notebooks, scripts,
       tests, the FastAPI app), so training and scoring can never drift apart.
LATER: Sub-packages are added in their stages:
           ews/data/        Stage 2  synthetic data generation
           ews/features/    Stage 5  feature engineering
           ews/models/      Stage 6  model training
           ews/evaluation/  Stage 7  metrics and validation
           ews/monitoring/  Stage 11 PSI, data quality, alerts
           ews/pipelines/   Stage 9  end-to-end train and score runs
"""

# Package version: bump it when the code changes meaningfully.
# It will be stored next to every saved model and score, for traceability.
__version__ = "0.1.0"