"""Demand forecasting: how many units of each product will each store sell?

Approach
--------
* One global gradient-boosting model (scikit-learn ``HistGradientBoostingRegressor``
  with a Poisson objective, suited to count data) trained on every
  store x product x day.
* Features: calendar, holidays, price and promotion, plus lagged demand.
  Every lag is at least ``FORECAST_HORIZON`` (7) days old, so each prediction is
  a true 7-day-ahead forecast - nothing from the future leaks in.
* Evaluation: the last 8 weeks are held out and never seen in training. The
  model is compared against two baselines a store could run in a spreadsheet:
  "same weekday last week" and "average of the last 4 weeks".
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance

from . import config, database, viz
from .generate_data import holiday_factor

H = config.FORECAST_HORIZON
CATEGORICAL = ["store_id", "product_id", "category"]
FEATURES = CATEGORICAL + [
    "weekday", "month", "doy_sin", "doy_cos", "holiday_factor", "days_to_christmas",
    "unit_price", "discount_pct",
    "lag_7", "lag_14", "lag_21", "lag_28", "roll_mean_7", "roll_mean_28",
    "lag_7_discount", "roll_mean_discount_28",
]


def promo_calendar(promotions: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Expand promotions to one row per product and promoted day."""
    rows = []
    for p in promotions.itertuples():
        days = pd.date_range(p.start_date, p.end_date)
        rows.append(pd.DataFrame({"date": days, "product_id": p.product_id,
                                  "discount_pct": p.discount_pct}))
    cal = pd.concat(rows, ignore_index=True)
    return cal[cal.date.isin(dates)]


def build_panel(sales: pd.DataFrame, products: pd.DataFrame, promotions: pd.DataFrame,
                future_days: int = H) -> pd.DataFrame:
    """Dense store x product x day panel (zero-sales days included) with features.
    ``future_days`` extra days are appended with unknown demand so they can be predicted."""
    last = sales.date.max()
    dates = pd.date_range(sales.date.min(), last + pd.Timedelta(days=future_days))
    grid = pd.MultiIndex.from_product(
        [sorted(sales.store_id.unique()), products.product_id, dates],
        names=["store_id", "product_id", "date"]).to_frame(index=False)
    panel = grid.merge(sales[["date", "store_id", "product_id", "units"]],
                       on=["date", "store_id", "product_id"], how="left")
    panel["units"] = panel.units.fillna(0.0)
    panel.loc[panel.date > last, "units"] = np.nan

    panel = panel.merge(products[["product_id", "category", "unit_price"]], on="product_id")
    panel = panel.merge(promo_calendar(promotions, dates), on=["date", "product_id"], how="left")
    panel["discount_pct"] = panel.discount_pct.fillna(0.0)
    panel = panel.sort_values(["store_id", "product_id", "date"]).reset_index(drop=True)

    # calendar
    panel["weekday"] = panel.date.dt.dayofweek
    panel["month"] = panel.date.dt.month
    doy = panel.date.dt.dayofyear
    panel["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    panel["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    hol = pd.Series(holiday_factor(dates), index=dates)
    panel["holiday_factor"] = panel.date.map(hol)
    christmas = pd.to_datetime(panel.date.dt.year.astype(str) + "-12-24")
    panel["days_to_christmas"] = (christmas - panel.date).dt.days.clip(-8, 30)

    # lagged demand and lagged promotion intensity (all >= H days old)
    g = panel.groupby(["store_id", "product_id"], sort=False)
    for lag in (7, 14, 21, 28):
        panel[f"lag_{lag}"] = g.units.shift(lag)
    panel["roll_mean_7"] = g.units.transform(lambda s: s.shift(H).rolling(7).mean())
    panel["roll_mean_28"] = g.units.transform(lambda s: s.shift(H).rolling(28).mean())
    panel["lag_7_discount"] = g.discount_pct.shift(7)
    panel["roll_mean_discount_28"] = g.discount_pct.transform(
        lambda s: s.shift(H).rolling(28).mean())

    for col in CATEGORICAL:
        panel[col] = panel[col].astype("category")
    return panel.dropna(subset=["roll_mean_28"]).reset_index(drop=True)


def make_model() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss="poisson", learning_rate=0.06, max_iter=400, max_leaf_nodes=31,
        min_samples_leaf=40, l2_regularization=1.0, categorical_features=CATEGORICAL,
        early_stopping=True, validation_fraction=0.1, random_state=config.SEED)


def wape(actual, forecast) -> float:
    """Weighted absolute percentage error: total absolute error / total demand."""
    return float(np.abs(np.asarray(actual) - np.asarray(forecast)).sum() / np.asarray(actual).sum())


