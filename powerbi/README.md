# Power BI dashboard guide

The pipeline exports a ready-to-load **star schema** to `powerbi/data/`. This guide
takes you from those files to a four-page dashboard in about 30 minutes.

> The `.pbix` file itself is not in the repository: it has to be built in Power BI
> Desktop (Windows). After you build it, save it here as
> `powerbi/SmartRetailAnalytics.pbix` and add screenshots to `powerbi/screenshots/`.

## 1. Load the data

*Get data → Folder →* select `powerbi/data` *→ Transform data*, or load each CSV
with *Get data → Text/CSV*.

| Table | Grain | Rows |
| --- | --- | --- |
| `dim_date` | one row per day (history + 7 forecast days) | ~740 |
| `dim_product` | one row per product | 73 |
| `dim_store` | one row per store | 3 |
| `fact_sales` | store x product x day | ~160k |
| `fact_baskets` | store x day (number of baskets) | ~2.2k |
| `fact_forecast` | store x product x day (8 hold-out weeks + next 7 days) | ~14k |
| `fact_inventory_plan` | store x product | 219 |
| `fact_promotions` | one row per promotion | 161 |
| `basket_rules` | one row per rule A → B | 50 |

Set `dim_date[date]` and every fact `date` column to type **Date**, then
*Table tools → Mark as date table* on `dim_date`.

## 2. Model (relationships)

All relationships are one-to-many, single direction, from dimension to fact.

```
dim_date[date]          1 ──── *  fact_sales[date]
dim_date[date]          1 ──── *  fact_baskets[date]
dim_date[date]          1 ──── *  fact_forecast[date]
dim_product[product_id] 1 ──── *  fact_sales[product_id]
dim_product[product_id] 1 ──── *  fact_forecast[product_id]
dim_product[product_id] 1 ──── *  fact_inventory_plan[product_id]
dim_product[product_id] 1 ──── *  fact_promotions[product_id]
dim_store[store_id]     1 ──── *  fact_sales[store_id]
dim_store[store_id]     1 ──── *  fact_baskets[store_id]
dim_store[store_id]     1 ──── *  fact_forecast[store_id]
dim_store[store_id]     1 ──── *  fact_inventory_plan[store_id]
```

`basket_rules` stays disconnected (it is already aggregated).

Sort `dim_date[month]` by `month_num` and `dim_date[weekday]` by `weekday_num`
(*Column tools → Sort by column*).

## 3. DAX measures

Create a blank table called `_Measures` and add:

