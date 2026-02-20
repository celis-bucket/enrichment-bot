"""
Feature engineering and schema validation for the Orders Estimator.

Handles:
- Input schema validation (hard fail on missing required columns, soft warn on extras)
- Derived feature computation (missing indicators, log transforms, ratios)
- Full feature preparation pipeline
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional

from .config import (
    RAW_FEATURE_COLUMNS,
    DERIVED_FEATURE_COLUMNS,
    ALL_FEATURE_COLUMNS,
    CATEGORICAL_FEATURES,
    TARGET_COLUMN,
    ALLOWED_PLATFORMS,
    ALLOWED_CATEGORIES,
)

# ---------------------------------------------------------------------------
# Currency normalization constants
# ---------------------------------------------------------------------------
USD_COP_RATE = 4_200   # approximate USD → COP conversion rate
USD_THRESHOLD = 500     # avg_price below this → detected as USD (clean gap in data)


def _normalize_prices(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Detect and convert USD prices to COP.

    17/142 training stores have prices in USD instead of COP. This creates
    a massive feature-space gap (USD $50 vs COP 50,000) that LightGBM
    exploits as a dominant split, inflating price feature importance.

    Detection: avg_price < 500 → USD (robust threshold: clean gap at 500-700,
    no stores in that range, COP starts at 5,000+).

    Converts avg_price, price_range_min, price_range_max to COP.
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

    return df, warnings


def validate_input_schema(
    df: pd.DataFrame,
    require_target: bool = False,
) -> list[str]:
    """
    Validate input DataFrame against the frozen feature schema.

    Args:
        df: Input DataFrame (training or prediction data).
        require_target: If True, assert TARGET_COLUMN is present and non-null.

    Returns:
        List of warning messages (empty if all OK).

    Raises:
        ValueError: If required columns are missing, category values are invalid,
                    or target is missing/null when required.
    """
    warnings: list[str] = []

    # -- Required columns --
    required = ["platform", "category"]
    missing_required = [c for c in required if c not in df.columns]
    if missing_required:
        raise ValueError(f"Missing required columns: {missing_required}")

    # -- Check all raw feature columns exist --
    missing_features = [c for c in RAW_FEATURE_COLUMNS if c not in df.columns]
    if missing_features:
        warnings.append(f"Missing feature columns (will be treated as NaN): {missing_features}")
        for col in missing_features:
            df[col] = np.nan

    # -- Validate platform values --
    known_platforms = set(ALLOWED_PLATFORMS)
    unknown_platforms = set(df["platform"].dropna().unique()) - known_platforms
    if unknown_platforms:
        warnings.append(f"Unknown platforms mapped to 'other': {unknown_platforms}")
        df.loc[~df["platform"].isin(known_platforms) & df["platform"].notna(), "platform"] = "other"

    # -- Validate category values --
    known_categories = set(ALLOWED_CATEGORIES)
    if df["category"].isna().any():
        raise ValueError(
            f"NULL category found in {df['category'].isna().sum()} rows. "
            "Category is required for all stores."
        )
    unknown_categories = set(df["category"].unique()) - known_categories
    if unknown_categories:
        raise ValueError(
            f"Unknown categories found: {unknown_categories}. "
            f"Allowed: {sorted(known_categories)}"
        )

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
    expected = set(RAW_FEATURE_COLUMNS) | {TARGET_COLUMN, "domain", "Nombre", "clean_url",
                                            "instagram_url", "geography", "signals_used"}
    extra = set(df.columns) - expected
    if extra:
        warnings.append(f"Extra columns ignored by model: {extra}")

    return warnings


def compute_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all derived features from raw enrichment data.

    Does NOT modify input DataFrame. Returns a copy with derived columns added.

    Derived features:
        - has_catalog: 1 if product_count is not null
        - has_instagram: 1 if ig_followers is not null
        - has_employees_data: 1 if number_employes is not null
        - log_ig_followers: log1p(ig_followers)
        - log_monthly_visits: log1p(estimated_monthly_visits)
        - log_product_count: log1p(product_count)
        - log_avg_price: log1p(avg_price)
        - log_number_employes: log1p(number_employes)
        - price_range_ratio: (max - min) / avg when avg > 0
    """
    df = df.copy()

    # Missing indicators (binary flags)
    df["has_catalog"] = df["product_count"].notna().astype(int)
    df["has_instagram"] = df["ig_followers"].notna().astype(int)
    df["has_employees_data"] = df["number_employes"].notna().astype(int)

    # Log transforms for skewed numerics (fillna(0) before log so log1p(0)=0)
    df["log_ig_followers"] = np.log1p(df["ig_followers"].fillna(0))
    df["log_monthly_visits"] = np.log1p(df["estimated_monthly_visits"].fillna(0))
    df["log_product_count"] = np.log1p(df["product_count"].fillna(0))
    df["log_avg_price"] = np.log1p(df["avg_price"].fillna(0))
    df["log_number_employes"] = np.log1p(df["number_employes"].fillna(0))

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
    Full feature preparation pipeline: validate, derive, select.

    Args:
        df: Raw enrichment data (from CSV or Google Sheets).
        require_target: If True, extract and return target series.

    Returns:
        (X, y, warnings) where:
            X: DataFrame with ALL_FEATURE_COLUMNS
            y: Target series (or None if require_target=False)
            warnings: List of warning messages from validation
    """
    # Convert "NA" strings to NaN for numeric columns
    numeric_cols = [c for c in RAW_FEATURE_COLUMNS if c not in CATEGORICAL_FEATURES]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Normalize USD prices to COP (must happen before validation/derived features)
    df, price_warnings = _normalize_prices(df)

    # Validate
    warnings = validate_input_schema(df, require_target=require_target)
    warnings.extend(price_warnings)

    # Derive features
    df = compute_derived_features(df)

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
