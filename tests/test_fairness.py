"""Non-blocking loyalty-tier fairness check on held-out evaluation metrics."""

import json
import math
import os
import warnings
from pathlib import Path

import pytest


FAIRNESS_GAP_THRESHOLD = 0.10


def loyalty_tier_recall_gap(slice_results):
    """Return (gap, highest-tier name/recall, lowest-tier name/recall).

    The caller supplies held-out per-tier results produced at the global
    top-10% score cutoff. Slices without a finite recall are excluded.
    """
    if not isinstance(slice_results, dict):
        raise ValueError("slice_results must be a mapping of loyalty tier to metrics")

    recalls = {}
    for tier, metrics in slice_results.items():
        if not isinstance(metrics, dict):
            continue
        value = metrics.get("recall_top10")
        if value is None:
            continue
        recall = float(value)
        if math.isfinite(recall):
            if not 0.0 <= recall <= 1.0:
                raise ValueError(f"Recall for {tier} must be between 0 and 1, got {recall}")
            recalls[str(tier)] = recall

    if len(recalls) < 2:
        raise ValueError("At least two loyalty tiers must have finite recall values")

    highest_tier = max(recalls, key=recalls.get)
    lowest_tier = min(recalls, key=recalls.get)
    highest_recall = recalls[highest_tier]
    lowest_recall = recalls[lowest_tier]
    return highest_recall - lowest_recall, highest_tier, highest_recall, lowest_tier, lowest_recall


def _gap_exceeds_threshold(gap):
    """Avoid treating floating-point noise at exactly 10 percentage points as a flag."""
    return gap - FAIRNESS_GAP_THRESHOLD > 1e-12


def warn_on_recall_gap(slice_results):
    """Emit a review warning for a material disparity; never reject the model."""
    gap, high_tier, high, low_tier, low = loyalty_tier_recall_gap(slice_results)
    if _gap_exceeds_threshold(gap):
        warnings.warn(
            f"FAIRNESS FLAG: loyalty-tier recall gap is {gap:.1%}; "
            f"highest={high_tier} ({high:.3f}), lowest={low_tier} ({low:.3f}). "
            "Review the disparity before model approval.",
            UserWarning,
        )
    return gap


@pytest.fixture(scope="module")
def evaluation_metrics():
    metrics_path = os.environ.get("EVAL_METRICS_PATH")
    if not metrics_path or not Path(metrics_path).is_file():
        pytest.fail(
            "Required evaluation_metrics.json is missing. Set EVAL_METRICS_PATH to the "
            "metrics emitted by the training run.",
            pytrace=False,
        )
    with open(metrics_path, encoding="utf-8") as handle:
        metrics = json.load(handle)
    if not isinstance(metrics.get("slice_results"), dict):
        pytest.fail("Evaluation metrics must include slice_results by loyalty tier", pytrace=False)
    return metrics


def test_held_out_metrics_include_valid_recall_for_multiple_tiers(evaluation_metrics):
    """A missing slice report must fail instead of silently bypassing fairness review."""
    gap, _, high, _, low = loyalty_tier_recall_gap(evaluation_metrics["slice_results"])
    assert 0.0 <= low <= high <= 1.0
    assert 0.0 <= gap <= 1.0


def test_recall_gap_over_10pp_emits_warning_without_failing():
    sample_slices = {
        "Bronze": {"recall_top10": 0.40},
        "Silver": {"recall_top10": 0.25},
    }
    gap, _, _, _, _ = loyalty_tier_recall_gap(sample_slices)
    assert _gap_exceeds_threshold(gap)
    with pytest.warns(UserWarning, match="FAIRNESS FLAG"):
        warn_on_recall_gap(sample_slices)


def test_current_model_gap_is_flagged_but_does_not_block(evaluation_metrics):
    """Surface a material disparity in the CodeBuild warning summary, not as a failed gate."""
    gap = warn_on_recall_gap(evaluation_metrics["slice_results"])
    # Intentionally no assertion that the gap is below the limit: this is a
    # warning for the approver, not an automatic model rejection criterion.
    assert 0.0 <= gap <= 1.0
