-- Seasonal index per category and calendar month.
-- 100 = that category's average month; 130 = 30% above its own average.
WITH cat_month AS (
    SELECT
        category,
        CAST(STRFTIME('%m', transaction_date) AS INTEGER) AS month,
        SUM(revenue) / COUNT(DISTINCT transaction_date)   AS revenue_per_day
    FROM v_sales
    GROUP BY category, month
)
SELECT
    category,
    month,
    ROUND(revenue_per_day, 2) AS revenue_per_day,
    ROUND(100.0 * revenue_per_day / AVG(revenue_per_day) OVER (PARTITION BY category), 1) AS seasonal_index
FROM cat_month
ORDER BY category, month;
