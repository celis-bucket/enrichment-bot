"""
Feature engineering and schema validation for the Orders Estimator.

V4 schema: 15 model features (7 raw + 8 derived) — down from 27 in V3.
See config.py for rationale.

Handles:
- Input schema validation (hard fail on missing required columns, soft warn on extras)
- Currency detection and normalization (USD -> COP)
- Derived feature computation (log transforms, ratios, platform grouping)
- Full feature preparation pipeline
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional

from .config import (
    RAW_INPUT_COLUMNS,
    RAW_FEATURE_COLUMNS,
    DERIVED_FEATURE_COLUMNS,
    ALL_FEATURE_COLUMNS,
    CATEGORICAL_FEATURES,
    TARGET_COLUMN,
    ALLOWED_PLATFORMS,
)

import os, sys
_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
from models.enrichment_result import ALLOWED_CATEGORIES

# ---------------------------------------------------------------------------
# Currency normalization constants
# ---------------------------------------------------------------------------
USD_COP_RATE = 4_200   # approximate USD -> COP conversion rate
USD_THRESHOLD = 500     # avg_price below this -> detected as USD (clean gap in data)

# ---------------------------------------------------------------------------
# Platform group mapping (collapse 7 platforms -> 3)
# ---------------------------------------------------------------------------
PLATFORM_GROUP_MAP = {
    "Shopify": "shopify",
    "VTEX": "vtex",
    # Everything else -> "other"
}


def _normalize_prices(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], pd.Series]:
    """
    Detect and convert USD prices to COP.

    Returns:
        (df, warnings, usd_mask) where usd_mask is a boolean Series
        indicating which rows were detected as USD-priced.
    """
    warnings = []
    price_cols = ["avg_price", "price_range_min", "price_range_max"]

    mask = df["avg_price"].notna() & (df["avg_price"] < USD_THRESHOLD)
    n_usd = mask.sum()

    if n_usd > 0:
        for col in price_cols:
            if col in df.columns:
                df.loc[mask, col] = df.loc[mask, col] * USD_COP_RATE
        warnings.append(
            f"Currency normalization: {n_usd} stores detected as USD "
            f"(avg_price < {USD_THRESHOLD}), converted to COP at rate {USD_COP_RATE}"
        )

    return df, warnings, mask


def validate_input_schema(
    df: pd.DataFrame,
    require_target: bool = False,
) -> list[str]:
    """
    Validate input DataFrame against the feature schema.

    Checks:
    - Required column 'platform' exists
    - All RAW_INPUT_COLUMNS exist (soft fail: fills missing with NaN)
    - Platform values are known (maps unknown to 'other')
    - Target column present and non-null when required
    """
    warnings: list[str] = []

    # -- Required columns --
    if "platform" not in df.columns:
        raise ValueError("Missing required column: platform")

    # -- Check all raw input columns exist --
    missing_features = [c for c in RAW_INPUT_COLUMNS if c not in df.columns]
    if missing_features:
        warnings.append(f"Missing input columns (will be treated as NaN): {missing_features}")
        for col in missing_features:
            df[col] = np.nan

    # -- Validate platform values --
    known_platforms = set(ALLOWED_PLATFORMS)
    unknown_platforms = set(df["platform"].dropna().unique()) - known_platforms
    if unknown_platforms:
        warnings.append(f"Unknown platforms mapped to 'other': {unknown_platforms}")
        df.loc[~df["platform"].isin(known_platforms) & df["platform"].notna(), "platform"] = "other"

    # -- Target validation --
    if require_target:
        if TARGET_COLUMN not in df.columns:
            raise ValueError(f"TARGET MISSING: Column '{TARGET_COLUMN}' not found in data.")
        null_target = df[TARGET_COLUMN].isna()
        if null_target.any():
            bad_rows = df.loc[null_target, ["domain", TARGET_COLUMN]] if "domain" in df.columns else df.loc[null_target]
            raise ValueError(
                f"TARGET MISSING: {null_target.sum()} rows have null target. "
                f"Fix the training data. Rows:\n{bad_rows.to_string()}"
            )

    # -- Warn about unexpected extra columns --
    expected = set(RAW_INPUT_COLUMNS) | {TARGET_COLUMN, "domain", "Nombre", "clean_url",
                                          "instagram_url", "geography", "signals_used",
                                          "category", "currency"}
    extra = set(df.columns) - expected
    if extra:
        warnings.append(f"Extra columns ignored by model: {extra}")

    return warnings


def compute_derived_features(df: pd.DataFrame, usd_mask: pd.Series = None) -> pd.DataFrame:
    """
    Compute all derived features from raw enrichment data.

    Does NOT modify input DataFrame. Returns a copy with derived columns added.

    V4b derived features:
        - platform_group: collapsed platform (shopify/vtex/other)
        - has_meta_ads: 1 if meta_active_ads_count > 0
        - is_usd_origin: 1 if store was detected as USD-priced
        - log_ig_followers: log1p(ig_followers)
        - log_monthly_visits: log1p(estimated_monthly_visits)
        - log_product_count: log1p(product_count)
        - log_avg_price: log1p(avg_price) — after COP normalization
        - price_range_ratio: (max - min) / avg when avg > 0
        - company_age: 2026 - founded_year (capped at 30)
        - log_fb_followers: log1p(fb_followers)
        - log_tiktok_followers: log1p(tiktok_followers)
    """
    df = df.copy()

    # Platform grouping: Shopify, VTEX, other
    df["platform_group"] = df["platform"].map(
        lambda x: PLATFORM_GROUP_MAP.get(x, "other") if pd.notna(x) else "other"
    )

    # Binary flags (only has_meta_ads kept — others had zero importance)
    df["has_meta_ads"] = (df["meta_active_ads_count"].fillna(0) > 0).astype(int)

    # Currency origin flag
    if usd_mask is not None:
        df["is_usd_origin"] = usd_mask.astype(int)
    else:
        df["is_usd_origin"] = 0

    # Company age from founded_year (cap at 30 years)
    current_year = 2026
    df["company_age"] = np.where(
        df["founded_year"].notna() & (df["founded_year"] > 1900),
        np.minimum(current_year - df["founded_year"].fillna(0), 30),
        np.nan,
    )

    # Log transforms for skewed numerics
    df["log_ig_followers"] = np.log1p(df["ig_followers"].fillna(0))
    df["log_monthly_visits"] = np.log1p(df["estimated_monthly_visits"].fillna(0))
    df["log_product_count"] = np.log1p(df["product_count"].fillna(0))
    df["log_avg_price"] = np.log1p(df["avg_price"].fillna(0))
    df["log_fb_followers"] = np.log1p(df["fb_followers"].fillna(0))
    df["log_tiktok_followers"] = np.log1p(df["tiktok_followers"].fillna(0))

    # Price range ratio: (max - min) / avg — measures catalog price diversity
    df["price_range_ratio"] = np.where(
        df["avg_price"].notna() & (df["avg_price"] > 0),
        (df["price_range_max"].fillna(0) - df["price_range_min"].fillna(0)) / df["avg_price"],
        np.nan,
    )

    return df


def prepare_features(
    df: pd.DataFrame,
    require_target: bool = False,
) -> Tuple[pd.DataFrame, Optional[pd.Series], list[str]]:
    """
    Full feature preparation pipeline: validate, normalize, derive, select.

    Args:
        df: Raw enrichment data (from CSV or Google Sheets).
        require_target: If True, extract and return target series.

    Returns:
        (X, y, warnings) where:
            X: DataFrame with ALL_FEATURE_COLUMNS (15 columns)
            y: Target series (or None if require_target=False)
            warnings: List of warning messages from validation
    """
    # Convert string values to numeric for raw input columns
    numeric_cols = [c for c in RAW_INPUT_COLUMNS if c not in ("platform",)]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Normalize USD prices to COP (must happen before derived features)
    df, price_warnings, usd_mask = _normalize_prices(df)

    # Validate
    warnings = validate_input_schema(df, require_target=require_target)
    warnings.extend(price_warnings)

    # Derive features
    df = compute_derived_features(df, usd_mask=usd_mask)

    # Extract target if needed
    y = None
    if require_target:
        y = df[TARGET_COLUMN].astype(float)

    # Select only model feature columns
    X = df[ALL_FEATURE_COLUMNS].copy()

    # Ensure categorical columns are pandas category dtype (required by LightGBM)
    for cat_col in CATEGORICAL_FEATURES:
        X[cat_col] = X[cat_col].astype("category")

    return X, y, warnings
