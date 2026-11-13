-- Revenue, profit and margin by category.
SELECT
    category,
    COUNT(DISTINCT product_id)                         AS products,
    SUM(quantity)                                      AS units_sold,
    ROUND(SUM(revenue), 2)                             AS revenue,
    ROUND(SUM(gross_profit), 2)                        AS gross_profit,
    ROUND(100.0 * SUM(gross_profit) / SUM(revenue), 1) AS margin_pct,
    ROUND(100.0 * SUM(revenue) / (SELECT SUM(revenue) FROM v_sales), 1) AS revenue_share_pct
FROM v_sales
GROUP BY category
ORDER BY revenue DESC;
