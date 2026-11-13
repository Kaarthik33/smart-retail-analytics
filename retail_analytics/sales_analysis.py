"""Sales analysis: run the SQL query library and turn the results into tables and charts.

Answers:  Which products generate the most revenue?
          Which days and seasons have the highest sales?
"""

from __future__ import annotations

import calendar

import pandas as pd

from . import config, database, viz


def run() -> dict[str, pd.DataFrame]:
    config.ensure_dirs()
    results = {}
    with database.connect() as con:
        for path in sorted(config.QUERY_DIR.glob("*.sql")):
            name = path.stem.split("_", 1)[1]          # "01_top_products" -> "top_products"
            df = database.run_query_file(path, con)
            df.to_csv(config.TABLES_DIR / f"{name}.csv", index=False)
            results[name] = df
    print(f"  ran {len(results)} SQL queries -> reports/tables/")

    _plot_top_products(results["top_products_by_revenue"])
    _plot_monthly(results["monthly_sales_trend"])
    _plot_weekday(results["sales_by_weekday"])
    _plot_seasonality(results["category_seasonality"])
    return results


def _plot_top_products(df: pd.DataFrame) -> None:
    top = df.head(15)
    fig, ax = viz.new_figure(9, 5.6)
    viz.hbar(ax, top.product_name, top.revenue / 1000, fmt="€{:,.0f}k")
    viz.titled(ax, "Top 15 products by revenue",
               f"These 15 of {len(df)} products bring in "
               f"{top.revenue_share_pct.sum():.0f}% of total revenue")
    ax.set_xlabel("Revenue, EUR thousands (2024-2025)")
    viz.save(fig, config.FIGURES_DIR / "01_top_products.png")


def _plot_monthly(df: pd.DataFrame) -> None:
    fig, ax = viz.new_figure(9, 4.4)
    x = pd.to_datetime(df.year_month)
    ax.plot(x, df.revenue / 1000, color=viz.BLUE)
    peak = df.revenue.idxmax()
    ax.scatter([x[peak]], [df.revenue[peak] / 1000], color=viz.BLUE, s=45, zorder=3,
               edgecolor=viz.SURFACE, linewidth=2)
    ax.annotate(f"{x[peak]:%b %Y}: €{df.revenue[peak] / 1000:,.0f}k", (x[peak], df.revenue[peak] / 1000),
                xytext=(-8, 4), textcoords="offset points", ha="right", color=viz.INK_SECONDARY,
                fontsize=9)
    ax.set_ylim(0, df.revenue.max() / 1000 * 1.12)
    ax.grid(axis="x", visible=False)
    yoy = df.yoy_growth_pct.dropna().mean()
    viz.titled(ax, "Monthly revenue", f"{x[peak]:%B} is the peak month; 2025 ran {yoy:+.1f}% vs. 2024 on average")
    ax.set_ylabel("Revenue, EUR thousands")
    viz.save(fig, config.FIGURES_DIR / "02_monthly_revenue.png")


def _plot_weekday(df: pd.DataFrame) -> None:
    fig, ax = viz.new_figure(7.5, 4.2)
    bars = ax.bar(df.weekday.str[:3], df.avg_daily_revenue, color=viz.BLUE, width=0.62)
    ax.bar_label(bars, labels=[f"{v:.0f}" for v in df.index_vs_avg_day], padding=3,
                 color=viz.INK_SECONDARY, fontsize=9)
    ax.grid(axis="x", visible=False)
    best = df.loc[df.avg_daily_revenue.idxmax()]
    viz.titled(ax, "Average daily revenue by weekday",
               f"{best.weekday} sells {best.index_vs_avg_day - 100:.0f}% more than an average day "
               "(labels: index, 100 = average day)")
    ax.set_ylabel("Average revenue per day, EUR")
    viz.save(fig, config.FIGURES_DIR / "03_weekday_revenue.png")


def _plot_seasonality(df: pd.DataFrame) -> None:
    grid = df.pivot(index="category", columns="month", values="seasonal_index")
    grid = grid.loc[grid.std(axis=1).sort_values(ascending=False).index]
    fig, ax = viz.new_figure(9.5, 4.8)
    span = max(abs(grid.values - 100).max(), 10)
    im = ax.imshow(grid.values, cmap=viz.DIVERGING, vmin=100 - span, vmax=100 + span, aspect="auto")
    ax.set_xticks(range(12), [calendar.month_abbr[m] for m in grid.columns])
    ax.set_yticks(range(len(grid)), grid.index)
    ax.grid(False)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    # white gaps between cells
    ax.set_xticks([i - 0.5 for i in range(1, 12)], minor=True)
    ax.set_yticks([i - 0.5 for i in range(1, len(grid))], minor=True)
    ax.grid(which="minor", color=viz.SURFACE, linewidth=2)
    ax.tick_params(which="minor", length=0)
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            v = grid.values[i, j]
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=8.5,
                    color="#ffffff" if abs(v - 100) > span * 0.6 else viz.INK)
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.outline.set_visible(False)
    cbar.set_label("Seasonal index")
    viz.titled(ax, "Seasonal index by category and month",
               "100 = the category's average month. Blue = above average, orange = below")
    viz.save(fig, config.FIGURES_DIR / "04_category_seasonality.png")


if __name__ == "__main__":
    run()