def evaluate(holdout: pd.DataFrame) -> pd.DataFrame:
    methods = {
        "Gradient boosting (this project)": "forecast",
        "Baseline: same weekday last week": "lag_7",
        "Baseline: 4-week average": "roll_mean_28",
    }
    weekly = (holdout.assign(week=holdout.date.dt.to_period("W-SUN"))
              .groupby(["store_id", "product_id", "week"], observed=True)
              [["units"] + list(methods.values())].sum())
    rows = []
    for label, col in methods.items():
        rows.append({
            "method": label,
            "wape_daily_pct": round(100 * wape(holdout.units, holdout[col]), 1),
            "wape_weekly_pct": round(100 * wape(weekly.units, weekly[col]), 1),
            "mae_units_per_day": round(float(np.abs(holdout.units - holdout[col]).mean()), 2),
            "bias_pct": round(100 * float((holdout[col].sum() - holdout.units.sum())
                                          / holdout.units.sum()), 1),
        })
    return pd.DataFrame(rows)


def run() -> dict:
    config.ensure_dirs()
    with database.connect() as con:
        sales = database.daily_sales(con)
        products = pd.read_sql_query("SELECT * FROM products", con)
        promotions = pd.read_sql_query("SELECT * FROM promotions", con,
                                       parse_dates=["start_date", "end_date"])

    panel = build_panel(sales, products, promotions)
    last = sales.date.max()
    cutoff = last - pd.Timedelta(days=config.HOLDOUT_DAYS)
    train = panel[panel.date <= cutoff]
    holdout = panel[(panel.date > cutoff) & (panel.date <= last)].copy()
    future = panel[panel.date > last].copy()

    # 1) honest evaluation: fit on the past, score the unseen last 8 weeks
    model = make_model().fit(train[FEATURES], train.units)
    holdout["forecast"] = model.predict(holdout[FEATURES])
    metrics = evaluate(holdout)
    metrics.to_csv(config.TABLES_DIR / "forecast_metrics.csv", index=False)

    sample = holdout.sample(min(len(holdout), 8000), random_state=config.SEED)
    imp = permutation_importance(model, sample[FEATURES], sample.units, n_repeats=3,
                                 random_state=config.SEED,
                                 scoring="neg_mean_absolute_error")
    importance = (pd.DataFrame({"feature": FEATURES, "mae_increase": imp.importances_mean})
                  .sort_values("mae_increase", ascending=False).round(4))
    importance.to_csv(config.TABLES_DIR / "forecast_feature_importance.csv", index=False)

    # 2) production forecast: refit on all history, predict the next 7 days
    final = make_model().fit(panel.loc[panel.date <= last, FEATURES],
                             panel.loc[panel.date <= last, "units"])
    future["forecast"] = final.predict(future[FEATURES])

    cols = ["date", "store_id", "product_id"]
    holdout_out = holdout[cols + ["units", "forecast", "lag_7", "roll_mean_28", "discount_pct"]]
    holdout_out = holdout_out.rename(columns={"units": "actual_units",
                                              "lag_7": "baseline_last_week",
                                              "roll_mean_28": "baseline_4wk_avg"})
    holdout_out = holdout_out.round({"forecast": 2, "baseline_4wk_avg": 2})
    holdout_out.to_csv(config.TABLES_DIR / "forecast_holdout.csv", index=False)
    future_out = future[cols + ["forecast"]].round({"forecast": 2})
    future_out.to_csv(config.TABLES_DIR / "forecast_next_7_days.csv", index=False)

    m = metrics.iloc[0]
    print(f"  holdout WAPE: {m.wape_daily_pct}% daily, {m.wape_weekly_pct}% weekly "
          f"(last-week baseline: {metrics.iloc[1].wape_daily_pct}% / {metrics.iloc[1].wape_weekly_pct}%)")
    _plot_holdout(holdout)
    _plot_metrics(metrics)
    return {"metrics": metrics, "holdout": holdout_out, "future": future_out,
            "importance": importance}


def _plot_holdout(holdout: pd.DataFrame) -> None:
    daily = holdout.groupby("date")[["units", "forecast"]].sum()
    fig, ax = viz.new_figure(9.5, 4.4)
    ax.plot(daily.index, daily.units, color=viz.NEUTRAL, label="Actual")
    ax.plot(daily.index, daily.forecast, color=viz.BLUE, label="Forecast (made 7 days ahead)")
    ax.set_ylim(0, daily.units.max() * 1.15)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="lower left", ncols=2)
    viz.titled(ax, "Forecast vs. actual on the 8 held-out weeks",
               f"Total units per day across all stores and products; "
               f"error on the daily total: {100 * viz_wape(daily):.1f}%")
    ax.set_ylabel("Units sold per day")
    viz.save(fig, config.FIGURES_DIR / "06_forecast_vs_actual.png")


def viz_wape(daily: pd.DataFrame) -> float:
    return wape(daily.units, daily.forecast)


def _plot_metrics(metrics: pd.DataFrame) -> None:
    fig, ax = viz.new_figure(8.5, 3.2)
    colors = [viz.BLUE] + [viz.NEUTRAL] * (len(metrics) - 1)
    viz.hbar(ax, metrics.method, metrics.wape_weekly_pct, color=colors[::-1], fmt="{:.1f}%")
    viz.titled(ax, "Forecast error by method (lower is better)",
               "Weekly WAPE per store and product on the held-out 8 weeks")
    ax.set_xlabel("WAPE, %")
    viz.save(fig, config.FIGURES_DIR / "07_forecast_accuracy.png")


if __name__ == "__main__":
    run()
