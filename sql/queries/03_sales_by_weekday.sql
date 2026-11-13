-- Q3a. Which days of the week have the highest sales?
-- Averages per calendar day so that weekdays are compared fairly.
WITH daily AS (
    SELECT
        transaction_date,
        CAST(STRFTIME('%w', transaction_date) AS INTEGER) AS weekday_num,  -- 0 = Sunday
        COUNT(DISTINCT transaction_id) AS baskets,
        SUM(revenue)                   AS revenue
    FROM v_sales
    GROUP BY transaction_date
)
SELECT
    CASE weekday_num
        WHEN 1 THEN 'Monday' WHEN 2 THEN 'Tuesday' WHEN 3 THEN 'Wednesday'
        WHEN 4 THEN 'Thursday' WHEN 5 THEN 'Friday' WHEN 6 THEN 'Saturday'
        ELSE 'Sunday'
    END                                         AS weekday,
    (weekday_num + 6) % 7                       AS weekday_order,          -- Monday first
    ROUND(AVG(revenue), 2)                      AS avg_daily_revenue,
    ROUND(AVG(baskets), 1)                      AS avg_daily_baskets,
    ROUND(SUM(revenue) / SUM(baskets), 2)       AS avg_basket_value,
    ROUND(100.0 * AVG(revenue) / (SELECT AVG(revenue) FROM daily), 1) AS index_vs_avg_day
FROM daily
GROUP BY weekday_num
ORDER BY weekday_order;
