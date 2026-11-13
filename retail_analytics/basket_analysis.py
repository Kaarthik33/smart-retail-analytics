"""Market basket analysis: which products are frequently purchased together?

Pairwise association rules computed with sparse matrix algebra:

    support(A, B)      share of all baskets that contain both A and B
    confidence(A -> B) share of baskets with A that also contain B
    lift(A -> B)       confidence divided by B's overall share of baskets.
                       Lift 3 means: B is 3x more likely in a basket once A is in it.

Building the basket x product matrix X once and taking X.T @ X gives the
co-occurrence count of every product pair in a single operation, which is far
faster than enumerating itemsets for a catalog of this size.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse

from . import config, database, viz


def association_rules(baskets: pd.DataFrame, min_support: float = config.MIN_SUPPORT,
                      min_confidence: float = config.MIN_CONFIDENCE,
                      min_lift: float = config.MIN_LIFT) -> pd.DataFrame:
    """Compute pairwise rules from a long table with columns
    ``transaction_id`` and ``item``. Returns one row per directed rule A -> B."""
    tx_codes, _ = pd.factorize(baskets["transaction_id"])
    item_codes, items = pd.factorize(baskets["item"])
    n_baskets, n_items = tx_codes.max() + 1, len(items)

    x = sparse.csr_matrix((np.ones(len(baskets), dtype=np.int32), (tx_codes, item_codes)),
                          shape=(n_baskets, n_items))
    x.data[:] = 1                                   # presence, not quantity
    pair_counts = (x.T @ x).toarray()
    item_counts = pair_counts.diagonal()

    a, b = np.nonzero(pair_counts)
    keep = a != b
    a, b = a[keep], b[keep]
    together = pair_counts[a, b]

    rules = pd.DataFrame({
        "antecedent": items[a],
        "consequent": items[b],
        "baskets_together": together,
        "support": together / n_baskets,
        "confidence": together / item_counts[a],
        "lift": together * n_baskets / (item_counts[a] * item_counts[b]),
    })
    rules = rules[(rules.support >= min_support) & (rules.confidence >= min_confidence)
                  & (rules.lift >= min_lift)]
    return rules.sort_values(["lift", "confidence"], ascending=False).reset_index(drop=True)


def run() -> pd.DataFrame:
    config.ensure_dirs()
    with database.connect() as con:
        baskets = pd.read_sql_query(
            "SELECT transaction_id, product_name AS item FROM v_sales", con)
    rules = association_rules(baskets)
    out = rules.copy()
    out[["support", "confidence"]] = out[["support", "confidence"]].round(4)
    out["lift"] = out["lift"].round(2)
    out.to_csv(config.TABLES_DIR / "association_rules.csv", index=False)
    print(f"  {len(rules)} association rules from {baskets.transaction_id.nunique():,} baskets")
    _plot(rules)
    return rules


def _plot(rules: pd.DataFrame) -> None:
    # each pair appears twice (A->B and B->A); keep the direction with higher confidence
    pair_key = rules.apply(lambda r: tuple(sorted((r.antecedent, r.consequent))), axis=1)
    best = (rules.assign(pair=pair_key).sort_values("confidence", ascending=False)
            .drop_duplicates("pair").sort_values("lift", ascending=False).head(12))
    labels = [f"{r.antecedent}  →  {r.consequent}" for r in best.itertuples()]
    fig, ax = viz.new_figure(9.5, 5.2)
    viz.hbar(ax, labels, best.lift, fmt="{:.1f}x")
    viz.titled(ax, "Products most often bought together",
               "Lift: how many times more likely the second product is once the first is in the basket")
    ax.set_xlabel("Lift")
    viz.save(fig, config.FIGURES_DIR / "05_basket_rules.png")


if __name__ == "__main__":
    run()
