"""Export a star schema for Power BI (CSV files in powerbi/data/).

    dim_date, dim_product, dim_store          dimensions
    fact_sales                                units, revenue, cost per store x product x day
    fact_forecast                             hold-out forecasts vs. actuals + next 7 days
    fact_inventory_plan                       reorder recommendations
    fact_promotions                           uplift per promotion
    basket_rules                              association rules
"""

from __future__ import annotations

import pandas as pd

from . import config, database
from .forecasting import promo_calendar
from .generate_data import holiday_factor


def run() -> None:
    config.ensure_dirs()
    out = config.POWERBI_DIR
    with database.connect() as con:
        sales = database.daily_sales(con)
        products = pd.read_sql_query("SELECT * FROM products", con)
        stores = pd.read_sql_query("SELECT * FROM stores", con)
        promotions = pd.read_sql_query("SELECT * FROM promotions", con,
                                       parse_dates=["start_date", "end_date"])
        baskets = pd.read_sql_query(
            "SELECT transaction_date AS date, store_id, COUNT(*) AS baskets "
            "FROM transactions GROUP BY transaction_date, store_id", con)

    future = pd.read_csv(config.TABLES_DIR / "forecast_next_7_days.csv", parse_dates=["date"])
    holdout = pd.read_csv(config.TABLES_DIR / "forecast_holdout.csv", parse_dates=["date"])

    # dim_date covers history plus the forecast horizon
    dates = pd.date_range(sales.date.min(), future.date.max())
    season = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
              6: "Summer", 7: "Summer", 8: "Summer", 9: "Autumn", 10: "Autumn", 11: "Autumn"}
    dim_date = pd.DataFrame({
        "date": dates.date,
        "year": dates.year,
        "quarter": "Q" + dates.quarter.astype(str),
        "month_num": dates.month,
        "month": dates.strftime("%b"),
        "year_month": dates.strftime("%Y-%m"),
        "iso_week": dates.isocalendar().week.to_numpy(),
        "weekday_num": dates.dayofweek + 1,
        "weekday": dates.strftime("%a"),
        "is_weekend": dates.dayofweek >= 5,
        "season": dates.month.map(season),
        "is_holiday_period": holiday_factor(dates) != 1,
    })
    dim_date.to_csv(out / "dim_date.csv", index=False)
    products.to_csv(out / "dim_product.csv", index=False)
    stores.to_csv(out / "dim_store.csv", index=False)

    fact = sales.merge(promo_calendar(promotions, dates), on=["date", "product_id"], how="left")
    fact["discount_pct"] = fact.discount_pct.fillna(0)
    fact["on_promo"] = fact.discount_pct > 0
    fact["gross_profit"] = fact.revenue - fact.cost
    fact = fact.round({"revenue": 2, "cost": 2, "gross_profit": 2})
    fact["date"] = fact.date.dt.date
    fact.to_csv(out / "fact_sales.csv", index=False)
    baskets.to_csv(out / "fact_baskets.csv", index=False)

    forecast = pd.concat([
        holdout[["date", "store_id", "product_id", "actual_units", "forecast",
                 "baseline_last_week", "baseline_4wk_avg"]].assign(period="Hold-out (evaluation)"),
        future.assign(period="Next 7 days"),
    ], ignore_index=True)
    forecast["date"] = forecast.date.dt.date
    forecast.to_csv(out / "fact_forecast.csv", index=False)

    for src, dst in [("inventory_plan", "fact_inventory_plan"),
                     ("promotion_uplift", "fact_promotions"),
                     ("association_rules", "basket_rules")]:
        pd.read_csv(config.TABLES_DIR / f"{src}.csv").to_csv(out / f"{dst}.csv", index=False)

    size = sum(f.stat().st_size for f in out.glob("*.csv")) / 1e6
    print(f"  Power BI star schema exported -> powerbi/data/ ({size:.1f} MB)")


if __name__ == "__main__":
    run()
