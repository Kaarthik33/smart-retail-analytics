-- Store scorecard.
SELECT
    store_id,
    store_name,
    COUNT(DISTINCT transaction_id)                              AS baskets,
    ROUND(SUM(revenue), 2)                                      AS revenue,
    ROUND(SUM(revenue) / COUNT(DISTINCT transaction_id), 2)     AS avg_basket_value,
    ROUND(1.0 * SUM(quantity) / COUNT(DISTINCT transaction_id), 2) AS units_per_basket,
    ROUND(100.0 * SUM(gross_profit) / SUM(revenue), 1)          AS margin_pct
FROM v_sales
GROUP BY store_id, store_name
ORDER BY revenue DESC;
