-- Q3b. Which months and seasons have the highest sales? Includes year-over-year growth.
WITH monthly AS (
    SELECT
        STRFTIME('%Y-%m', transaction_date)             AS year_month,
        CAST(STRFTIME('%Y', transaction_date) AS INTEGER) AS year,
        CAST(STRFTIME('%m', transaction_date) AS INTEGER) AS month,
        COUNT(DISTINCT transaction_id)                  AS baskets,
        SUM(revenue)                                    AS revenue
    FROM v_sales
    GROUP BY year_month
)
SELECT
    year_month,
    year,
    month,
    CASE
        WHEN month IN (12, 1, 2) THEN 'Winter'
        WHEN month IN (3, 4, 5)  THEN 'Spring'
        WHEN month IN (6, 7, 8)  THEN 'Summer'
        ELSE 'Autumn'
    END                                             AS season,
    baskets,
    ROUND(revenue, 2)                               AS revenue,
    ROUND(100.0 * (revenue / LAG(revenue, 12) OVER (ORDER BY year_month) - 1), 1) AS yoy_growth_pct
FROM monthly
ORDER BY year_month;
