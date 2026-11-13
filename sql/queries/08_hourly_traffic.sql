-- When are the stores busiest? Average baskets per opening hour.
SELECT
    CAST(STRFTIME('%H', transaction_ts) AS INTEGER) AS hour_of_day,
    COUNT(*)                                        AS baskets,
    ROUND(1.0 * COUNT(*) / (SELECT COUNT(DISTINCT transaction_date) FROM transactions), 1)
                                                    AS avg_baskets_per_day,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM transactions), 1) AS share_pct
FROM transactions
GROUP BY hour_of_day
ORDER BY hour_of_day;
