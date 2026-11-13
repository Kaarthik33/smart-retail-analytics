"""Promotion analysis: what happens to sales during promotions?

For every promotion, sales during the promotion are compared with a baseline:
the same product's average daily sales in the 28 days before the promotion
started. 28 days is exactly four weeks, so every weekday is represented
equally and the weekly sales rhythm cannot distort the comparison.

    uplift          = promo daily units / baseline daily units - 1
    incremental ... = what was earned during the promotion minus what the
                      baseline says would have been earned at full price

A promotion can lift units and revenue and still lose money, because every
unit (including those that would have sold anyway) is sold at a lower margin.
"""

from __future__ import annotations

import pandas as pd

from . import config, database, viz

BASELINE_DAYS = 28


def promotion_uplift(daily: pd.DataFrame, promotions: pd.DataFrame,
                     products: pd.DataFrame) -> pd.DataFrame:
    """``daily``: units, revenue and cost per product and date (chain-wide),
    indexed by (product_id, date) with no missing days."""
    info = products.set_index("product_id")
    first_day = daily.index.get_level_values("date").min()
    rows = []
    for p in promotions.itertuples():
        base_start = p.start_date - pd.Timedelta(days=BASELINE_DAYS)
        if base_start < first_day:
            continue                                   # not enough history for a baseline
        series = daily.loc[p.product_id]
        base = series.loc[base_start:p.start_date - pd.Timedelta(days=1)]
        promo = series.loc[p.start_date:p.end_date]
        days = len(promo)
        price, cost = info.at[p.product_id, "unit_price"], info.at[p.product_id, "unit_cost"]

        base_units = base.units.mean()
        base_revenue, base_profit = base_units * price * days, base_units * (price - cost) * days
        promo_units, promo_revenue = promo.units.sum(), promo.revenue.sum()
        promo_profit = promo_revenue - promo.cost.sum()
        rows.append({
            "promo_id": p.promo_id,
            "product_id": p.product_id,
            "product_name": info.at[p.product_id, "product_name"],
            "category": info.at[p.product_id, "category"],
            "start_date": p.start_date.date(),
            "days": days,
            "discount_pct": p.discount_pct,
            "baseline_units_per_day": round(base_units, 1),
            "promo_units_per_day": round(promo_units / days, 1),
            "unit_uplift_pct": round(100 * (promo_units / days / base_units - 1), 1),
            "incremental_units": round(promo_units - base_units * days),
            "incremental_revenue": round(promo_revenue - base_revenue, 2),
            "incremental_profit": round(promo_profit - base_profit, 2),
        })
    return pd.DataFrame(rows)


def summarise(uplift: pd.DataFrame, by: str) -> pd.DataFrame:
    g = uplift.groupby(by)
    out = pd.DataFrame({
        "promotions": g.size(),
        "avg_unit_uplift_pct": g.unit_uplift_pct.mean().round(1),
        "incremental_revenue": g.incremental_revenue.sum().round(0),
        "incremental_profit": g.incremental_profit.sum().round(0),
        "share_profitable_pct": (100 * g.incremental_profit.apply(lambda s: (s > 0).mean())).round(0),
    })
    return out.reset_index()


def run() -> dict:
    config.ensure_dirs()
    with database.connect() as con:
        sales = database.daily_sales(con)
        products = pd.read_sql_query("SELECT * FROM products", con)
        promotions = pd.read_sql_query("SELECT * FROM promotions", con,
                                       parse_dates=["start_date", "end_date"])

    dates = pd.date_range(sales.date.min(), sales.date.max())
    daily = (sales.groupby(["product_id", "date"])[["units", "revenue", "cost"]].sum()
             .reindex(pd.MultiIndex.from_product([products.product_id, dates],
                                                 names=["product_id", "date"]), fill_value=0)
             .sort_index())

    uplift = promotion_uplift(daily, promotions, products)
    by_discount = summarise(uplift, "discount_pct")
    by_category = summarise(uplift, "category").sort_values("avg_unit_uplift_pct", ascending=False)

    uplift.to_csv(config.TABLES_DIR / "promotion_uplift.csv", index=False)
    by_discount.to_csv(config.TABLES_DIR / "promotion_uplift_by_discount.csv", index=False)
    by_category.to_csv(config.TABLES_DIR / "promotion_uplift_by_category.csv", index=False)

    print(f"  {len(uplift)} promotions analysed: average unit uplift "
          f"{uplift.unit_uplift_pct.mean():+.0f}%, "
          f"{(uplift.incremental_profit > 0).mean():.0%} were profitable")
    _plot_discount(by_discount)
    _plot_category(by_category)
    return {"uplift": uplift, "by_discount": by_discount, "by_category": by_category}


def _plot_discount(by_discount: pd.DataFrame) -> None:
    fig, ax = viz.new_figure(7.5, 4.2)
    x = [f"{d:.0f}% off" for d in by_discount.discount_pct]
    bars = ax.bar(x, by_discount.avg_unit_uplift_pct, color=viz.BLUE, width=0.6)
    ax.bar_label(bars, labels=[f"+{v:.0f}%" for v in by_discount.avg_unit_uplift_pct], padding=3,
                 color=viz.INK_SECONDARY, fontsize=9.5)
    ax.grid(axis="x", visible=False)
    ax.set_ylim(0, by_discount.avg_unit_uplift_pct.max() * 1.15)
    viz.titled(ax, "Deeper discounts sell more units",
               "Average uplift in units sold per day vs. the 4 weeks before each promotion")
    ax.set_ylabel("Unit uplift, %")
    viz.save(fig, config.FIGURES_DIR / "09_promo_uplift_by_discount.png")


def _plot_category(by_category: pd.DataFrame) -> None:
    df = by_category.sort_values("incremental_profit", ascending=False)
    fig, ax = viz.new_figure(9, 4.6)
    colors = [viz.BLUE if v >= 0 else viz.ORANGE for v in df.incremental_profit]
    bars = ax.barh(df.category[::-1], df.incremental_profit[::-1], color=colors[::-1], height=0.62)
    ax.bar_label(bars, labels=[f"{'+' if v >= 0 else '-'}€{abs(v):,.0f}" for v in df.incremental_profit[::-1]], padding=4,
                 color=viz.INK_SECONDARY, fontsize=9)
    ax.axvline(0, color=viz.AXIS, linewidth=1)
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    lo, hi = df.incremental_profit.min(), df.incremental_profit.max()
    pad = (hi - min(lo, 0)) * 0.18
    ax.set_xlim(min(lo, 0) - pad, max(hi, 0) + pad)
    viz.titled(ax, "Did promotions pay off? Incremental gross profit by category",
               "Profit during promotions minus the profit the baseline would have earned at full price")
    ax.set_xlabel("Incremental gross profit, EUR (all promotions 2024-2025)")
    viz.save(fig, config.FIGURES_DIR / "10_promo_profit_by_category.png")


if __name__ == "__main__":
    run()
