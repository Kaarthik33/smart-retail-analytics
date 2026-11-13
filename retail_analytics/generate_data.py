"""Generate a realistic synthetic supermarket dataset.

The data is simulated (no real company's data is used), but it is built to
behave like real grocery sales so that every analysis has something to find:

* weekly rhythm (Friday/Saturday peaks) and yearly seasonality per product
* holiday effects (Easter, Christmas)
* slow underlying growth
* promotions with category-specific price elasticity
* shopping "missions" that make certain products sell together
* an inventory snapshot with deliberately imperfect stock levels

Everything is driven by one random seed, so the dataset is reproducible.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

# category -> (gross margin, promo elasticity, supplier lead time in days)
CATEGORIES = {
    "Produce":       (0.38, 4.0, 1),
    "Dairy":         (0.28, 3.5, 2),
    "Bakery":        (0.45, 3.5, 1),
    "Meat & Fish":   (0.25, 4.5, 2),
    "Pantry":        (0.32, 5.5, 5),
    "Beverages":     (0.30, 7.0, 4),
    "Snacks":        (0.40, 8.0, 4),
    "Frozen":        (0.33, 6.0, 3),
    "Household":     (0.35, 6.5, 7),
    "Personal Care": (0.42, 6.0, 7),
}

# category -> [(product name, list price in EUR, relative popularity)]
CATALOG = {
    "Produce": [
        ("Bananas", 1.49, 3.2), ("Apples", 2.49, 2.4), ("Tomatoes", 2.29, 2.2),
        ("Potatoes", 2.99, 1.8), ("Onions", 1.29, 1.6), ("Lettuce", 1.19, 1.4),
        ("Strawberries", 3.49, 1.3), ("Lemons", 1.59, 0.9), ("Avocados", 1.99, 1.1),
    ],
    "Dairy": [
        ("Whole Milk", 1.19, 3.4), ("Butter", 2.29, 2.3), ("Eggs 12-pack", 3.19, 2.5),
        ("Cheddar Cheese", 2.99, 1.5), ("Parmesan", 3.79, 0.7), ("Greek Yogurt", 1.49, 1.9),
        ("Cooking Cream", 0.99, 1.0), ("Mozzarella", 1.29, 1.3),
    ],
    "Bakery": [
        ("White Bread", 1.79, 2.6), ("Wholegrain Bread", 2.29, 1.9), ("Burger Buns", 1.59, 0.7),
        ("Croissants", 2.49, 1.2), ("Tortilla Wraps", 1.89, 0.8), ("Bagels", 2.19, 0.7),
    ],
    "Meat & Fish": [
        ("Ground Beef", 5.49, 1.3), ("Chicken Breast", 6.99, 1.7), ("Bacon", 2.79, 1.1),
        ("Sausages", 3.49, 1.0), ("Salmon Fillet", 7.99, 0.7), ("Sliced Ham", 2.49, 1.2),
    ],
    "Pantry": [
        ("Spaghetti", 0.99, 1.4), ("Pasta Sauce", 1.99, 0.9), ("Rice", 2.49, 1.1),
        ("Olive Oil", 6.99, 0.6), ("Flour", 0.89, 0.8), ("Sugar", 1.29, 0.8),
        ("Canned Tomatoes", 0.89, 1.0), ("Tomato Soup", 1.49, 0.7), ("Strawberry Jam", 2.19, 0.6),
        ("Peanut Butter", 2.99, 0.6), ("Cornflakes", 2.79, 0.9), ("Muesli", 3.29, 0.7),
        ("Ketchup", 2.29, 0.6), ("Salsa Dip", 2.19, 0.4),
    ],
    "Beverages": [
        ("Coffee Beans", 6.49, 1.2), ("Black Tea", 2.49, 0.6), ("Orange Juice", 2.29, 1.4),
        ("Cola", 1.59, 1.7), ("Mineral Water 6-pack", 2.99, 2.0), ("Lager Beer 6-pack", 5.99, 1.2),
        ("Red Wine", 6.99, 0.8), ("Sparkling Wine", 5.49, 0.4), ("Oat Drink", 1.99, 0.8),
    ],
    "Snacks": [
        ("Tortilla Chips", 1.79, 0.7), ("Potato Chips", 1.69, 1.4), ("Milk Chocolate", 1.29, 1.6),
        ("Butter Biscuits", 1.49, 0.9), ("Salted Peanuts", 1.99, 0.7), ("Gummy Bears", 1.19, 1.0),
    ],
    "Frozen": [
        ("Vanilla Ice Cream", 3.49, 0.9), ("Frozen Pizza", 2.99, 1.5), ("Frozen Peas", 1.49, 0.7),
        ("Fish Fingers", 3.29, 0.7), ("French Fries", 2.19, 0.9),
    ],
    "Household": [
        ("Toilet Paper", 4.49, 1.2), ("Dish Soap", 1.79, 0.6), ("Laundry Detergent", 7.99, 0.5),
        ("Paper Towels", 2.99, 0.7), ("Trash Bags", 2.49, 0.5),
    ],
    "Personal Care": [
        ("Diapers", 9.99, 0.35), ("Baby Wipes", 1.99, 0.3), ("Shampoo", 2.99, 0.6),
        ("Toothpaste", 1.99, 0.7), ("Shower Gel", 1.79, 0.6),
    ],
}

# product -> (peak day of year, amplitude). Demand = 1 + amp * cos(distance to peak).
SEASONALITY = {
    "Vanilla Ice Cream": (200, 0.80), "Strawberries": (160, 0.75), "Lettuce": (190, 0.30),
    "Mineral Water 6-pack": (200, 0.40), "Cola": (200, 0.25), "Lager Beer 6-pack": (195, 0.35),
    "Sausages": (190, 0.45), "Burger Buns": (190, 0.50), "Ground Beef": (190, 0.20),
    "Ketchup": (190, 0.30), "Tomatoes": (200, 0.25), "Avocados": (180, 0.20),
    "Tomato Soup": (15, 0.55), "Black Tea": (15, 0.35), "Potatoes": (330, 0.20),
    "Milk Chocolate": (350, 0.40), "Butter Biscuits": (350, 0.40), "Flour": (345, 0.50),
    "Sugar": (345, 0.40), "Sparkling Wine": (358, 0.90), "Red Wine": (350, 0.35),
    "Salmon Fillet": (355, 0.35), "Lemons": (20, 0.20), "Frozen Pizza": (20, 0.15),
}

# Shopping missions: products that are bought together on purpose.
# (name, products, relative frequency)
MISSIONS = [
    ("Pasta night", ["Spaghetti", "Pasta Sauce", "Parmesan"], 1.3),
    ("Breakfast", ["White Bread", "Butter", "Strawberry Jam"], 1.2),
    ("Cereal", ["Cornflakes", "Whole Milk"], 1.1),
    ("Game night", ["Tortilla Chips", "Salsa Dip", "Lager Beer 6-pack"], 0.8),
    ("Barbecue", ["Burger Buns", "Ground Beef", "Ketchup"], 0.9),
    ("Baby care", ["Diapers", "Baby Wipes"], 0.6),
    ("Coffee", ["Coffee Beans", "Cooking Cream"], 0.8),
    ("Tea time", ["Black Tea", "Butter Biscuits"], 0.6),
    ("Baking", ["Flour", "Sugar", "Eggs 12-pack", "Butter"], 0.7),
    ("Tex-Mex", ["Tortilla Wraps", "Avocados", "Tomatoes"], 0.7),
]
MISSION_PROBABILITY = 0.45   # share of baskets driven by a mission
MISSION_ITEM_PROBABILITY = 0.85

STORES = [
    ("S01", "FreshMart City Center", "Urban flagship", 1.35),
    ("S02", "FreshMart Riverside", "Suburban", 1.00),
    ("S03", "FreshMart Express Station", "Convenience", 0.65),
]

# Monday .. Sunday
WEEKDAY_FACTOR = np.array([0.90, 0.85, 0.90, 1.00, 1.25, 1.45, 0.70])
HOUR_WEIGHTS = np.array(
    # 08  09  10  11  12  13  14  15  16  17  18  19  20
    [3, 5, 7, 9, 10, 8, 6, 6, 8, 11, 12, 9, 5], dtype=float
)
HOURS = np.arange(8, 21)

EASTER_SUNDAYS = {2024: "2024-03-31", 2025: "2025-04-20", 2026: "2026-04-05"}


def holiday_factor(dates: pd.DatetimeIndex) -> np.ndarray:
    """Store traffic multiplier around public holidays."""
    f = np.ones(len(dates))
    md = dates.month * 100 + dates.day
    f[(md >= 1218) & (md <= 1224)] = 1.45      # Christmas shopping week
    f[(md >= 1229) & (md <= 1231)] = 1.25      # New Year's Eve
    f[(md == 1225) | (md == 1226) | (md == 101)] = 0.40  # reduced opening hours
    for easter in EASTER_SUNDAYS.values():
        d = pd.Timestamp(easter)
        f[(dates >= d - pd.Timedelta(days=4)) & (dates < d)] = 1.30
    return f


def build_products() -> pd.DataFrame:
    rows = []
    pid = 1
    for category, items in CATALOG.items():
        margin, elasticity, lead = CATEGORIES[category]
        for name, price, popularity in items:
            rows.append({
                "product_id": f"P{pid:03d}",
                "product_name": name,
                "category": category,
                "unit_price": price,
                "unit_cost": round(price * (1 - margin), 2),
                "lead_time_days": lead,
                "_popularity": popularity,
                "_elasticity": elasticity,
            })
            pid += 1
    return pd.DataFrame(rows)


def build_stores() -> pd.DataFrame:
    return pd.DataFrame(STORES, columns=["store_id", "store_name", "store_type", "_size"])


def build_promotions(products: pd.DataFrame, dates: pd.DatetimeIndex,
                     rng: np.random.Generator) -> pd.DataFrame:
    """Chain-wide weekly promotions, starting on Mondays, never overlapping per product."""
    mondays = dates[dates.dayofweek == 0]
    rows, busy = [], {}
    n_target = int(len(mondays) * 1.6)
    attempts = 0
    while len(rows) < n_target and attempts < n_target * 20:
        attempts += 1
        p = products.iloc[rng.integers(len(products))]
        start = mondays[rng.integers(len(mondays))]
        length = int(rng.choice([7, 14], p=[0.75, 0.25]))
        end = start + pd.Timedelta(days=length - 1)
        if end > dates[-1]:
            continue
        # keep a 5-week gap so every promotion has a clean baseline window
        if any(start <= b_end + pd.Timedelta(days=35) and end >= b_start - pd.Timedelta(days=35)
               for b_start, b_end in busy.get(p.product_id, [])):
            continue
        busy.setdefault(p.product_id, []).append((start, end))
        rows.append({
            "product_id": p.product_id,
            "start_date": start,
            "end_date": end,
            "discount_pct": float(rng.choice([10, 15, 20, 25, 30], p=[0.2, 0.25, 0.3, 0.15, 0.1])),
        })
    promos = pd.DataFrame(rows).sort_values(["start_date", "product_id"]).reset_index(drop=True)
    promos.insert(0, "promo_id", [f"PR{i:04d}" for i in range(1, len(promos) + 1)])
    return promos


def generate(start: str = config.START_DATE, end: str = config.END_DATE,
             base_baskets: int = config.BASE_DAILY_BASKETS, seed: int = config.SEED) -> dict:
    """Return a dict of DataFrames: products, stores, promotions, transactions,
    transaction_items and inventory."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, end, freq="D")
    n_days = len(dates)

    products = build_products()
    stores = build_stores()
    promotions = build_promotions(products, dates, rng)
    n_products = len(products)
    name_to_idx = {n: i for i, n in enumerate(products.product_name)}

    # --- per-day demand weight for every product (days x products) ---------
    doy = dates.dayofyear.to_numpy()
    season = np.ones((n_days, n_products))
    for name, (peak, amp) in SEASONALITY.items():
        season[:, name_to_idx[name]] = 1 + amp * np.cos(2 * np.pi * (doy - peak) / 365.25)

    discount = np.zeros((n_days, n_products))
    pid_to_idx = {p: i for i, p in enumerate(products.product_id)}
    for promo in promotions.itertuples():
        mask = (dates >= promo.start_date) & (dates <= promo.end_date)
        discount[mask, pid_to_idx[promo.product_id]] = promo.discount_pct / 100
    promo_boost = 1 + discount * products._elasticity.to_numpy()

    weight = products._popularity.to_numpy() * season * promo_boost

    mission_items = [np.array([name_to_idx[n] for n in items]) for _, items, _ in MISSIONS]
    mission_base = np.array([w for _, _, w in MISSIONS])

    # --- store traffic ------------------------------------------------------
    trend = 1 + 0.08 * np.arange(n_days) / max(n_days - 1, 1)
    yearly = 1 + 0.05 * np.cos(2 * np.pi * (doy - 350) / 365.25)
    traffic = (base_baskets * WEEKDAY_FACTOR[dates.dayofweek] * holiday_factor(dates)
               * trend * yearly)

    prices = products.unit_price.to_numpy()
    hour_p = HOUR_WEIGHTS / HOUR_WEIGHTS.sum()

    tx_parts, item_parts = [], []
    next_tx = 1
    for store in stores.itertuples():
        for d in range(n_days):
            n = rng.poisson(traffic[d] * store._4 * rng.lognormal(0, 0.06))
            if n == 0:
                continue
            w = weight[d]
            # random fill-in items
            sizes = 1 + rng.poisson(3.0, n)
            basket = np.repeat(np.arange(n), sizes)
            item = rng.choice(n_products, size=sizes.sum(), p=w / w.sum())
            # mission items; a mission gets more popular when its products are in season/on promo
            m_weight = mission_base * np.array([(season[d, m] * promo_boost[d, m]).mean()
                                                for m in mission_items])
            has_mission = rng.random(n) < MISSION_PROBABILITY
            mission = rng.choice(len(MISSIONS), size=n, p=m_weight / m_weight.sum())
            extra_b, extra_i = [basket], [item]
            for m, m_items in enumerate(mission_items):
                idx = np.flatnonzero(has_mission & (mission == m))
                for it in m_items:
                    keep = idx[rng.random(len(idx)) < MISSION_ITEM_PROBABILITY]
                    extra_b.append(keep)
                    extra_i.append(np.full(len(keep), it))
            basket = np.concatenate(extra_b)
            item = np.concatenate(extra_i)

            # one line per (basket, product); repeated picks become quantity
            key, qty = np.unique(basket * n_products + item, return_counts=True)
            b, it = key // n_products, key % n_products
            qty = qty + rng.poisson(0.15 + 0.8 * discount[d, it])  # stock-up on deals

            tx_ids = next_tx + np.arange(n)
            minutes = rng.choice(HOURS, size=n, p=hour_p) * 60 + rng.integers(0, 60, n)
            tx_parts.append(pd.DataFrame({
                "transaction_id": tx_ids,
                "store_id": store.store_id,
                "transaction_ts": dates[d] + pd.to_timedelta(minutes, unit="m"),
            }))
            disc = discount[d, it]
            item_parts.append(pd.DataFrame({
                "transaction_id": tx_ids[b],
                "product_idx": it,
                "quantity": qty,
                "unit_price": prices[it],
                "discount_pct": disc * 100,
            }))
            next_tx += n

    transactions = pd.concat(tx_parts, ignore_index=True)
    transactions["transaction_date"] = transactions.transaction_ts.dt.normalize()
    items = pd.concat(item_parts, ignore_index=True)
    items["product_id"] = products.product_id.to_numpy()[items.pop("product_idx").to_numpy()]
    items["line_revenue"] = (items.quantity * items.unit_price
                             * (1 - items.discount_pct / 100)).round(2)
    items = items[["transaction_id", "product_id", "quantity", "unit_price",
                   "discount_pct", "line_revenue"]]

    inventory = _build_inventory(transactions, items, products, stores, dates, rng)

    products = products.drop(columns=["_popularity", "_elasticity"])
    stores = stores.drop(columns=["_size"])
    return {
        "products": products, "stores": stores, "promotions": promotions,
        "transactions": transactions, "transaction_items": items, "inventory": inventory,
    }


