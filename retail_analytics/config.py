"""Central configuration: paths and business parameters used across the pipeline."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "retail.db"

SQL_DIR = ROOT / "sql"
QUERY_DIR = SQL_DIR / "queries"

REPORTS_DIR = ROOT / "reports"
TABLES_DIR = REPORTS_DIR / "tables"
FIGURES_DIR = REPORTS_DIR / "figures"
POWERBI_DIR = ROOT / "powerbi" / "data"

# --- Data generation -------------------------------------------------------
SEED = 42
START_DATE = "2024-01-01"
END_DATE = "2025-12-31"
BASE_DAILY_BASKETS = 70  # per average-sized store on an average day

# --- Market basket analysis ------------------------------------------------
MIN_SUPPORT = 0.005      # pair appears in at least 0.5% of baskets
MIN_CONFIDENCE = 0.10
MIN_LIFT = 1.20

# --- Forecasting -----------------------------------------------------------
HOLDOUT_DAYS = 56        # last 8 weeks are held out for evaluation
FORECAST_HORIZON = 7     # days ahead; every lag feature is at least this old

# --- Inventory -------------------------------------------------------------
SERVICE_LEVEL_Z = 1.645  # 95% cycle service level
REVIEW_PERIOD_DAYS = 7   # stores place replenishment orders weekly


def ensure_dirs() -> None:
    for d in (RAW_DIR, TABLES_DIR, FIGURES_DIR, POWERBI_DIR):
        d.mkdir(parents=True, exist_ok=True)
