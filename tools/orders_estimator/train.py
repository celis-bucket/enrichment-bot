"""
Training pipeline for the Orders Estimator.

Handles:
- Loading and validating training CSV
- Training 3 LightGBM quantile models (P10/P50/P90)
- Hyperparameter sweep
- Saving all artifacts (models, schema, metadata, feature importance)
"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import lightgbm as lgb

from . import __version__
from .config import (
    ARTIFACTS_DIR,
    MODELS_DIR,
    DATASETS_DIR,
    REPORTS_DIR,
    LGBM_PARAMS,
    PARAM_GRID,
    ALL_FEATURE_COLUMNS,
    CATEGORICAL_FEATURES,
    TARGET_COLUMN,
    ALLOWED_PLATFORMS,
)
from .features import prepare_features
from .evaluate import (
    cross_validate,
    sweep_hyperparameters,
    check_leakage,
    compute_metrics,
    compute_bucket_accuracy,
)

_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from models.enrichment_result import ALLOWED_CATEGORIES


def load_training_data(csv_path: str) -> pd.DataFrame:
    """
    Load and validate training CSV.

    Raises:
        FileNotFoundError: If csv_path doesn't exist.
        ValueError: If TARGET_COLUMN is missing or has NaN.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Training CSV not found: {csv_path}")

    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    print(f"  Loaded {len(df)} rows, {len(df.columns)} columns from {os.path.basename(csv_path)}")

    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"TARGET MISSING: Column '{TARGET_COLUMN}' not found. Columns: {list(df.columns)}")

    return df


