"""Unit tests for the analytical building blocks. Run with:  pytest"""

import numpy as np
import pandas as pd
import pytest

from retail_analytics import basket_analysis, forecasting, generate_data, inventory, promotions


@pytest.fixture(scope="module")
def data():
    return generate_data.generate(start="2024-01-01", end="2024-03-31", base_baskets=15, seed=1)


def test_generated_data_is_consistent(data):
    items, tx, products = data["transaction_items"], data["transactions"], data["products"]
    assert tx.transaction_id.is_unique
    assert not items.duplicated(["transaction_id", "product_id"]).any()
    assert set(items.transaction_id) == set(tx.transaction_id)      # no empty or orphan baskets
    assert set(items.product_id) <= set(products.product_id)
    assert (items.quantity > 0).all()
    expected = (items.quantity * items.unit_price * (1 - items.discount_pct / 100)).round(2)
    assert np.allclose(items.line_revenue, expected)
    assert (products.unit_cost < products.unit_price).all()


def test_generation_is_reproducible():
    kwargs = dict(start="2024-01-01", end="2024-01-14", base_baskets=10, seed=7)
    a, b = generate_data.generate(**kwargs), generate_data.generate(**kwargs)
    pd.testing.assert_frame_equal(a["transaction_items"], b["transaction_items"])


def test_discounts_only_inside_promotions(data):
    items = data["transaction_items"].merge(data["transactions"], on="transaction_id")
    promoted = items[items.discount_pct > 0]
    assert len(promoted) > 0
    for row in promoted.sample(50, random_state=0).itertuples():
        match = data["promotions"].query(
            "product_id == @row.product_id and start_date <= @row.transaction_date <= end_date")
        assert len(match) == 1 and match.discount_pct.iloc[0] == row.discount_pct


def test_association_rules_on_known_example():
    # 4 baskets: bread+butter together in 2, bread in 3, butter in 2, milk in 2
    baskets = pd.DataFrame({
        "transaction_id": [1, 1, 2, 2, 3, 3, 4],
        "item": ["bread", "butter", "bread", "butter", "bread", "milk", "milk"],
    })
    rules = basket_analysis.association_rules(baskets, min_support=0, min_confidence=0, min_lift=0)
    r = rules.set_index(["antecedent", "consequent"]).loc[("butter", "bread")]
    assert r.support == pytest.approx(2 / 4)
    assert r.confidence == pytest.approx(1.0)            # every butter basket has bread
    assert r.lift == pytest.approx(1.0 / (3 / 4))


def test_wape():
    assert forecasting.wape([10, 10], [8, 13]) == pytest.approx(5 / 20)


def test_forecast_features_never_use_recent_data(data):
    sales = (data["transaction_items"].merge(data["transactions"], on="transaction_id")
             .groupby(["transaction_date", "store_id", "product_id"], as_index=False)
             .quantity.sum()
             .rename(columns={"transaction_date": "date", "quantity": "units"}))
    panel = forecasting.build_panel(sales, data["products"], data["promotions"])
    one = panel[(panel.store_id == "S01") & (panel.product_id == "P001")].set_index("date")
    day = one.index[40]
    assert one.at[day, "lag_7"] == one.at[day - pd.Timedelta(days=7), "units"]
    window = one.loc[day - pd.Timedelta(days=13):day - pd.Timedelta(days=7), "units"]
    assert one.at[day, "roll_mean_7"] == pytest.approx(window.mean())
    # future rows exist, have features, and have no target
    future = panel[panel.date > sales.date.max()]
    assert future.date.nunique() == forecasting.H and future.units.isna().all()
    assert future[forecasting.FEATURES].notna().all().all()


def test_inventory_policy():
    p = inventory.plan(daily_demand=[10, 10, 10], sigma=[2, 2, 2], lead_time=[2, 2, 2],
                       stock_on_hand=[5, 60, 500], z=1.645, review=7)
    assert list(p.status) == ["Reorder now", "Healthy", "Overstocked"]
    assert p.reorder_point[0] == np.ceil(10 * 2 + 1.645 * 2 * np.sqrt(2))
    assert p.order_up_to_level[0] == np.ceil(10 * 9 + 1.645 * 2 * 3)
    assert p.recommended_order_qty[0] == p.order_up_to_level[0] - 5
    assert p.recommended_order_qty[1] == 0 and p.recommended_order_qty[2] == 0


def test_promotion_uplift_on_known_example():
    dates = pd.date_range("2024-01-01", periods=35)
    units = np.r_[np.full(28, 10.0), np.full(7, 30.0)]           # 3x units in promo week
    daily = pd.DataFrame({"units": units,
                          "revenue": units * np.r_[np.full(28, 2.0), np.full(7, 1.5)],
                          "cost": units * 1.0},
                         index=pd.MultiIndex.from_product([["P1"], dates],
                                                          names=["product_id", "date"]))
    promos = pd.DataFrame({"promo_id": ["PR1"], "product_id": ["P1"],
                           "start_date": [dates[28]], "end_date": [dates[34]],
                           "discount_pct": [25.0]})
    products = pd.DataFrame({"product_id": ["P1"], "product_name": ["Test"], "category": ["C"],
                             "unit_price": [2.0], "unit_cost": [1.0]})
    r = promotions.promotion_uplift(daily, promos, products).iloc[0]
    assert r.unit_uplift_pct == pytest.approx(200.0)
    assert r.incremental_units == 140
    assert r.incremental_revenue == pytest.approx(30 * 7 * 1.5 - 10 * 7 * 2.0)
    assert r.incremental_profit == pytest.approx(30 * 7 * 0.5 - 10 * 7 * 1.0)
