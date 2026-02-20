"""
Evaluation framework for the Orders Estimator.

Provides:
- Metric computation (WAPE, MAE, MdAE, R², Spearman, bucket accuracy)
- Cross-validation with repeated stratified K-fold
- Hyperparameter sweep
- Overfitting detection
- Data leakage checks

Uses LightGBM as the model backend.
"""

import numpy as np
import pandas as pd
from itertools import product as iter_product
from scipy.stats import spearmanr
from sklearn.model_selection import RepeatedStratifiedKFold
import lightgbm as lgb

from .config import (
    ORDER_BUCKETS,
    BUCKET_LABELS,
    CATEGORICAL_FEATURES,
    LGBM_PARAMS,
    PARAM_GRID,
    CV_N_SPLITS,
    CV_N_REPEATS,
)


# ---------------------------------------------------------------------------
# Bucket utilities
# ---------------------------------------------------------------------------

def assign_bucket(value: float) -> str:
    """Assign an order count to a tier bucket."""
    for label, (lo, hi) in ORDER_BUCKETS.items():
        if lo <= value <= hi:
            return label
    return BUCKET_LABELS[-1]


def _bucket_index(label: str) -> int:
    return BUCKET_LABELS.index(label)


# ---------------------------------------------------------------------------
# Metrics (all computed on ORIGINAL scale, not log)
# ---------------------------------------------------------------------------

def wape(y_true: np.ndarray, y_pred: np.ndarray, weights: np.ndarray = None) -> float:
    """
    Weighted Absolute Percentage Error.
    Weights default to log1p(y_true) + 1 so big stores matter more.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if weights is None:
        weights = np.log1p(y_true) + 1
    numerator = np.sum(np.abs(y_true - y_pred) * weights)
    denominator = np.sum(y_true * weights)
    return float(numerator / max(denominator, 1))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))))


def mdae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.median(np.abs(np.asarray(y_true) - np.asarray(y_pred))))


def r_squared(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    return float(1 - ss_res / max(ss_tot, 1e-10))


def spearman_rho(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    rho, _ = spearmanr(y_true, y_pred)
    return float(rho)


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Compute all metrics on original scale."""
    return {
        "wape": wape(y_true, y_pred),
        "mae": mae(y_true, y_pred),
        "mdae": mdae(y_true, y_pred),
        "r2": r_squared(y_true, y_pred),
        "spearman": spearman_rho(y_true, y_pred),
    }


