"""Pandas feature calculations matching the Lab 2 churn feature definitions.

These functions provide a small, testable implementation of the feature
definitions in ``glue-scripts/feature_engineer.py``. All time windows are
anchored to ``snapshot_date`` and exclude transactions after that date.
"""

from __future__ import annotations

import pandas as pd


N_CATEGORIES = 8.0
NO_PURCHASE_RECENCY_DAYS = 999

FEATURE_COLUMNS = [
    "days_since_last_purchase",
    "customer_tenure_days",
    "purchase_frequency_30d",
    "purchase_frequency_90d",
    "purchase_frequency_180d",
    "avg_order_value",
    "total_spend_90d",
    "total_lifetime_value",
    "avg_basket_size_6m",
    "category_diversity_score",
    "online_to_store_ratio",
]


def _history(transactions: pd.DataFrame, snapshot_date) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Return valid transaction rows through the inclusive snapshot date."""
    required = {"customer_id", "purchase_date"}
    missing = required.difference(transactions.columns)
    if missing:
        raise ValueError(f"transactions missing required columns: {sorted(missing)}")

    cutoff = pd.Timestamp(snapshot_date)
    if cutoff.tz is not None:
        cutoff = cutoff.tz_localize(None)

    history = transactions.copy()
    history["purchase_date"] = pd.to_datetime(history["purchase_date"], errors="coerce")
    if getattr(history["purchase_date"].dt, "tz", None) is not None:
        history["purchase_date"] = history["purchase_date"].dt.tz_localize(None)
    history = history.dropna(subset=["customer_id", "purchase_date"])
    history = history.loc[history["purchase_date"] <= cutoff].copy()
    return history, cutoff


def _customer_ids(
    transactions: pd.DataFrame,
    customers: pd.DataFrame | None = None,
) -> list:
    """Collect customer IDs in stable order from an optional roster and data."""
    ids = []
    if customers is not None:
        if "customer_id" not in customers.columns:
            raise ValueError("customers missing required column: customer_id")
        ids.extend(customers["customer_id"].dropna().tolist())
    if "customer_id" in transactions.columns:
        ids.extend(transactions["customer_id"].dropna().tolist())
    return list(dict.fromkeys(ids))


def compute_recency_features(
    transactions: pd.DataFrame,
    snapshot_date,
    customers: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Calculate days since last purchase and customer tenure.

    ``customers`` may be supplied as a roster containing ``customer_id`` so
    that customers without eligible transactions are included. Their recency
    is the documented 999-day sentinel and their tenure is zero.
    """
    history, cutoff = _history(transactions, snapshot_date)
    ids = _customer_ids(history, customers)
    result = pd.DataFrame({"customer_id": ids})
    if result.empty:
        result["days_since_last_purchase"] = pd.Series(dtype="int64")
        result["customer_tenure_days"] = pd.Series(dtype="int64")
        return result

    if history.empty:
        result["days_since_last_purchase"] = NO_PURCHASE_RECENCY_DAYS
        result["customer_tenure_days"] = 0
        return result

    dates = history.groupby("customer_id")["purchase_date"].agg(first="min", last="max")
    result = result.join(dates, on="customer_id")
    result["days_since_last_purchase"] = (cutoff - result["last"]).dt.days
    result["customer_tenure_days"] = (cutoff - result["first"]).dt.days
    result["days_since_last_purchase"] = result["days_since_last_purchase"].fillna(
        NO_PURCHASE_RECENCY_DAYS
    )
    result["customer_tenure_days"] = result["customer_tenure_days"].fillna(0)
    return result.drop(columns=["first", "last"])


def compute_frequency_features(
    transactions: pd.DataFrame,
    snapshot_date,
) -> pd.DataFrame:
    """Count transactions in the inclusive rolling 30-, 90-, and 180-day windows."""
    history, cutoff = _history(transactions, snapshot_date)
    ids = _customer_ids(history)
    result = pd.DataFrame({"customer_id": ids})
    for days in (30, 90, 180):
        start = cutoff - pd.Timedelta(days=days)
        counts = history.loc[history["purchase_date"] >= start].groupby("customer_id").size()
        result[f"purchase_frequency_{days}d"] = (
            result["customer_id"].map(counts).fillna(0).astype("int64")
        )
    return result


