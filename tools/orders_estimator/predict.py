"""
Prediction module for the Orders Estimator.

Handles:
- Loading saved LightGBM models and feature schema
- Single and batch prediction
- Confidence flag computation
- Guardrails (capping, zero-prediction alerts)
"""

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import lightgbm as lgb

from . import __version__
from .config import (
    MODELS_DIR,
    ALL_FEATURE_COLUMNS,
    CATEGORICAL_FEATURES,
    PREDICTION_COLUMNS,
)
from .features import prepare_features


def load_models(models_dir: str = None) -> dict:
    """
    Load saved LightGBM models and feature schema.

    Returns:
        {
            models: {p10: lgb.Booster, p50: ..., p90: ...},
            feature_schema: dict,
            training_meta: dict,
        }

    Raises:
        FileNotFoundError: If model files don't exist.
        ValueError: If feature_schema.json is corrupted or missing.
    """
    models_dir = models_dir or MODELS_DIR

    # Load models
    models = {}
    for label in ["p10", "p50", "p90"]:
        path = os.path.join(models_dir, f"model_{label}.txt")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"No trained model found at {path}. Run 'cli.py train' first."
            )
        # Load via Python I/O to avoid LightGBM C library path issues
        with open(path, "r", encoding="utf-8") as f:
            model_str = f.read()
        model = lgb.Booster(model_str=model_str)
        models[label] = model

    # Load feature schema
    schema_path = os.path.join(models_dir, "feature_schema.json")
    if not os.path.exists(schema_path):
        raise ValueError(f"Feature schema not found at {schema_path}")
    with open(schema_path) as f:
        feature_schema = json.load(f)

    # Load training metadata
    meta_path = os.path.join(models_dir, "training_meta.json")
    training_meta = {}
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            training_meta = json.load(f)

    return {
        "models": models,
        "feature_schema": feature_schema,
        "training_meta": training_meta,
    }


def compute_confidence(row: pd.Series) -> str:
    """
    Assign confidence level based on available feature coverage.

    HIGH:   has catalog + has Instagram + has traffic
    MEDIUM: has Instagram + has traffic
    LOW:    everything else
    """
    has_catalog = int(row.get("has_catalog", 0)) == 1
    has_ig = int(row.get("has_instagram", 0)) == 1

    # Check traffic from raw or derived
    has_traffic = False
    if "estimated_monthly_visits" in row.index:
        has_traffic = pd.notna(row["estimated_monthly_visits"]) and row["estimated_monthly_visits"] > 0
    elif "log_monthly_visits" in row.index:
        has_traffic = row.get("log_monthly_visits", 0) > 0

    if has_catalog and has_ig and has_traffic:
        return "high"
    elif has_ig and has_traffic:
        return "medium"
    else:
        return "low"


def predict_single(row: dict, loaded: dict = None) -> dict:
    """
    Predict for a single store.

    Args:
        row: Dict with enrichment features.
        loaded: Pre-loaded models dict from load_models() (optional).

    Returns:
        {
            predicted_orders_p10: int,
            predicted_orders_p50: int,
            predicted_orders_p90: int,
            prediction_confidence: str,
            model_version: str,
        }

    Raises:
        ValueError: If required features (platform, category) are missing.
    """
    if loaded is None:
        loaded = load_models()

    df = pd.DataFrame([row])
    result = predict_batch(df, loaded=loaded)
    return result.iloc[0][PREDICTION_COLUMNS].to_dict()


def predict_batch(
    df: pd.DataFrame,
    loaded: dict = None,
    max_cap_multiplier: float = 2.0,
) -> pd.DataFrame:
    """
    Predict for a batch of stores.

    Args:
        df: DataFrame with enrichment features.
        loaded: Pre-loaded models dict from load_models() (optional).
        max_cap_multiplier: Cap predictions at this multiple of max training target.

    Returns:
        Input DataFrame with prediction columns appended.
    """
    if loaded is None:
        loaded = load_models()

    models = loaded["models"]
    training_meta = loaded["training_meta"]
    version = training_meta.get("version", __version__)
    target_max = training_meta.get("target_max", 50000)
    cap = target_max * max_cap_multiplier

    # Prepare features (do NOT require target)
    X, _, warnings = prepare_features(df.copy(), require_target=False)
    if warnings:
        for w in warnings:
            print(f"  WARNING: {w}", file=sys.stderr)

    # Predict on log scale, transform back
    preds = {}
    for label, model in models.items():
        pred_log = model.predict(X)
        pred = np.maximum(np.expm1(pred_log), 0)
        preds[label] = pred

    # Enforce monotonicity: p10 <= p50 <= p90
    p10 = preds["p10"].copy()
    p50 = preds["p50"].copy()
    p90 = preds["p90"].copy()
    p10 = np.minimum(p10, p50)
    p90 = np.maximum(p90, p50)

    # Cap extreme predictions
    capped = 0
    for arr in [p10, p50, p90]:
        over = arr > cap
        capped += over.sum()
        arr[over] = cap
    if capped > 0:
        print(
            f"  WARNING: {capped} predictions capped at {cap:.0f} "
            f"(2x max training target {target_max:.0f})",
            file=sys.stderr,
        )

    # Round to integers
    df = df.copy()
    df["predicted_orders_p10"] = np.round(p10).astype(int)
    df["predicted_orders_p50"] = np.round(p50).astype(int)
    df["predicted_orders_p90"] = np.round(p90).astype(int)

    # Confidence flags
    df["prediction_confidence"] = X.apply(compute_confidence, axis=1)

    # Model version
    df["model_version"] = version

    # Zero-prediction alert
    zero_pct = (df["predicted_orders_p50"] == 0).mean()
    if zero_pct > 0.8:
        print(
            f"  CRITICAL: {zero_pct:.0%} of P50 predictions are zero. "
            "Model may be broken or data is wildly out-of-distribution.",
            file=sys.stderr,
        )

    return df
