"""ews.config — loads the project settings from config/config.yaml.

WHAT:  load_config()  -> reads config.yaml into a Python dictionary
       resolve_path() -> turns a path from the config into a full path
       PROJECT_ROOT   -> the credit-ews/ folder, found automatically
WHY:   No hardcoded numbers or paths anywhere else in the code, and paths
       work no matter which folder a script or notebook is run from.

USAGE:
    from ews.config import load_config, resolve_path
    cfg = load_config()
    cfg["target"]["dpd_threshold"]                 # -> 30
    resolve_path(cfg["paths"]["synthetic_data"])   # -> C:/.../credit-ews/data/synthetic
"""

from pathlib import Path   # Path: an object-oriented, cross-platform way to handle file paths

import yaml                # pyyaml: reads YAML files

# --- Locate the project folder -------------------------------------------
# __file__ is the full path of THIS file: .../credit-ews/src/ews/config.py
# .resolve() makes it absolute; .parents[0] = ews/, [1] = src/, [2] = credit-ews/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Default location of the settings file, built from PROJECT_ROOT (never a hardcoded C:\ path)
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"

# Sections every config must contain; if one is missing, we fail early and clearly
REQUIRED_SECTIONS = ["project", "paths", "synthetic_data", "target", "features", "splits", "monitoring"]


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> dict:
    """Read the YAML config file and return it as a dictionary.

    Args:
        path: location of the YAML file (defaults to config/config.yaml).

    Returns:
        dict of settings, e.g. cfg["target"]["horizon_days"] -> 90

    Raises:
        FileNotFoundError: the file doesn't exist.
        ValueError: the file is empty or a required section is missing.
    """
    path = Path(path)                                  # accept a string or a Path

    if not path.exists():                              # clear message instead of a cryptic crash
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as f:        # "with" closes the file automatically
        cfg = yaml.safe_load(f)                        # safe_load: reads data only, never runs code

    if not isinstance(cfg, dict):                      # an empty file gives None, not a dictionary
        raise ValueError(f"Config file is empty or not a valid mapping: {path}")

    missing = [s for s in REQUIRED_SECTIONS if s not in cfg]   # list any absent sections
    if missing:
        raise ValueError(f"Config is missing required section(s): {missing}")

    return cfg


def resolve_path(relative_path: str) -> Path:
    """Turn a path from the config (relative to the project folder) into a full path.

    Example:
        resolve_path("data/synthetic") -> C:/Users/.../credit-ews/data/synthetic
    """
    return PROJECT_ROOT / relative_path               # "/" joins paths with Path objects