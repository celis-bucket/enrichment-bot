"""
Configuration and schema definitions for the Orders Estimator.
Single source of truth for feature schema, model parameters, and bucket definitions.

Uses LightGBM as the primary model (CatBoost unavailable on Python 3.14).
"""

import os
import sys

_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from models.enrichment_result import ALLOWED_CATEGORIES

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
ARTIFACTS_DIR = os.path.join(PROJECT_ROOT, ".tmp", "orders_estimator")
MODELS_DIR = os.path.join(ARTIFACTS_DIR, "models")
DATASETS_DIR = os.path.join(ARTIFACTS_DIR, "datasets")
REPORTS_DIR = os.path.join(ARTIFACTS_DIR, "reports")

# ---------------------------------------------------------------------------
# Feature Schema
# ---------------------------------------------------------------------------
RAW_FEATURE_COLUMNS = [
    "platform",
    "category",
    "ig_followers",
    "ig_engagement_rate",
    "ig_size_score",
    "ig_health_score",
    "product_count",
    "avg_price",
    "price_range_min",
    "price_range_max",
    "estimated_monthly_visits",
    "brand_demand_score",
    "number_employes",
]

CATEGORICAL_FEATURES = ["platform", "category"]

DERIVED_FEATURE_COLUMNS = [
    "has_catalog",
    "has_instagram",
    "has_employees_data",
    "log_ig_followers",
    "log_monthly_visits",
    "log_product_count",
    "log_avg_price",
    "log_number_employes",
    "price_range_ratio",
]

ALL_FEATURE_COLUMNS = RAW_FEATURE_COLUMNS + DERIVED_FEATURE_COLUMNS

TARGET_COLUMN = "Monthly_orderts (target)"

ALLOWED_PLATFORMS = [
    "Shopify", "WooCommerce", "VTEX", "Custom", "PrestaShop", "Magento", "other",
]

# ---------------------------------------------------------------------------
# Bucket Definitions (order tiers)
# ---------------------------------------------------------------------------
ORDER_BUCKETS = {
    "micro":      (0, 50),
    "small":      (51, 300),
    "medium":     (301, 1500),
    "large":      (1501, 5000),
    "enterprise": (5001, float("inf")),
}

BUCKET_LABELS = list(ORDER_BUCKETS.keys())

# ---------------------------------------------------------------------------
# LightGBM Default Parameters (conservative for ~175 samples)
# ---------------------------------------------------------------------------
LGBM_PARAMS = {
    "n_estimators": 500,
    "learning_rate": 0.05,
    "max_depth": 4,
    "num_leaves": 15,            # conservative: 2^4 - 1
    "reg_lambda": 10.0,          # L2 regularization
    "reg_alpha": 1.0,            # L1 regularization
    "min_child_samples": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "verbose": -1,
    "n_jobs": 1,
}

# Hyperparameter sweep grid
PARAM_GRID = {
    "max_depth": [3, 4, 5],
    "reg_lambda": [5, 10, 20],
    "learning_rate": [0.03, 0.05, 0.1],
}

# ---------------------------------------------------------------------------
# Prediction output columns
# ---------------------------------------------------------------------------
PREDICTION_COLUMNS = [
    "predicted_orders_p10",
    "predicted_orders_p50",
    "predicted_orders_p90",
    "prediction_confidence",
    "model_version",
]

# ---------------------------------------------------------------------------
# Cross-validation defaults
# ---------------------------------------------------------------------------
CV_N_SPLITS = 5
CV_N_REPEATS = 3
