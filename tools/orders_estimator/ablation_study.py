"""
Ablation study for the Orders Estimator.

Trains the model with different feature subsets to validate
that removing redundant features does not degrade performance.

Usage:
    python -m tools.orders_estimator.ablation_study "Traning data algorith order estimation V3.csv"
"""

import os
import sys
import time
import json
import argparse

import numpy as np
import pandas as pd

# Allow imports from tools/ root
_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from orders_estimator.config import (
    LGBM_PARAMS,
    CATEGORICAL_FEATURES,
    TARGET_COLUMN,
    ALL_FEATURE_COLUMNS,
)
from orders_estimator.features import prepare_features, compute_derived_features, _normalize_prices
from orders_estimator.evaluate import cross_validate
from orders_estimator.train import load_training_data


# ---------------------------------------------------------------------------
# Feature set definitions for ablation
# ---------------------------------------------------------------------------

FEATURE_SETS = {
    "v3_baseline": {
        "description": "Current V3 model (27 features)",
        "features": ALL_FEATURE_COLUMNS,
        "categorical": CATEGORICAL_FEATURES,
    },
    "v4_no_raw_price": {
        "description": "Drop raw price features, keep log_avg_price + ratio (24 features)",
        "features": [f for f in ALL_FEATURE_COLUMNS
                     if f not in ("avg_price", "price_range_min", "price_range_max")],
        "categorical": CATEGORICAL_FEATURES,
    },
    "v4_slim": {
        "description": "Track A proposed schema (16 features)",
        "features": [
            # Categorical
            "platform",  # will be used as-is for now (platform_group requires code change)
            # Instagram
            "log_ig_followers", "ig_engagement_rate", "ig_size_score", "ig_health_score",
            # Catalog
            "log_product_count", "log_avg_price", "price_range_ratio",
            # Traffic & demand
            "log_monthly_visits", "brand_demand_score", "site_serp_coverage_score",
            # Company
            "number_employes",
            # Meta ads
            "meta_active_ads_count", "has_meta_ads",
        ],
        "categorical": ["platform"],
    },
    "v4_slim_no_platform": {
        "description": "Track A without platform (15 features)",
        "features": [
            # Instagram
            "log_ig_followers", "ig_engagement_rate", "ig_size_score", "ig_health_score",
            # Catalog
            "log_product_count", "log_avg_price", "price_range_ratio",
            # Traffic & demand
            "log_monthly_visits", "brand_demand_score", "site_serp_coverage_score",
            # Company
            "number_employes",
            # Meta ads
            "meta_active_ads_count", "has_meta_ads",
        ],
        "categorical": [],
    },
    "v4_no_price_at_all": {
        "description": "Zero price features — test price signal (20 features)",
        "features": [f for f in ALL_FEATURE_COLUMNS
                     if f not in ("avg_price", "price_range_min", "price_range_max",
                                  "log_avg_price", "price_range_ratio")],
        "categorical": CATEGORICAL_FEATURES,
    },
    "v4_top10_only": {
        "description": "Only top 10 features by V3 importance",
        "features": [
            "meta_active_ads_count", "number_employes",
            "price_range_ratio", "product_count",
            "ig_engagement_rate", "ig_health_score",
            "estimated_monthly_visits", "ig_followers",
            "ig_size_score", "brand_demand_score",
        ],
        "categorical": [],
    },
}


