"""scripts/verify_environment.py — is this machine ready to run the project?

WHAT:  Checks 5 things and prints [PASS] / [FAIL] / [WARN] for each:
       1. Python version and isolated environment
       2. every required package imports
       3. the project folder structure exists
       4. our own package (ews) imports and config.yaml loads
       5. a tiny model can be trained (smoke test)
WHY:   Setup problems caught now are 1-minute fixes; caught in Stage 6 they
       look like mysterious model errors.
USAGE: From the project folder:   python scripts/verify_environment.py
       Exit code 0 = all good, 1 = something failed (useful for automation later).
"""

import importlib          # import a library by its name as text, e.g. "pandas"
import os                 # read environment variables (to detect conda)
import sys                # Python version, interpreter location, exit codes
from pathlib import Path  # cross-platform file paths

# The project folder = one level above this script (scripts/ -> credit-ews/)
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# (name used in "import", name used in "pip install", required?)
# required=False -> a missing package gives a WARN, not a FAIL
PACKAGES = [
    ("numpy", "numpy", True),
    ("pandas", "pandas", True),
    ("yaml", "pyyaml", True),          # imported as "yaml", installed as "pyyaml"
    ("matplotlib", "matplotlib", True),
    ("seaborn", "seaborn", True),
    ("sklearn", "scikit-learn", True), # imported as "sklearn", installed as "scikit-learn"
    ("xgboost", "xgboost", True),
    ("lightgbm", "lightgbm", False),
    ("optbinning", "optbinning", False),
    ("shap", "shap", True),
    ("joblib", "joblib", True),
    ("pandera", "pandera", True),
    ("sqlalchemy", "sqlalchemy", True),
    ("fastapi", "fastapi", False),
    ("pytest", "pytest", True),
]

# Folders created in Lessons 3 and 4
REQUIRED_DIRS = [
    "config", "data/raw", "data/synthetic", "data/processed", "notebooks",
    "src/ews", "scripts", "tests", "artifacts/models", "artifacts/reports",
    "sql", "powerbi", "docs",
]

failures = 0  # counts [FAIL] lines; decides the exit code at the end


def report(ok: bool, label: str, detail: str = "", required: bool = True) -> None:
    """Print one result line and count failures."""
    global failures                       # we update the counter defined above
    if ok:
        tag = "PASS"
    elif required:
        tag = "FAIL"
        failures += 1
    else:
        tag = "WARN"                      # optional item missing: noted, not fatal
    print(f"  [{tag}] {label}" + (f" — {detail}" if detail else ""))


# --- 1. Python interpreter ---------------------------------------------------------
print("\n1. Python interpreter")
v = sys.version_info                                      # e.g. (3, 12, 16, ...)
report(v[:2] == (3, 12), f"Python {v.major}.{v.minor}.{v.micro}",
       "" if v[:2] == (3, 12) else "expected 3.12: activate credit-ews")

conda_env = os.environ.get("CONDA_DEFAULT_ENV")           # name of the active conda env, if any
in_conda = conda_env not in (None, "base")                # base doesn't count as isolated
in_venv = sys.prefix != sys.base_prefix                   # True inside a Python venv
report(in_conda or in_venv, "Isolated environment",
       f"conda env '{conda_env}'" if in_conda else
       (sys.prefix if in_venv else "run: conda activate credit-ews"))
print(f"         interpreter: {sys.executable}")          # where Python is running from

# --- 2. Packages ---------------------------------------------------------------------
print("\n2. Packages")
for import_name, pip_name, required in PACKAGES:
    try:
        module = importlib.import_module(import_name)      # try to import it
        version = getattr(module, "__version__", "?")      # most libraries expose __version__
        report(True, f"{pip_name:<14} {version}")
    except Exception as e:                                 # any import problem -> show the fix
        report(False, pip_name, f"pip install {pip_name}  ({type(e).__name__})", required)

# --- 3. Project folders -----------------------------------------------------------
print("\n3. Project folders")
for d in REQUIRED_DIRS:
    report((PROJECT_ROOT / d).is_dir(), d)                 # is_dir(): exists AND is a folder

# --- 4. Our package and config ----------------------------------------------------
print("\n4. Our package (ews) and config")
try:
    import ews                                             # works only after: pip install -e .
    from ews.config import load_config

    report(True, f"ews package imports (version {ews.__version__})")
    cfg = load_config()
    t = cfg["target"]
    report(True, "config/config.yaml loads",
           f"{t['name']}: DPD >= {t['dpd_threshold']} within {t['horizon_days']} days")
except Exception as e:
    report(False, "ews package / config", f"{type(e).__name__}: {e}")

# --- 5. Smoke test: can we actually train a model? ---------------------------
print("\n5. Smoke test (tiny model on random data)")
try:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score

    rng = np.random.default_rng(42)                        # seeded -> same numbers every run
    X = rng.normal(size=(1000, 3))                         # 1,000 fake rows, 3 fake features
    y = (X[:, 0] + rng.normal(scale=0.5, size=1000) > 0).astype(int)   # target driven by feature 0
    model = LogisticRegression().fit(X, y)                 # train
    auc = roc_auc_score(y, model.predict_proba(X)[:, 1])   # how well it ranks
    report(auc > 0.8, "scikit-learn trains and scores", f"AUC = {auc:.3f} (expected > 0.8)")
except Exception as e:
    report(False, "smoke test", f"{type(e).__name__}: {e}")

# --- Summary --------------------------------------------------------------------
print("\n" + "=" * 55)
if failures:
    print(f"  {failures} check(s) FAILED: fix them before continuing.")
    sys.exit(1)                                            # non-zero exit = failure (for automation)
print("  ENVIRONMENT READY")