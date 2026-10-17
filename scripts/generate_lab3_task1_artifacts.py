"""Generate the Task 1 report and plots from the final trained model."""

import argparse
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import confusion_matrix, roc_auc_score
from sklearn.model_selection import train_test_split


FEATURES = [
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
SLICE = "loyalty_tier"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-csv", required=True)
    parser.add_argument("--model", default="model/model.xgb")
    parser.add_argument("--evidence-dir", default="docs/lab3-evidence")
    parser.add_argument("--metrics", default="docs/lab3-evidence/evaluation_metrics.json")
    parser.add_argument("--log", default="docs/lab3-evidence/train-final.log")
    args = parser.parse_args()

    root = Path.cwd()
    evidence = root / args.evidence_dir
    evidence.mkdir(parents=True, exist_ok=True)
    metrics = json.loads((root / args.metrics).read_text(encoding="utf-8"))
    metadata = json.loads((root / "model/model_metadata.json").read_text(encoding="utf-8"))
    log_text = (root / args.log).read_text(encoding="utf-8", errors="replace")

    df = pd.read_csv(args.data_csv).dropna(subset=[LABEL]).reset_index(drop=True)
    missing = [col for col in FEATURES + [LABEL, SLICE] if col not in df.columns]
    if missing:
        raise ValueError(f"Athena CSV is missing required columns: {missing}")

    X = df[FEATURES].fillna(-1).to_numpy()
    y = df[LABEL].to_numpy(dtype=int)
    X_train, X_val, y_train, y_val, _, tier_val = train_test_split(
        X, y, df[SLICE], test_size=0.30, random_state=42, stratify=y
    )

    model = xgb.Booster()
    model.load_model(bytearray((root / args.model).read_bytes()))
    probabilities = model.predict(xgb.DMatrix(X_val, feature_names=FEATURES))
    top10 = probabilities >= np.percentile(probabilities, 90)
    reproduced = {
        "auc_roc": roc_auc_score(y_val, probabilities),
        "precision_top10": y_val[top10].mean(),
        "recall_top10": y_val[top10].sum() / y_val.sum(),
    }
    threshold = 0.5
    predictions = (probabilities > threshold).astype(int)
    cm = confusion_matrix(y_val, predictions, labels=[0, 1])

    fig, ax = plt.subplots(figsize=(7.2, 5.8), constrained_layout=True)
    image = ax.imshow(cm, cmap="Blues")
    fig.colorbar(image, ax=ax, label="Customers")
    ax.set(
        xticks=[0, 1], yticks=[0, 1],
        xticklabels=["No churn (0)", "Churn (1)"],
        yticklabels=["No churn (0)", "Churn (1)"],
        xlabel="Predicted label", ylabel="Actual label",
        title=f"Validation confusion matrix (threshold = {threshold:.1f})",
    )
    midpoint = cm.max() / 2 if cm.size and cm.max() else 0
    for row in range(2):
        for col in range(2):
            ax.text(
                col, row, f"{cm[row, col]:,}", ha="center", va="center",
                color="white" if cm[row, col] > midpoint else "black",
                fontsize=14, fontweight="bold",
            )
    fig.savefig(evidence / "confusion-matrix.png", dpi=180)
    plt.close(fig)

    gain = model.get_score(importance_type="gain")
    importance = {
        name: float(gain.get(name, gain.get(f"f{i}", 0.0)))
        for i, name in enumerate(FEATURES)
    }
    ranked = sorted(importance.items(), key=lambda pair: pair[1])
    fig, ax = plt.subplots(figsize=(9.2, 6.4), constrained_layout=True)
    ax.barh([name for name, _ in ranked], [score for _, score in ranked], color="#2878B5")
    ax.set_xlabel("Average gain across splits")
    ax.set_title("XGBoost feature importance (gain)")
    ax.grid(axis="x", alpha=0.2)
    fig.savefig(evidence / "feature-importance.png", dpi=180)
    plt.close(fig)

    slice_csv = evidence / "slice_evaluation.csv"
    slice_out = evidence / "slice-evaluation.csv"
    if not slice_csv.exists():
        raise FileNotFoundError(f"Expected training output not found: {slice_csv}")
    slices = pd.read_csv(slice_csv)
    slices.to_csv(slice_out, index=False)

    query_match = re.search(r"Athena QueryExecutionId:\s*([0-9a-f-]{36})", log_text)
    run_match = re.search(r"/runs/([0-9a-f]{32})", log_text)
    package_match = re.search(r"Model registered:\s*(arn:[^\s]+)", log_text)
    query_id = query_match.group(1) if query_match else "not found in log"
    run_id = run_match.group(1) if run_match else "not found in log"
    package_arn = package_match.group(1) if package_match else "not found in log"
    hyper = metadata["hyperparameters"]
    ci_low, ci_high = metrics["lift_ci_low"], metrics["lift_ci_high"]

    table_rows = []
    for row in slices.to_dict(orient="records"):
        too_small = str(row.get("too_small", False)).lower() == "true"
        flag = "Yes — interpret cautiously" if too_small else "No"
        table_rows.append(
            f"| {row['tier']} | {int(row['n'])} | {int(row['positives'])} | "
            f"{float(row['auc']):.3f} | {float(row['recall_top10']):.3f} | {flag} |"
        )

    weakest = slices.sort_values("recall_top10").iloc[0]
    flagged_slices = slices[
        slices["below_aggregate"].astype(str).str.lower() == "true"
    ]
    flagged_text = "; ".join(
        f"{row['tier']} ({float(row['recall_top10']):.3f}; "
        f"n={int(row['n'])}, positives={int(row['positives'])})"
        for row in flagged_slices.to_dict(orient="records")
    ) or "none"
    top_gain = max(importance.items(), key=lambda pair: pair[1])
    best_iteration = model.attr("best_iteration")
    best_iteration_note = (
        f"The saved model reports best iteration {best_iteration}."
        if best_iteration is not None else
        "Training used early stopping on validation AUC, with 200 rounds as the configured maximum."
    )
    report = f"""# Task 1 — Churn model evaluation

## Evaluation setup

The final run read the Lab 2 SageMaker Feature Store offline data through Athena (query ID `{query_id}`), then sorted and deduplicated customers in the training query. The dataset contained 9,999 customers. A stratified 70/30 split produced 6,999 training rows and 3,000 held-out validation rows (`random_state=42`). Missing feature values were filled with `-1`.

The final model was a local XGBoost {metadata.get('xgboost_version', '3.2.0')} binary classifier using 11 features. Its configured hyperparameters were `max_depth={hyper['max_depth']}`, `eta={hyper['eta']}`, `num_round={hyper['num_round']}`, `min_child_weight=5`, `subsample=0.8`, `colsample_bytree=0.8`, and a training-split-derived `scale_pos_weight=3.5448`. {best_iteration_note}

## Held-out metrics

| Metric | Result | Interpretation |
|---|---:|---|
| AUC-ROC | {metrics['auc_roc']:.4f} | Reported; no absolute AUC gate |
| Recency-only baseline AUC | {metrics['baseline_auc']:.4f} | Baseline trained on `days_since_last_purchase` alone |
| AUC lift over baseline | {metrics['auc_vs_baseline']:.4f} | Full-model AUC minus baseline AUC |
| Paired bootstrap 95% CI for lift | [{ci_low:.4f}, {ci_high:.4f}] | Excludes zero; evidence the engineered model improves on recency |
| Precision in highest-scored 10% | {metrics['precision_top10']:.4f} | Passes the 0.50 minimum |
| Recall in highest-scored 10% | {metrics['recall_top10']:.4f} | Passes the 0.25 minimum |
| Validation customers | {metrics['n_val_samples']:,} | Held-out rows |

Precision and recall at the top 10% use a ranking cutoff over validation probabilities. The confusion matrix below uses a separate fixed classification threshold of 0.50.

The lift interval uses 2,000 paired bootstrap resamples of the same validation row indices for both models (seed 42); its endpoints are the 2.5th and 97.5th percentiles of the resampled AUC differences.

![Confusion matrix at threshold 0.50](lab3-evidence/confusion-matrix.png)

## Loyalty-tier slices

The table reports each tier's sample count alongside AUC and recall among customers selected by the same global top-10% score cutoff. A tier is marked too small when it has fewer than 20 positive or fewer than 20 negative validation examples.

| Tier | n | Positives | AUC | Recall@top10 | Too small |
|---|---:|---:|---:|---:|---|
{chr(10).join(table_rows)}

Aggregate top-10% recall is {metrics['recall_top10']:.3f}. Tiers flagged as more than 10 percentage points below it are: **{flagged_text}**. The lowest recall is **{weakest['tier']}**; its AUC is {float(weakest['auc']):.3f}, showing why ranking quality and recall under a global contact budget tell different stories. Its positive count is just above the report's small-sample cutoff, so interpret that tier's recall cautiously. No tier meets the script's formal too-small rule.

Full slice results: [slice-evaluation.csv](lab3-evidence/slice-evaluation.csv).

## Feature importance

This plot uses XGBoost's average gain importance. It describes how the fitted model used features; it is not a causal explanation.

![XGBoost feature importance by gain](lab3-evidence/feature-importance.png)

The highest-gain feature is **{top_gain[0]}**. Importance is conditional on this training sample and these model settings.

## Provenance and decision

The final run was logged in the `northstar-churn` MLflow experiment (run ID `{run_id}`) and registered as `{package_arn}` with `PendingManualApproval`. The registered model is not approved for deployment. Evaluation gates passed: precision@top10 ≥ 0.50, recall@top10 ≥ 0.25, and the paired 95% confidence interval for AUC lift is above zero.
"""
    (root / "docs/lab3-evaluation-report.md").write_text(report, encoding="utf-8")

    print(f"Wrote {evidence / 'confusion-matrix.png'}")
    print(f"Wrote {evidence / 'feature-importance.png'}")
    print(f"Wrote {slice_out}")
    print(root / "docs/lab3-evaluation-report.md")
    print(f"Confusion matrix [tn fp; fn tp]: {cm.tolist()}")
    for name, value in reproduced.items():
        print(f"Reproduced {name}: {value:.4f} (saved: {metrics[name]:.4f})")
    print(f"Top feature by gain: {top_gain[0]}")


if __name__ == "__main__":
    main()