def _data_hash(csv_path: str) -> str:
    """SHA-256 hash of CSV file content."""
    h = hashlib.sha256()
    with open(csv_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def _ensure_dirs():
    """Create artifact directories if they don't exist."""
    for d in [ARTIFACTS_DIR, MODELS_DIR, DATASETS_DIR, REPORTS_DIR]:
        os.makedirs(d, exist_ok=True)


def train_quantile_models(
    X: pd.DataFrame,
    y: pd.Series,
    params: dict = None,
    quantiles: list = None,
) -> dict:
    """
    Train LightGBM quantile regression models.

    Args:
        X: Feature DataFrame with ALL_FEATURE_COLUMNS.
        y: Raw target (Monthly_orderts). Will be log1p-transformed internally.
        params: LightGBM params override (default: LGBM_PARAMS).
        quantiles: List of quantile values (default: [0.1, 0.5, 0.9]).

    Returns:
        Dict mapping "p10"/"p50"/"p90" to trained lgb.Booster.
    """
    quantiles = quantiles or [0.1, 0.5, 0.9]
    params = params or LGBM_PARAMS.copy()

    y_log = np.log1p(y.values.astype(float))
    sample_weights = np.log1p(y.values.astype(float)) + 1

    models = {}
    labels = {0.1: "p10", 0.5: "p50", 0.9: "p90"}

    for q in quantiles:
        label = labels.get(q, f"p{int(q*100)}")
        print(f"  Training {label} model (quantile={q})...", end=" ", flush=True)
        t0 = time.time()

        p = {**params}
        p["objective"] = "quantile"
        p["alpha"] = q
        n_estimators = p.pop("n_estimators", 500)
        random_state = p.pop("random_state", 42)
        p["seed"] = random_state
        p.pop("early_stopping_rounds", None)

        train_ds = lgb.Dataset(
            X, label=y_log, weight=sample_weights,
            categorical_feature=CATEGORICAL_FEATURES,
            free_raw_data=False,
        )

        model = lgb.train(p, train_ds, num_boost_round=n_estimators)

        elapsed = time.time() - t0
        print(f"done ({elapsed:.1f}s, {model.num_trees()} trees)")
        models[label] = model

    return models


def save_artifacts(
    models: dict,
    feature_importance: dict,
    training_meta: dict,
    output_dir: str = None,
) -> str:
    """
    Save all training artifacts to disk.

    Saves:
        model_p10.txt, model_p50.txt, model_p90.txt (LightGBM text format)
        feature_schema.json
        training_meta.json
        feature_importance.json

    Returns:
        Path to output directory.
    """
    output_dir = output_dir or MODELS_DIR
    os.makedirs(output_dir, exist_ok=True)

    # Save models using Python file I/O (avoids LightGBM C library path issues
    # with Google Drive / Unicode paths)
    for label, model in models.items():
        model_path = os.path.join(output_dir, f"model_{label}.txt")
        model_str = model.model_to_string()
        with open(model_path, "w", encoding="utf-8") as f:
            f.write(model_str)
        print(f"  Saved {model_path}")

    # Save feature schema
    schema = {
        "version": __version__,
        "feature_columns": ALL_FEATURE_COLUMNS,
        "categorical_features": CATEGORICAL_FEATURES,
        "allowed_platforms": ALLOWED_PLATFORMS,
        "allowed_categories": ALLOWED_CATEGORIES,
        "target_transform": "log1p",
        "model_backend": "lightgbm",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    schema_path = os.path.join(output_dir, "feature_schema.json")
    with open(schema_path, "w") as f:
        json.dump(schema, f, indent=2, default=str)
    print(f"  Saved {schema_path}")

    # Save training metadata
    meta_path = os.path.join(output_dir, "training_meta.json")
    with open(meta_path, "w") as f:
        json.dump(training_meta, f, indent=2, default=str)
    print(f"  Saved {meta_path}")

    # Save feature importance
    imp_path = os.path.join(output_dir, "feature_importance.json")
    with open(imp_path, "w") as f:
        json.dump(feature_importance, f, indent=2)
    print(f"  Saved {imp_path}")

    return output_dir


def train_pipeline(
    csv_path: str,
    output_dir: str = None,
    force: bool = False,
    skip_sweep: bool = False,
) -> dict:
    """
    Full training pipeline: load -> validate -> sweep -> train -> evaluate -> save.

    Args:
        csv_path: Path to training CSV.
        output_dir: Custom output directory (default: .tmp/orders_estimator/models).
        force: Force retrain even if data hash unchanged.
        skip_sweep: Skip hyperparameter sweep (use defaults).

    Returns:
        {models_dir, metrics, feature_importance, warnings, training_meta}
    """
    _ensure_dirs()
    output_dir = output_dir or MODELS_DIR
    all_warnings = []

    # Check data hash
    data_hash = _data_hash(csv_path)
    meta_path = os.path.join(output_dir, "training_meta.json")
    if os.path.exists(meta_path) and not force:
        with open(meta_path) as f:
            prev_meta = json.load(f)
        if prev_meta.get("data_hash") == data_hash:
            print(f"  Data unchanged (hash={data_hash}). Use --force to retrain.")
            return {"models_dir": output_dir, "skipped": True}

    print(f"\n{'='*60}")
    print(f"  ORDERS ESTIMATOR v{__version__} — TRAINING PIPELINE")
    print(f"  Backend: LightGBM {lgb.__version__}")
    print(f"{'='*60}\n")

    # 1. Load data
    print("[1/6] Loading training data...")
    df = load_training_data(csv_path)

    # Save dataset snapshot
    snapshot_name = f"training_{datetime.now().strftime('%Y%m%d')}_{data_hash}.csv"
    snapshot_path = os.path.join(DATASETS_DIR, snapshot_name)
    if not os.path.exists(snapshot_path):
        df.to_csv(snapshot_path, index=False)
        print(f"  Snapshot: {snapshot_path}")

    # 2. Prepare features
    print("\n[2/6] Preparing features...")
    X, y, prep_warnings = prepare_features(df, require_target=True)
    all_warnings.extend(prep_warnings)
    print(f"  Features: {X.shape[1]}, Samples: {X.shape[0]}")
    if prep_warnings:
        for w in prep_warnings:
            print(f"  WARNING: {w}")

    # 3. Leakage checks
    print("\n[3/6] Running leakage checks...")
    leakage_warnings = check_leakage(X, y)
    all_warnings.extend(leakage_warnings)
    if leakage_warnings:
        for w in leakage_warnings:
            print(f"  WARNING: {w}")
    else:
        print("  No leakage detected.")

    # 4. Hyperparameter sweep
    best_params = LGBM_PARAMS.copy()
    if not skip_sweep:
        print("\n[4/6] Running hyperparameter sweep (27 combos x 15 folds)...")
        sweep_result = sweep_hyperparameters(X, y, PARAM_GRID)
        print(f"  Best params: {sweep_result['best_params']}")
        print(f"  Best CV WAPE: {sweep_result['best_wape']:.3f}")
        best_params.update(sweep_result["best_params"])
        # Sync num_leaves with max_depth
        if "max_depth" in sweep_result["best_params"]:
            best_params["num_leaves"] = min(2 ** sweep_result["best_params"]["max_depth"] - 1, 31)

        # Save sweep report
        sweep_path = os.path.join(REPORTS_DIR, "sweep_report.json")
        with open(sweep_path, "w") as f:
            json.dump(sweep_result, f, indent=2)
    else:
        print("\n[4/6] Skipping hyperparameter sweep (using defaults).")
        sweep_result = None

    # 5. Cross-validation
    print("\n[5/6] Running cross-validation...")
    cv_result = cross_validate(X, y, params=best_params)
    all_warnings.extend(cv_result.get("overfitting_warnings", []))

    m = cv_result["metrics"]
    print(f"  WAPE:     {m['wape']['mean']:.3f} (+/- {m['wape']['std']:.3f})")
    print(f"  MAE:      {m['mae']['mean']:.0f} (+/- {m['mae']['std']:.0f})")
    print(f"  MdAE:     {m['mdae']['mean']:.0f} (+/- {m['mdae']['std']:.0f})")
    print(f"  R²:       {m['r2']['mean']:.3f} (+/- {m['r2']['std']:.3f})")
    print(f"  Spearman: {m['spearman']['mean']:.3f} (+/- {m['spearman']['std']:.3f})")
    print(f"  Bucket accuracy (exact): {m['exact']['mean']:.1%}")
    print(f"  Bucket accuracy (±1):    {m['within_1']['mean']:.1%}")
    print(f"  Baseline naive median WAPE: {cv_result['baseline_naive_median_wape']:.3f}")

    if cv_result.get("overfitting_warnings"):
        for w in cv_result["overfitting_warnings"]:
            print(f"  WARNING: {w}")

    # Save CV report
    cv_path = os.path.join(REPORTS_DIR, "cv_report.json")
    with open(cv_path, "w") as f:
        json.dump(cv_result, f, indent=2)

    # 6. Train final models on full data
    print("\n[6/6] Training final quantile models on full data...")
    models = train_quantile_models(X, y, params=best_params)

    # Feature importance from P50 model
    p50_model = models["p50"]
    importance_vals = p50_model.feature_importance(importance_type="gain")
    feature_names = ALL_FEATURE_COLUMNS
    feature_importance = {
        "method": "gain",
        "features": sorted(
            [{"name": name, "importance": round(float(imp), 2)}
             for name, imp in zip(feature_names, importance_vals)],
            key=lambda x: x["importance"],
            reverse=True,
        ),
    }

    print("\n  Top 10 features:")
    for i, feat in enumerate(feature_importance["features"][:10], 1):
        print(f"    {i:2d}. {feat['name']:30s} {feat['importance']:.1f}")

    # Training metadata
    training_meta = {
        "version": __version__,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "data_hash": data_hash,
        "data_file": os.path.basename(csv_path),
        "n_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "target_max": float(y.max()),
        "target_min": float(y.min()),
        "target_median": float(y.median()),
        "cv_wape_mean": m["wape"]["mean"],
        "cv_wape_std": m["wape"]["std"],
        "cv_r2_mean": m["r2"]["mean"],
        "cv_spearman_mean": m["spearman"]["mean"],
        "cv_bucket_exact": m["exact"]["mean"],
        "cv_bucket_within_1": m["within_1"]["mean"],
        "baseline_naive_wape": cv_result["baseline_naive_median_wape"],
        "model_backend": "lightgbm",
        "lgbm_params": best_params,
        "overfitting_warnings": all_warnings,
    }

    # Save artifacts
    print("\n  Saving artifacts...")
    save_artifacts(models, feature_importance, training_meta, output_dir)

    print(f"\n{'='*60}")
    print(f"  TRAINING COMPLETE")
    print(f"  Model version: {__version__}")
    print(f"  Artifacts: {output_dir}")
    print(f"{'='*60}\n")

    return {
        "models_dir": output_dir,
        "metrics": cv_result["metrics"],
        "feature_importance": feature_importance,
        "warnings": all_warnings,
        "training_meta": training_meta,
        "skipped": False,
    }
