"""Inventory planning: how much stock should each store keep of each product?

Classic periodic-review policy, driven by the demand forecast:

    safety stock     = z * sigma * sqrt(lead time + review period)
    reorder point    = daily demand * lead time + z * sigma * sqrt(lead time)
    order-up-to level = daily demand * (lead time + review period) + safety stock

where ``daily demand`` is the forecast for the coming week, ``sigma`` is the
standard deviation of the forecast's daily error on the hold-out period (so a
product that is hard to predict automatically gets more buffer) and ``z`` is
set by the target service level (1.645 -> 95%).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, database, viz


def plan(daily_demand, sigma, lead_time, stock_on_hand,
         z: float = config.SERVICE_LEVEL_Z, review: int = config.REVIEW_PERIOD_DAYS) -> pd.DataFrame:
    """Vectorised inventory policy. All inputs are array-like of equal length."""
    d = np.asarray(daily_demand, dtype=float)
    s = np.asarray(sigma, dtype=float)
    lt = np.asarray(lead_time, dtype=float)
    stock = np.asarray(stock_on_hand, dtype=float)

    safety = z * s * np.sqrt(lt + review)
    reorder_point = d * lt + z * s * np.sqrt(lt)
    target = d * (lt + review) + safety
    order_qty = np.where(stock <= reorder_point, np.ceil(target - stock), 0).clip(min=0)
    cover = np.divide(stock, d, out=np.full_like(stock, np.inf), where=d > 0)
    status = np.select([stock <= reorder_point, stock > 1.5 * target],
                       ["Reorder now", "Overstocked"], default="Healthy")
    return pd.DataFrame({
        "forecast_daily_demand": d.round(2),
        "safety_stock": np.ceil(safety).astype(int),
        "reorder_point": np.ceil(reorder_point).astype(int),
        "order_up_to_level": np.ceil(target).astype(int),
        "stock_on_hand": stock.astype(int),
        "days_of_cover": cover.round(1),
        "status": status,
        "recommended_order_qty": order_qty.astype(int),
    })


def run() -> pd.DataFrame:
    config.ensure_dirs()
    holdout = pd.read_csv(config.TABLES_DIR / "forecast_holdout.csv")
    future = pd.read_csv(config.TABLES_DIR / "forecast_next_7_days.csv")
    with database.connect() as con:
        products = pd.read_sql_query("SELECT * FROM products", con)
        stores = pd.read_sql_query("SELECT * FROM stores", con)
        stock = pd.read_sql_query("SELECT store_id, product_id, stock_on_hand FROM inventory", con)

    keys = ["store_id", "product_id"]
    demand = future.groupby(keys).forecast.mean().rename("daily_demand")
    holdout["error"] = holdout.actual_units - holdout.forecast
    sigma = holdout.groupby(keys).error.std().rename("sigma")

    base = (stock.merge(demand, on=keys).merge(sigma, on=keys)
            .merge(products, on="product_id").merge(stores, on="store_id"))
    result = pd.concat([
        base[["store_id", "store_name", "product_id", "product_name", "category", "lead_time_days"]],
        plan(base.daily_demand, base.sigma, base.lead_time_days, base.stock_on_hand),
    ], axis=1)
    result["order_value_eur"] = (result.recommended_order_qty * base.unit_cost).round(2)
    result["excess_stock_value_eur"] = (
        (result.stock_on_hand - result.order_up_to_level).clip(lower=0) * base.unit_cost
    ).where(result.status == "Overstocked", 0).round(2)
    result = result.sort_values(["status", "days_of_cover"],
                                key=lambda c: c.map({"Reorder now": 0, "Overstocked": 1, "Healthy": 2})
                                if c.name == "status" else c).reset_index(drop=True)
    result.to_csv(config.TABLES_DIR / "inventory_plan.csv", index=False)

    counts = result.status.value_counts()
    print(f"  inventory plan: {counts.get('Reorder now', 0)} to reorder, "
          f"{counts.get('Overstocked', 0)} overstocked, {counts.get('Healthy', 0)} healthy")
    _plot(result)
    return result


def _plot(result: pd.DataFrame) -> None:
    order = ["Reorder now", "Healthy", "Overstocked"]
    counts = (result.groupby(["store_name", "status"]).size().unstack(fill_value=0)
              .reindex(columns=order, fill_value=0))
    fig, ax = viz.new_figure(9, 3.6)
    left = np.zeros(len(counts))
    for status in order:
        vals = counts[status].to_numpy()
        bars = ax.barh(counts.index, vals, left=left, color=viz.STATUS[status], label=status,
                       height=0.55, edgecolor=viz.SURFACE, linewidth=2)
        ax.bar_label(bars, labels=[str(v) if v else "" for v in vals], label_type="center",
                     color=viz.INK if status == "Overstocked" else "#ffffff", fontsize=9.5)
        left += vals
    ax.grid(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.invert_yaxis()
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncols=3)
    viz.titled(ax, "Stock status by store",
               f"Number of products; total recommended order: "
               f"€{result.order_value_eur.sum():,.0f} at cost")
    ax.set_xlabel("Products")
    viz.save(fig, config.FIGURES_DIR / "08_inventory_status.png")


if __name__ == "__main__":
    run()
