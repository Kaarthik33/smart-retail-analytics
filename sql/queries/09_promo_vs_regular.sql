-- Q5 (first look). Promoted vs. regular-price sales by category.
-- A proper uplift estimate against a baseline is done in promotions.py.
SELECT
    category,
    ROUND(100.0 * SUM(CASE WHEN on_promo = 1 THEN revenue END) / SUM(revenue), 1) AS promo_revenue_share_pct,
    ROUND(AVG(CASE WHEN on_promo = 1 THEN quantity END), 2)                       AS units_per_line_promo,
    ROUND(AVG(CASE WHEN on_promo = 0 THEN quantity END), 2)                       AS units_per_line_regular,
    ROUND(100.0 * SUM(CASE WHEN on_promo = 1 THEN gross_profit END)
          / SUM(CASE WHEN on_promo = 1 THEN revenue END), 1)                      AS margin_pct_promo,
    ROUND(100.0 * SUM(CASE WHEN on_promo = 0 THEN gross_profit END)
          / SUM(CASE WHEN on_promo = 0 THEN revenue END), 1)                      AS margin_pct_regular
FROM v_sales
GROUP BY category
ORDER BY promo_revenue_share_pct DESC;
