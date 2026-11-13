"""Load the raw CSV files into a SQLite database and run SQL files against it."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from . import config

TABLES = ["stores", "products", "promotions", "transactions", "transaction_items", "inventory"]
DATE_COLUMNS = {
    "promotions": ["start_date", "end_date"],
    "transactions": ["transaction_ts", "transaction_date"],
    "inventory": ["snapshot_date"],
}


def connect(db_path: Path = config.DB_PATH) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def build_database(raw_dir: Path = config.RAW_DIR, db_path: Path = config.DB_PATH) -> None:
    """Create the schema and bulk-load every table from CSV."""
    with connect(db_path) as con:
        con.executescript((config.SQL_DIR / "schema.sql").read_text())
        for table in TABLES:
            df = pd.read_csv(raw_dir / f"{table}.csv")
            for col in DATE_COLUMNS.get(table, []):
                # ISO-8601 text sorts correctly and works with SQLite date functions
                fmt = "%Y-%m-%d %H:%M:%S" if col.endswith("_ts") else "%Y-%m-%d"
                df[col] = pd.to_datetime(df[col]).dt.strftime(fmt)
            df.to_sql(table, con, if_exists="append", index=False, chunksize=50_000)
        con.execute("ANALYZE")
    print(f"  database ready: {db_path.relative_to(config.ROOT)}")


def run_query_file(path: Path, con: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(path.read_text(), con)


def daily_sales(con: sqlite3.Connection) -> pd.DataFrame:
    """Units and revenue per store, product and day (only days with sales)."""
    return pd.read_sql_query(
        """
        SELECT transaction_date AS date, store_id, product_id,
               SUM(quantity) AS units, SUM(revenue) AS revenue, SUM(cost) AS cost
        FROM v_sales
        GROUP BY transaction_date, store_id, product_id
        """,
        con, parse_dates=["date"],
    )


if __name__ == "__main__":
    build_database()
