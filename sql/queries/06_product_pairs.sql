-- Q2. Which products are frequently purchased together?
-- Pure-SQL co-occurrence count with support, confidence and lift.
-- (The Python module basket_analysis.py computes the same metrics for all rules.)
WITH basket_count AS (
    SELECT COUNT(*) AS n FROM transactions
),
item_count AS (
    SELECT product_id, COUNT(*) AS baskets
    FROM transaction_items
    GROUP BY product_id
),
pair_count AS (
    SELECT a.product_id AS product_a, b.product_id AS product_b, COUNT(*) AS baskets_together
    FROM transaction_items AS a
    JOIN transaction_items AS b
      ON b.transaction_id = a.transaction_id
     AND b.product_id > a.product_id
    GROUP BY a.product_id, b.product_id
)
SELECT
    pa.product_name                                         AS product_a,
    pb.product_name                                         AS product_b,
    pc.baskets_together,
    ROUND(100.0 * pc.baskets_together / bc.n, 2)            AS support_pct,
    ROUND(100.0 * pc.baskets_together / ia.baskets, 1)      AS confidence_a_to_b_pct,
    ROUND(100.0 * pc.baskets_together / ib.baskets, 1)      AS confidence_b_to_a_pct,
    ROUND(1.0 * pc.baskets_together * bc.n / (ia.baskets * ib.baskets), 2) AS lift
FROM pair_count AS pc
CROSS JOIN basket_count AS bc
JOIN item_count AS ia ON ia.product_id = pc.product_a
JOIN item_count AS ib ON ib.product_id = pc.product_b
JOIN products   AS pa ON pa.product_id = pc.product_a
JOIN products   AS pb ON pb.product_id = pc.product_b
WHERE 1.0 * pc.baskets_together / bc.n >= 0.005
ORDER BY lift DESC
LIMIT 25;