def compute_bucket_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Compute exact and +/-1 bucket accuracy."""
    true_buckets = [assign_bucket(v) for v in y_true]
    pred_buckets = [assign_bucket(v) for v in y_pred]

    exact = sum(t == p for t, p in zip(true_buckets, pred_buckets))
    within_1 = sum(
        abs(_bucket_index(t) - _bucket_index(p)) <= 1
        for t, p in zip(true_buckets, pred_buckets)
    )
    n = len(y_true)
    return {
        "exact": exact / max(n, 1),
        "within_1": within_1 / max(n, 1),
    }


# ---------------------------------------------------------------------------
# LightGBM helpers
# ---------------------------------------------------------------------------

def _build_lgb_dataset(X: pd.DataFrame, y_log: np.ndarray, weights: np.ndarray = None):
    """Build LightGBM Dataset with categorical feature handling."""
    ds = lgb.Dataset(
        X, label=y_log, weight=weights,
        categorical_feature=CATEGORICAL_FEATURES,
        free_raw_data=False,
    )
    return ds


def _train_lgbm(X_train, y_train_log, w_train, X_val, y_val_log, params, objective="regression"):
    """Train a single LightGBM model with early stopping."""
    p = {**params}
    p["objective"] = objective
    # Remove keys that are passed to lgb.train() separately
    n_estimators = p.pop("n_estimators", 500)
    random_state = p.pop("random_state", 42)
    p["seed"] = random_state
    early_stopping = p.pop("early_stopping_rounds", 50)

    train_ds = lgb.Dataset(X_train, label=y_train_log, weight=w_train,
                           categorical_feature=CATEGORICAL_FEATURES, free_raw_data=False)
    val_ds = lgb.Dataset(X_val, label=y_val_log,
                         categorical_feature=CATEGORICAL_FEATURES, free_raw_data=False)

    callbacks = [lgb.early_stopping(stopping_rounds=early_stopping, verbose=False),
                 lgb.log_evaluation(period=0)]

    model = lgb.train(
        p, train_ds,
        num_boost_round=n_estimators,
        valid_sets=[val_ds],
        callbacks=callbacks,
    )
    return model


# ---------------------------------------------------------------------------
# Cross-validation
# ---------------------------------------------------------------------------

def _stratify_labels(y: np.ndarray) -> np.ndarray:
    """Create bucket labels for stratified splitting."""
    return np.array([assign_bucket(v) for v in y])


def cross_validate(
    X: pd.DataFrame,
    y: pd.Series,
    params: dict = None,
    n_splits: int = CV_N_SPLITS,
    n_repeats: int = CV_N_REPEATS,
) -> dict:
    """
    Repeated stratified K-fold cross-validation with LightGBM.

    Returns:
        Dict with per-fold and aggregate metrics, overfitting warnings,
        and baseline comparisons.
    """
    params = params or LGBM_PARAMS.copy()
    params["early_stopping_rounds"] = 50
    y_arr = y.values.astype(float)
    y_log = np.log1p(y_arr)
    sample_weights = np.log1p(y_arr) + 1
    strat_labels = _stratify_labels(y_arr)

    cv = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=42)

    fold_metrics = []
    train_rmses = []
    cv_rmses_log = []

    for train_idx, val_idx in cv.split(X, strat_labels):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train_log, y_val_log = y_log[train_idx], y_log[val_idx]
        w_train = sample_weights[train_idx]

        model = _train_lgbm(X_train, y_train_log, w_train, X_val, y_val_log, params)

        # Predictions on original scale
        pred_log = model.predict(X_val)
        pred = np.maximum(np.expm1(pred_log), 0)
        y_val_orig = y_arr[val_idx]

        fold_metrics.append(compute_metrics(y_val_orig, pred))
        fold_metrics[-1].update(compute_bucket_accuracy(y_val_orig, pred))

        # Train RMSE for overfitting check
        train_pred_log = model.predict(X_train)
        train_rmse = np.sqrt(np.mean((y_train_log - train_pred_log) ** 2))
        train_rmses.append(train_rmse)

        val_rmse = np.sqrt(np.mean((y_val_log - pred_log) ** 2))
        cv_rmses_log.append(val_rmse)

    # Aggregate
    metric_names = ["wape", "mae", "mdae", "r2", "spearman", "exact", "within_1"]
    agg = {}
    for m in metric_names:
        vals = [f[m] for f in fold_metrics]
        agg[m] = {"mean": float(np.mean(vals)), "std": float(np.std(vals))}

    # Baselines
    naive_pred = np.full(len(y_arr), np.median(y_arr))
    naive_metrics = compute_metrics(y_arr, naive_pred)

    # Overfitting check
    overfitting_warnings = check_overfitting(
        train_rmse=float(np.mean(train_rmses)),
        cv_rmses=cv_rmses_log,
        n_features=X.shape[1],
        n_samples=X.shape[0],
    )

    return {
        "metrics": agg,
        "n_folds": n_splits * n_repeats,
        "n_samples": len(y_arr),
        "baseline_naive_median_wape": naive_metrics["wape"],
        "overfitting_warnings": overfitting_warnings,
    }


# ---------------------------------------------------------------------------
# Hyperparameter sweep
# ---------------------------------------------------------------------------

def sweep_hyperparameters(
    X: pd.DataFrame,
    y: pd.Series,
    param_grid: dict = None,
    n_splits: int = CV_N_SPLITS,
    n_repeats: int = CV_N_REPEATS,
) -> dict:
    """
    Sweep over hyperparameter grid, selecting best by mean CV WAPE.

    Returns:
        {best_params, best_wape, all_results}
    """
    param_grid = param_grid or PARAM_GRID
    base_params = LGBM_PARAMS.copy()
    base_params["early_stopping_rounds"] = 50

    y_arr = y.values.astype(float)
    y_log = np.log1p(y_arr)
    sample_weights = np.log1p(y_arr) + 1
    strat_labels = _stratify_labels(y_arr)
    cv = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=42)

    keys = sorted(param_grid.keys())
    combos = list(iter_product(*(param_grid[k] for k in keys)))

    all_results = []
    best_wape = float("inf")
    best_params = {}

    for combo in combos:
        override = dict(zip(keys, combo))
        params = {**base_params, **override}
        # Update num_leaves to match max_depth
        if "max_depth" in override:
            params["num_leaves"] = min(2 ** override["max_depth"] - 1, 31)

        fold_wapes = []
        for train_idx, val_idx in cv.split(X, strat_labels):
            model = _train_lgbm(
                X.iloc[train_idx], y_log[train_idx], sample_weights[train_idx],
                X.iloc[val_idx], y_log[val_idx], params,
            )
            pred = np.maximum(np.expm1(model.predict(X.iloc[val_idx])), 0)
            fold_wapes.append(wape(y_arr[val_idx], pred))

        mean_wape = float(np.mean(fold_wapes))
        all_results.append({
            "params": override,
            "mean_wape": mean_wape,
            "std_wape": float(np.std(fold_wapes)),
        })

        if mean_wape < best_wape:
            best_wape = mean_wape
            best_params = override

    return {
        "best_params": best_params,
        "best_wape": best_wape,
        "all_results": sorted(all_results, key=lambda r: r["mean_wape"]),
    }


# ---------------------------------------------------------------------------
# Overfitting & leakage checks
# ---------------------------------------------------------------------------

def check_overfitting(
    train_rmse: float,
    cv_rmses: list,
    n_features: int,
    n_samples: int,
) -> list:
    """Detect overfitting from train/CV gap and CV variance."""
    warnings = []
    cv_mean = np.mean(cv_rmses)
    cv_std = np.std(cv_rmses)

    if cv_mean > 0:
        gap = 1 - (train_rmse / cv_mean)
        if gap > 0.30:
            warnings.append(
                f"OVERFITTING: train RMSE {train_rmse:.3f} vs CV {cv_mean:.3f} (gap={gap:.1%})"
            )
    if cv_mean > 0 and cv_std > 0.3 * cv_mean:
        warnings.append(
            f"UNSTABLE: CV RMSE std={cv_std:.3f}, mean={cv_mean:.3f} (ratio={cv_std/cv_mean:.1%})"
        )
    if n_features > n_samples / 5:
        warnings.append(
            f"HIGH DIMENSIONALITY: {n_features} features for {n_samples} samples "
            f"(ratio={n_samples/n_features:.1f}:1, recommend >5:1)"
        )
    return warnings


def check_leakage(X: pd.DataFrame, y: pd.Series) -> list:
    """
    Run leakage checks against features and target.

    Checks:
        - No numeric feature has Pearson r > 0.95 with target
        - signals_used column is not present
    """
    warnings = []

    numeric_cols = X.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        valid = X[col].notna() & y.notna()
        if valid.sum() < 10:
            continue
        corr = np.corrcoef(X.loc[valid, col], y[valid])[0, 1]
        if abs(corr) > 0.95:
            warnings.append(
                f"LEAKAGE WARNING: '{col}' has Pearson r={corr:.3f} with target"
            )

    if "signals_used" in X.columns:
        warnings.append("LEAKAGE WARNING: 'signals_used' is pipeline metadata, not a store feature")

    return warnings
