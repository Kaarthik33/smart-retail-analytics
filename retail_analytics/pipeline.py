"""Run the whole project end to end:  python -m retail_analytics.pipeline"""

from __future__ import annotations

import argparse
import time

from . import (basket_analysis, database, export_powerbi, forecasting, generate_data, inventory,
               promotions, report, sales_analysis)

STEPS = [
    ("Generating data", generate_data.run),
    ("Building SQL database", database.build_database),
    ("Sales analysis (SQL)", sales_analysis.run),
    ("Market basket analysis", basket_analysis.run),
    ("Demand forecasting", forecasting.run),
    ("Inventory planning", inventory.run),
    ("Promotion analysis", promotions.run),
    ("Power BI export", export_powerbi.run),
    ("Insights report", report.run),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-generate", action="store_true",
                        help="reuse the existing data/raw CSV files and database")
    args = parser.parse_args()

    start = time.time()
    steps = STEPS[2:] if args.skip_generate else STEPS
    for i, (label, step) in enumerate(steps, 1):
        print(f"[{i}/{len(steps)}] {label}")
        step()
    print(f"Done in {time.time() - start:.0f}s")


if __name__ == "__main__":
    main()
