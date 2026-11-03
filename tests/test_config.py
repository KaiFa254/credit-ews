"""tests/test_config.py — automated checks on the settings and the config loader.

WHAT:  Six tests that fail loudly if the agreed problem definition or the
       config loader ever changes by accident.
WHY:   A silent change to the target or the split dates produces a model that
       trains fine but answers a DIFFERENT question. Tests catch that in seconds.
USAGE: From the project folder:   pytest          (expect: 6 passed)
       Verbose, one line per test: pytest -v
"""

from datetime import date      # to compare split dates as real dates, not text

import pytest                  # the testing framework

from ews.config import PROJECT_ROOT, load_config, resolve_path


# --- 1. The config file loads at all ------------------------------------------
def test_config_loads():
    cfg = load_config()                                 # Act: read the real config
    assert cfg["project"]["name"] == "credit-ews"       # Assert: it's OUR project's config


# --- 2. The agreed target has not changed ------------------------------------
def test_target_definition_is_dpd30_90d():
    t = load_config()["target"]
    assert t["name"] == "TARGET_DPD30_90D"
    assert t["dpd_threshold"] == 30          # bad = reaches 30+ DPD ...
    assert t["horizon_days"] == 90           # ... within 90 days
    assert t["horizon_months"] == 3          # 90 days ~ 3 monthly snapshots
    assert t["grain"] == "customer_month"    # one row per customer per month-end


# --- 3. The population starts "performing" ------------------------------------
def test_population_starts_performing():
    t = load_config()["target"]
    # If customers could start at, say, 25 DPD, reaching 30 would be almost certain:
    # the model would look brilliant by predicting the obvious.
    assert t["max_dpd_at_snapshot"] < t["dpd_threshold"]


# --- 4. Train -> validation -> test are in time order, never overlapping -------
def test_splits_are_chronological():
    s = load_config()["splits"]
    first = date.fromisoformat(s["first_usable_snapshot"])   # "2023-12-31" -> a real date
    train_end = date.fromisoformat(s["train_end"])
    val_end = date.fromisoformat(s["validation_end"])
    test_end = date.fromisoformat(s["test_end"])
    assert first < train_end < val_end < test_end           # strict time order = no overlap


# --- 5. A broken config gives a CLEAR error (fail fast, fail clearly) ----------
def test_missing_section_gives_clear_error(tmp_path):
    # Arrange: write a deliberately broken config into a temporary folder.
    # tmp_path is a fresh, empty folder that pytest creates for this test only.
    broken = tmp_path / "config.yaml"
    broken.write_text("project:\n  name: credit-ews\n", encoding="utf-8")   # most sections missing

    # Act + Assert: loading it MUST raise ValueError, and the message must name a missing section
    with pytest.raises(ValueError, match="missing required section"):
        load_config(broken)


# --- 6. Paths from the config stay inside the project --------------------------
def test_resolve_path_points_inside_project():
    cfg = load_config()
    p = resolve_path(cfg["paths"]["synthetic_data"])
    assert p.is_absolute()                               # a full path, usable from anywhere
    assert PROJECT_ROOT in p.parents                     # and inside credit-ews/