"""Your Lab 3 churn model, packaged for the Lab 4 pipeline.

YOU WRITE THIS FILE. The pipeline's training job runs train_sagemaker.py
(beside this file; do not edit it), which imports this module and calls
train(). Everything the job needs from you goes through the three names below.

Contract (train_sagemaker.py checks it in the first seconds of the job):

    FEATURE_COLUMNS   list[str]   model input columns, in order
    LABEL             str         "churn_label"
    train(df, seed=42) -> (xgboost.Booster, dict)

`df` is the full labeled feature table: every column of your Lab 2 output,
including `loyalty_tier` for slice evaluation. It is already loaded. Do not
query Athena or the Feature Store from here; the training container stages
the data for you and has no business making service calls for its input.

The metrics dict must include the four numbers the CI gate in
tests/test_model.py reads. Your Lab 3 evaluate_model() already returns them:

    precision_top10, recall_top10      gated at 0.50 / 0.25
    lift_ci_low, lift_ci_high          bootstrap 95% CI on AUC lift over the
                                       recency-only baseline; lift_ci_low > 0

Include anything else you reported in Lab 3 (auc_roc, baseline_auc,
positive_rate_val, slice results). It is all written to evaluation_metrics.json
and attached to the registered model.

What runs in the container: the SageMaker XGBoost 1.7-1 image ships pandas,
numpy, scikit-learn, xgboost and boto3. It does NOT ship mlflow or sagemaker,
so do not import them at the top of this file. MLflow tracking stays in your
Lab 3 script.

Only this directory (models/churn/) is uploaded to the training job, so the
code must live here. `import churn_training_skeleton` will fail inside the
container even though it works on your laptop. Copy the functions you need.

Test it locally before pushing:

    python models/churn/train_sagemaker.py \
        --train-channel <dir containing your features CSV or Parquet> \
        --model-dir /tmp/model --output-data-dir /tmp/out
"""

# Keeps Lab 3 annotations like `-> tuple[np.ndarray, np.ndarray]` from being
# evaluated, whatever Python the training container runs.
from __future__ import annotations

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

# Must match the columns your Lab 3 model was trained on, in the same order.
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

LABEL = "churn_label"
SLICE_COLUMN = "loyalty_tier"
BASELINE_FEATURE = "days_since_last_purchase"
BOOTSTRAP_N = 2000
EVAL_THRESHOLDS = {"precision_top10": 0.50, "recall_top10": 0.25}


def _train_candidate(X_train, y_train, X_val, y_val, seed):
    """Train the full Lab 3 XGBoost model with its established defaults."""
    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=FEATURE_COLUMNS)
    dval = xgb.DMatrix(X_val, label=y_val, feature_names=FEATURE_COLUMNS)
    scale_pos_weight = float((y_train == 0).sum() / max((y_train == 1).sum(), 1))
    params = {
        # XGBoost early-stops on the final metric in this list, so keep AUC last.
        "objective": "binary:logistic",
        "eval_metric": ["logloss", "auc"],
        "max_depth": 6,
        "eta": 0.1,
        "min_child_weight": 5,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "scale_pos_weight": scale_pos_weight,
        "seed": seed,
        "verbosity": 1,
    }
    return xgb.train(
        params=params,
        dtrain=dtrain,
        num_boost_round=200,
        evals=[(dtrain, "train"), (dval, "validation")],
        early_stopping_rounds=20,
        verbose_eval=25,
    )


def _train_recency_baseline(X_train, y_train, X_val, seed):
    """Train the comparison model using only days_since_last_purchase."""
    feature_index = FEATURE_COLUMNS.index(BASELINE_FEATURE)
    dtrain = xgb.DMatrix(
        X_train[:, [feature_index]], label=y_train, feature_names=[BASELINE_FEATURE]
    )
    dval = xgb.DMatrix(
        X_val[:, [feature_index]], feature_names=[BASELINE_FEATURE]
    )
    scale_pos_weight = float((y_train == 0).sum() / max((y_train == 1).sum(), 1))
    params = {
        "objective": "binary:logistic",
        "eval_metric": "auc",
        "max_depth": 4,
        "eta": 0.1,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "scale_pos_weight": scale_pos_weight,
        "seed": seed,
    }
    baseline = xgb.train(params, dtrain, num_boost_round=200)
    return baseline.predict(dval)


def _bootstrap_lift_ci(y_true, candidate_scores, baseline_scores, seed, n=BOOTSTRAP_N):
    """Paired bootstrap 95% interval for candidate AUC minus baseline AUC."""
    rng = np.random.default_rng(seed)
    y_true = np.asarray(y_true)
    indices = np.arange(len(y_true))
    differences = []
    for _ in range(n):
        sample = rng.choice(indices, size=len(indices), replace=True)
        sampled_labels = y_true[sample]
        if np.unique(sampled_labels).size < 2:
            continue
        differences.append(
            roc_auc_score(sampled_labels, candidate_scores[sample])
            - roc_auc_score(sampled_labels, baseline_scores[sample])
        )
    if len(differences) < n // 2:
        raise ValueError(
            "Too few usable bootstrap samples for the AUC-lift confidence interval; "
            "the validation set may be too small or imbalanced."
        )
    differences = np.sort(differences)
    return float(np.quantile(differences, 0.025)), float(np.quantile(differences, 0.975))


