-- Q1. Which products generate the most revenue?
-- Ranks every product and adds its share and the running (Pareto) share of revenue.
WITH product_sales AS (
    SELECT
        product_id,
        product_name,
        category,
        SUM(quantity)     AS units_sold,
        SUM(revenue)      AS revenue,
        SUM(gross_profit) AS gross_profit
    FROM v_sales
    GROUP BY product_id, product_name, category
)
SELECT
    RANK() OVER (ORDER BY revenue DESC)                         AS revenue_rank,
    product_id,
    product_name,
    category,
    units_sold,
    ROUND(revenue, 2)                                           AS revenue,
    ROUND(gross_profit, 2)                                      AS gross_profit,
    ROUND(100.0 * gross_profit / revenue, 1)                    AS margin_pct,
    ROUND(100.0 * revenue / SUM(revenue) OVER (), 2)            AS revenue_share_pct,
    ROUND(100.0 * SUM(revenue) OVER (ORDER BY revenue DESC, product_id)
          / SUM(revenue) OVER (), 2)                            AS cumulative_share_pct
FROM product_sales
ORDER BY revenue DESC;