```DAX
-- Sales
Revenue          = SUM ( fact_sales[revenue] )
Units Sold       = SUM ( fact_sales[units] )
Gross Profit     = SUM ( fact_sales[gross_profit] )
Gross Margin %   = DIVIDE ( [Gross Profit], [Revenue] )
Baskets          = SUM ( fact_baskets[baskets] )
Avg Basket Value = DIVIDE ( [Revenue], [Baskets] )

-- Time intelligence
Revenue LY       = CALCULATE ( [Revenue], SAMEPERIODLASTYEAR ( dim_date[date] ) )
Revenue YoY %    = DIVIDE ( [Revenue] - [Revenue LY], [Revenue LY] )
Revenue YTD      = TOTALYTD ( [Revenue], dim_date[date] )
Revenue 7d Avg   =
    AVERAGEX (
        DATESINPERIOD ( dim_date[date], MAX ( dim_date[date] ), -7, DAY ),
        [Revenue]
    )

-- Product ranking / Pareto
Revenue Share %  = DIVIDE ( [Revenue], CALCULATE ( [Revenue], ALLSELECTED ( dim_product ) ) )
Product Rank     = RANKX ( ALLSELECTED ( dim_product[product_name] ), [Revenue],, DESC )
Cumulative Revenue % =
    VAR CurrentRevenue = [Revenue]
    RETURN
        DIVIDE (
            SUMX (
                FILTER (
                    ALLSELECTED ( dim_product[product_name] ),
                    [Revenue] >= CurrentRevenue
                ),
                [Revenue]
            ),
            CALCULATE ( [Revenue], ALLSELECTED ( dim_product[product_name] ) )
        )

-- Seasonality
Seasonal Index =
    DIVIDE (
        AVERAGEX ( VALUES ( dim_date[date] ), [Revenue] ),
        CALCULATE (
            AVERAGEX ( VALUES ( dim_date[date] ), [Revenue] ),
            ALL ( dim_date )
        )
    ) * 100

-- Promotions
Promo Revenue          = CALCULATE ( [Revenue], fact_sales[on_promo] = TRUE () )
Promo Revenue Share %  = DIVIDE ( [Promo Revenue], [Revenue] )
Avg Unit Uplift %      = AVERAGE ( fact_promotions[unit_uplift_pct] ) / 100
Incremental Revenue    = SUM ( fact_promotions[incremental_revenue] )
Incremental Profit     = SUM ( fact_promotions[incremental_profit] )
Profitable Promos %    =
    DIVIDE (
        COUNTROWS ( FILTER ( fact_promotions, fact_promotions[incremental_profit] > 0 ) ),
        COUNTROWS ( fact_promotions )
    )

-- Forecast
Forecast Units  = SUM ( fact_forecast[forecast] )
Actual Units    = CALCULATE ( SUM ( fact_forecast[actual_units] ),
                              fact_forecast[period] = "Hold-out (evaluation)" )
Forecast WAPE % =
    VAR Detail =
        FILTER ( fact_forecast, fact_forecast[period] = "Hold-out (evaluation)" )
    RETURN
        DIVIDE (
            SUMX ( Detail, ABS ( fact_forecast[actual_units] - fact_forecast[forecast] ) ),
            SUMX ( Detail, fact_forecast[actual_units] )
        )

-- Inventory
Stock On Hand        = SUM ( fact_inventory_plan[stock_on_hand] )
Items To Reorder     = CALCULATE ( COUNTROWS ( fact_inventory_plan ),
                                   fact_inventory_plan[status] = "Reorder now" )
Items Overstocked    = CALCULATE ( COUNTROWS ( fact_inventory_plan ),
                                   fact_inventory_plan[status] = "Overstocked" )
Recommended Order €  = SUM ( fact_inventory_plan[order_value_eur] )
Excess Stock €       = SUM ( fact_inventory_plan[excess_stock_value_eur] )
```

Format the `%` measures as percentage and the money measures as currency (€).

## 4. Report pages

Put **slicers for year, store and category on every page** (sync them with
*View → Sync slicers*).

**Page 1 - Executive overview**
- Cards: Revenue, Revenue YoY %, Gross Margin %, Baskets, Avg Basket Value
- Line chart: Revenue by `year_month`, with Revenue LY as a second line
- Bar chart: Revenue by `category`
- Bar chart: top 10 `product_name` by Revenue (visual-level Top N filter)

**Page 2 - Products & baskets**
- Table: product, Revenue, Gross Margin %, Product Rank, Cumulative Revenue %
- Scatter: Units Sold (x) vs. Gross Margin % (y), bubble size Revenue, per product
- Table from `basket_rules`: antecedent, consequent, support, confidence, lift,
  sorted by lift, with data bars on lift

**Page 3 - Seasonality & promotions**
- Matrix: `category` x `month`, values Seasonal Index, conditional formatting
  diverging around 100
- Column chart: Revenue by `weekday`
- Column chart: Avg Unit Uplift % by `discount_pct`
- Bar chart: Incremental Profit by `category` (colour negative values differently)
- Cards: Promo Revenue Share %, Profitable Promos %

**Page 4 - Forecast & inventory**
- Line chart: Actual Units and Forecast Units by date
- Card: Forecast WAPE %
- Cards: Items To Reorder, Recommended Order €, Excess Stock €
- Table from `fact_inventory_plan`: store, product, stock on hand, days of cover,
  reorder point, recommended order qty, status - with conditional formatting on
  `status` (add an icon as well as a colour so it also reads in greyscale)

## 5. Refresh

Re-run `python -m retail_analytics.pipeline`, then press **Refresh** in Power BI.
