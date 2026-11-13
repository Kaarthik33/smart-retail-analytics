-- Smart Retail Analytics: relational schema (SQLite dialect, portable to PostgreSQL)

DROP VIEW IF EXISTS v_sales;
DROP TABLE IF EXISTS transaction_items;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS promotions;
DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS stores;

CREATE TABLE stores (
    store_id    TEXT PRIMARY KEY,
    store_name  TEXT NOT NULL,
    store_type  TEXT NOT NULL
);

CREATE TABLE products (
    product_id      TEXT PRIMARY KEY,
    product_name    TEXT NOT NULL,
    category        TEXT NOT NULL,
    unit_price      REAL NOT NULL CHECK (unit_price > 0),
    unit_cost       REAL NOT NULL CHECK (unit_cost > 0),
    lead_time_days  INTEGER NOT NULL
);

CREATE TABLE promotions (
    promo_id      TEXT PRIMARY KEY,
    product_id    TEXT NOT NULL REFERENCES products (product_id),
    start_date    TEXT NOT NULL,
    end_date      TEXT NOT NULL,
    discount_pct  REAL NOT NULL CHECK (discount_pct BETWEEN 0 AND 100)
);

CREATE TABLE transactions (
    transaction_id    INTEGER PRIMARY KEY,
    store_id          TEXT NOT NULL REFERENCES stores (store_id),
    transaction_ts    TEXT NOT NULL,
    transaction_date  TEXT NOT NULL
);

CREATE TABLE transaction_items (
    transaction_id  INTEGER NOT NULL REFERENCES transactions (transaction_id),
    product_id      TEXT NOT NULL REFERENCES products (product_id),
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    unit_price      REAL NOT NULL,
    discount_pct    REAL NOT NULL DEFAULT 0,
    line_revenue    REAL NOT NULL,
    PRIMARY KEY (transaction_id, product_id)
);

CREATE TABLE inventory (
    snapshot_date  TEXT NOT NULL,
    store_id       TEXT NOT NULL REFERENCES stores (store_id),
    product_id     TEXT NOT NULL REFERENCES products (product_id),
    stock_on_hand  INTEGER NOT NULL,
    PRIMARY KEY (snapshot_date, store_id, product_id)
);

CREATE INDEX idx_transactions_date  ON transactions (transaction_date);
CREATE INDEX idx_transactions_store ON transactions (store_id);
CREATE INDEX idx_items_product      ON transaction_items (product_id);

-- One row per line item with everything an analyst usually needs.
CREATE VIEW v_sales AS
SELECT
    t.transaction_id,
    t.transaction_date,
    t.transaction_ts,
    t.store_id,
    s.store_name,
    i.product_id,
    p.product_name,
    p.category,
    i.quantity,
    i.unit_price,
    i.discount_pct,
    i.line_revenue                              AS revenue,
    i.quantity * p.unit_cost                    AS cost,
    i.line_revenue - i.quantity * p.unit_cost   AS gross_profit,
    CASE WHEN i.discount_pct > 0 THEN 1 ELSE 0 END AS on_promo
FROM transaction_items AS i
JOIN transactions AS t ON t.transaction_id = i.transaction_id
JOIN products     AS p ON p.product_id = i.product_id
JOIN stores       AS s ON s.store_id = t.store_id;