def _build_inventory(transactions, items, products, stores, dates, rng) -> pd.DataFrame:
    """Stock on hand at close of the last day. Stock levels are set by a rough
    rule of thumb (as many stores do), so some products are short and some are
    overstocked - which is what the inventory analysis should detect."""
    recent = transactions.loc[transactions.transaction_date > dates[-1] - pd.Timedelta(days=28),
                              ["transaction_id", "store_id"]]
    sold = (items.merge(recent, on="transaction_id")
            .groupby(["store_id", "product_id"]).quantity.sum() / 28)
    grid = pd.MultiIndex.from_product([stores.store_id, products.product_id],
                                      names=["store_id", "product_id"])
    daily = sold.reindex(grid, fill_value=0).rename("daily").reset_index()
    days_of_cover = rng.choice([1.5, 4, 8, 14, 30], size=len(daily), p=[0.12, 0.23, 0.35, 0.2, 0.1])
    daily["stock_on_hand"] = np.round(daily.daily * days_of_cover * rng.uniform(0.8, 1.2, len(daily))
                                      ).astype(int)
    daily.insert(0, "snapshot_date", dates[-1])
    return daily[["snapshot_date", "store_id", "product_id", "stock_on_hand"]]


def run() -> dict:
    config.ensure_dirs()
    data = generate()
    for name, df in data.items():
        df.to_csv(config.RAW_DIR / f"{name}.csv", index=False)
    print(f"  generated {len(data['transactions']):,} transactions, "
          f"{len(data['transaction_items']):,} line items, "
          f"{len(data['promotions'])} promotions")
    return data


if __name__ == "__main__":
    run()