def _evaluate_candidate(model, X_val, y_val, baseline_scores, seed):
    """Compute Lab 3 quality metrics and fail training when a promotion gate misses."""
    dval = xgb.DMatrix(X_val, feature_names=FEATURE_COLUMNS)
    candidate_scores = model.predict(dval)
    auc_roc = float(roc_auc_score(y_val, candidate_scores))

    top10_threshold = np.percentile(candidate_scores, 90)
    top10_mask = candidate_scores >= top10_threshold
    precision_top10 = float(y_val[top10_mask].mean()) if top10_mask.any() else 0.0
    positive_count = int(y_val.sum())
    recall_top10 = (
        float(y_val[top10_mask].sum() / positive_count) if positive_count else 0.0
    )
    baseline_auc = float(roc_auc_score(y_val, baseline_scores))
    lift_ci_low, lift_ci_high = _bootstrap_lift_ci(
        y_val, candidate_scores, baseline_scores, seed=seed
    )

    # Keep the handout's canonical names and the aliases read by existing gates.
    metrics = {
        "auc_roc": round(auc_roc, 4),
        "baseline_auc_roc": round(baseline_auc, 4),
        "baseline_auc": round(baseline_auc, 4),
        "auc_lift_over_baseline": round(auc_roc - baseline_auc, 4),
        "auc_vs_baseline": round(auc_roc - baseline_auc, 4),
        "auc_lift_ci_low": round(lift_ci_low, 4),
        "auc_lift_ci_high": round(lift_ci_high, 4),
        "lift_ci_low": round(lift_ci_low, 4),
        "lift_ci_high": round(lift_ci_high, 4),
        "precision_top10": round(precision_top10, 4),
        "recall_top10": round(recall_top10, 4),
        "positive_rate_val": round(float(y_val.mean()), 4),
        "n_val_samples": int(len(y_val)),
    }

    failures = [
        f"{name}={metrics[name]:.4f} < {threshold:.2f}"
        for name, threshold in EVAL_THRESHOLDS.items()
        if metrics[name] < threshold
    ]
    if lift_ci_low <= 0:
        failures.append(
            f"AUC-lift 95% CI [{lift_ci_low:.4f}, {lift_ci_high:.4f}] includes zero"
        )
    if failures:
        raise ValueError(
            "Model failed evaluation gates: " + "; ".join(failures) + ". "
            "Training fails here so an unqualified model is not registered."
        )
    return metrics


def _evaluate_slices(model, X_val, y_val, tiers):
    """Report held-out recall at the global top-10% cutoff for each tier."""
    dval = xgb.DMatrix(X_val, feature_names=FEATURE_COLUMNS)
    scores = model.predict(dval)
    top10_mask = scores >= np.percentile(scores, 90)
    aggregate_recall = (
        float(y_val[top10_mask].sum() / y_val.sum()) if y_val.sum() else float("nan")
    )

    slice_results = {}
    tier_values = np.asarray(tiers, dtype=object)
    for tier in pd.unique(tier_values):
        mask = pd.isna(tier_values) if pd.isna(tier) else tier_values == tier
        tier_labels = y_val[mask]
        positives = int(tier_labels.sum())
        negatives = int(len(tier_labels) - positives)
        recall = (
            float(y_val[mask & top10_mask].sum() / positives)
            if positives else float("nan")
        )
        tier_auc = (
            float(roc_auc_score(y_val[mask], scores[mask]))
            if positives > 0 and negatives > 0 else float("nan")
        )
        key = "Unknown" if pd.isna(tier) else str(tier)
        slice_results[key] = {
            "tier": key,
            "n": int(mask.sum()),
            "positives": positives,
            "auc": tier_auc,
            "recall_top10": recall,
            "too_small": bool(positives < 20 or negatives < 20),
            "below_aggregate": bool(
                np.isfinite(recall)
                and np.isfinite(aggregate_recall)
                and recall < aggregate_recall - 0.10
            ),
        }
    return slice_results


def train(df: pd.DataFrame, seed: int = 42):
    """Train the churn model on `df` and return (booster, metrics).

    It validates and prepares the staged feature rows, splits features, labels,
    and loyalty tiers together, trains the full model and recency-only baseline,
    then applies the Lab 3 evaluation gates. The input data is already staged by
    train_sagemaker.py; this function makes no AWS calls and loads no files.
    """
    required = FEATURE_COLUMNS + [LABEL, SLICE_COLUMN]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Training DataFrame is missing required columns: {missing}")

    labeled = df.dropna(subset=[LABEL]).reset_index(drop=True)
    if labeled.empty:
        raise ValueError("Training DataFrame has no rows with a non-null churn label")
    labels = labeled[LABEL].to_numpy(dtype=int)
    if not set(np.unique(labels)).issubset({0, 1}):
        raise ValueError("churn_label must contain only binary values 0 and 1")

    feature_frame = labeled[FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    X = feature_frame.fillna(-1).to_numpy(dtype=float)
    tiers = labeled[SLICE_COLUMN].astype("object").to_numpy()

    X_train, X_val, y_train, y_val, _, tiers_val = train_test_split(
        X,
        labels,
        tiers,
        test_size=0.30,
        random_state=seed,
        stratify=labels,
    )
    model = _train_candidate(X_train, y_train, X_val, y_val, seed)
    baseline_scores = _train_recency_baseline(X_train, y_train, X_val, seed)
    metrics = _evaluate_candidate(model, X_val, y_val, baseline_scores, seed)
    metrics["slice_results"] = _evaluate_slices(model, X_val, y_val, tiers_val)
    return model, metrics