def compute_monetary_features(
    transactions: pd.DataFrame,
    snapshot_date,
) -> pd.DataFrame:
    """Calculate order value, spend, lifetime value, and 180-day basket size."""
    history, cutoff = _history(transactions, snapshot_date)
    ids = _customer_ids(history)
    result = pd.DataFrame({"customer_id": ids})
    names = [
        "avg_order_value",
        "total_spend_90d",
        "total_lifetime_value",
        "avg_basket_size_6m",
    ]
    if result.empty:
        for name in names:
            result[name] = pd.Series(dtype="float64")
        return result

    if "order_value" not in history.columns:
        raise ValueError("transactions missing required column: order_value")
    history["order_value"] = pd.to_numeric(history["order_value"], errors="coerce").fillna(0.0)
    grouped = history.groupby("customer_id")

    order_value = grouped["order_value"].agg(
        avg_order_value="mean",
        total_lifetime_value="sum",
    )
    recent_90 = history.loc[
        history["purchase_date"] >= cutoff - pd.Timedelta(days=90)
    ]
    spend_90 = recent_90.groupby("customer_id")["order_value"].sum().rename("total_spend_90d")

    if "num_items" in history.columns:
        history["num_items"] = pd.to_numeric(history["num_items"], errors="coerce").fillna(0.0)
        recent_180 = history.loc[
            history["purchase_date"] >= cutoff - pd.Timedelta(days=180)
        ]
        items = recent_180.groupby("customer_id")["num_items"].sum()
        orders = recent_180.groupby("customer_id").size()
        basket_size = items.div(orders.where(orders != 0)).fillna(0.0)
        basket_size.name = "avg_basket_size_6m"
    else:
        basket_size = pd.Series(0.0, index=order_value.index, name="avg_basket_size_6m")

    result = result.join(order_value, on="customer_id")
    result = result.join(spend_90, on="customer_id")
    result = result.join(basket_size, on="customer_id")
    return result.fillna(0.0)


def compute_behavioral_features(transactions: pd.DataFrame) -> pd.DataFrame:
    """Calculate category diversity and the share of orders placed online."""
    if "customer_id" not in transactions.columns:
        raise ValueError("transactions missing required column: customer_id")

    ids = transactions["customer_id"].dropna().drop_duplicates().tolist()
    result = pd.DataFrame({"customer_id": ids})
    if result.empty:
        result["category_diversity_score"] = pd.Series(dtype="float64")
        result["online_to_store_ratio"] = pd.Series(dtype="float64")
        return result

    if "product_category" in transactions.columns:
        categories = transactions.loc[
            transactions["product_category"].notna()
            & transactions["product_category"].astype(str).str.lower().ne("unknown")
        ].groupby("customer_id")["product_category"].nunique()
        diversity = (categories / N_CATEGORIES).rename("category_diversity_score")
    else:
        diversity = pd.Series(dtype="float64", name="category_diversity_score")

    if "channel" in transactions.columns:
        online_share = (
            transactions.assign(_is_online=transactions["channel"].eq("online").astype(float))
            .groupby("customer_id")["_is_online"]
            .mean()
            .rename("online_to_store_ratio")
        )
    else:
        online_share = pd.Series(dtype="float64", name="online_to_store_ratio")

    result = result.join(diversity, on="customer_id").join(online_share, on="customer_id")
    return result.fillna(0.0)


def build_churn_feature_set(
    customers: pd.DataFrame,
    transactions: pd.DataFrame,
    snapshot_date,
) -> pd.DataFrame:
    """Build a customer-grain feature table and retain roster metadata.

    Existing customer columns such as ``loyalty_tier`` and ``churn_label`` are
    carried through. The label is never recomputed from purchase recency.
    """
    if "customer_id" not in customers.columns:
        raise ValueError("customers missing required column: customer_id")

    roster = customers.drop_duplicates(subset=["customer_id"]).copy()
    history, cutoff = _history(transactions, snapshot_date)
    feature_frames = [
        compute_recency_features(history, cutoff, roster[["customer_id"]]),
        compute_frequency_features(history, cutoff),
        compute_monetary_features(history, cutoff),
        compute_behavioral_features(history),
    ]

    features = roster
    for frame in feature_frames:
        features = features.merge(frame, on="customer_id", how="left", validate="one_to_one")

    # A roster member with no purchase history retains the recency sentinel;
    # count, amount, basket, and behavioral values use zero as their neutral value.
    features["days_since_last_purchase"] = features["days_since_last_purchase"].fillna(
        NO_PURCHASE_RECENCY_DAYS
    )
    for column in FEATURE_COLUMNS:
        features[column] = pd.to_numeric(features[column], errors="coerce").fillna(0.0)
    return features