def run_ablation(csv_path: str, skip_sweep: bool = True):
    """
    Run ablation study across all feature sets.

    Args:
        csv_path: Path to training CSV.
        skip_sweep: If True, use default params (faster). If False, sweep per variant.
    """
    print("=" * 70)
    print("  ABLATION STUDY — Orders Estimator Feature Selection")
    print("=" * 70)

    # Load and prepare base data
    df = load_training_data(csv_path)

    # Prepare full feature set (need all columns for subsetting)
    X_full, y, warnings = prepare_features(df.copy(), require_target=True)
    if warnings:
        for w in warnings:
            print(f"  WARNING: {w}")

    print(f"\n  Full feature set: {X_full.shape[1]} features, {X_full.shape[0]} samples")
    print(f"  Target: {TARGET_COLUMN}")
    print(f"  Using {'default params' if skip_sweep else 'param sweep per variant'}")
    print()

    results = []

    for name, config in FEATURE_SETS.items():
        features = config["features"]
        categorical = config["categorical"]
        desc = config["description"]

        # Filter to available features
        available = [f for f in features if f in X_full.columns]
        missing = [f for f in features if f not in X_full.columns]

        if missing:
            print(f"  [{name}] WARNING: Missing features (skipped): {missing}")

        if len(available) < 3:
            print(f"  [{name}] SKIP: Too few features ({len(available)})")
            continue

        X_subset = X_full[available].copy()

        # Set categorical features
        cat_in_subset = [c for c in categorical if c in available]
        for col in cat_in_subset:
            X_subset[col] = X_subset[col].astype("category")

        # Patch CATEGORICAL_FEATURES in both config AND evaluate modules
        # (evaluate imports it directly with `from .config import`)
        import orders_estimator.config as cfg
        import orders_estimator.evaluate as ev
        original_cfg_cat = cfg.CATEGORICAL_FEATURES
        original_ev_cat = ev.CATEGORICAL_FEATURES
        cfg.CATEGORICAL_FEATURES = cat_in_subset
        ev.CATEGORICAL_FEATURES = cat_in_subset

        print(f"  [{name}] {desc}")
        print(f"    Features: {len(available)}, Categorical: {cat_in_subset}")

        t0 = time.time()
        params = LGBM_PARAMS.copy()

        try:
            cv_result = cross_validate(X_subset, y, params=params)
            elapsed = time.time() - t0

            m = cv_result["metrics"]
            overfitting = cv_result.get("overfitting_warnings", [])

            result = {
                "name": name,
                "description": desc,
                "n_features": len(available),
                "wape_mean": m["wape"]["mean"],
                "wape_std": m["wape"]["std"],
                "spearman_mean": m["spearman"]["mean"],
                "r2_mean": m["r2"]["mean"],
                "bucket_exact": m["exact"]["mean"],
                "bucket_within_1": m["within_1"]["mean"],
                "baseline_wape": cv_result["baseline_naive_median_wape"],
                "overfitting": overfitting,
                "elapsed_sec": elapsed,
            }
            results.append(result)

            of_flag = " [OVERFIT]" if overfitting else ""
            print(f"    WAPE={m['wape']['mean']:.3f}  Spearman={m['spearman']['mean']:.3f}  "
                  f"R2={m['r2']['mean']:.3f}  Bucket+-1={m['within_1']['mean']:.1%}  "
                  f"({elapsed:.1f}s){of_flag}")
        except Exception as e:
            print(f"    ERROR: {e}")
            results.append({"name": name, "error": str(e)})
        finally:
            cfg.CATEGORICAL_FEATURES = original_cfg_cat
            ev.CATEGORICAL_FEATURES = original_ev_cat

        print()

    # Summary table
    print("\n" + "=" * 70)
    print("  ABLATION RESULTS SUMMARY")
    print("=" * 70)
    print(f"\n  {'Variant':<25s} {'N feat':>6s} {'WAPE':>7s} {'Spearman':>9s} {'R2':>6s} {'Bkt+-1':>7s}")
    print("  " + "-" * 62)

    for r in sorted(results, key=lambda x: x.get("wape_mean", 999)):
        if "error" in r:
            print(f"  {r['name']:<25s} ERROR: {r['error'][:40]}")
            continue
        of = "*" if r["overfitting"] else " "
        print(f"  {r['name']:<25s} {r['n_features']:>6d} {r['wape_mean']:>7.3f} "
              f"{r['spearman_mean']:>9.3f} {r['r2_mean']:>6.3f} {r['bucket_within_1']:>6.1%}{of}")

    print(f"\n  * = overfitting warning (train/CV gap > 30%)")
    print(f"  Baseline naive median WAPE: {results[0].get('baseline_wape', 'N/A'):.3f}")

    # Save results
    from orders_estimator.config import REPORTS_DIR
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_path = os.path.join(REPORTS_DIR, "ablation_study.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Report saved to: {report_path}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ablation study for Orders Estimator feature selection")
    parser.add_argument("csv_path", help="Path to training CSV")
    parser.add_argument("--sweep", action="store_true", help="Run param sweep per variant (slower)")
    args = parser.parse_args()

    run_ablation(args.csv_path, skip_sweep=not args.sweep)
