> **DEPRECATED**: This workflow has been merged into [enrichment.md](enrichment.md). This file is kept for reference only.

# Orders Estimation Workflow

## Objective
Predict monthly order volume (P10/P50/P90) for Melonn ecommerce stores in Colombia using enrichment features. Output is used by ops for logistics capacity planning.

## Model Details
- **Backend**: LightGBM quantile regression
- **Target**: `Monthly_orderts` (log1p-transformed)
- **Features**: 15 (7 raw + 8 derived) — Instagram metrics, META ads count, catalog (log-scale), traffic, demand, SERP coverage, employee count, platform group
- **Sample weighting**: `log1p(orders) + 1` — big stores matter more
- **Training data**: ~142 Colombia stores with exact ops ground truth

## v4 Performance (Cross-Validation, 2026-03-16)
| Metric | Value |
|---|---|
| WAPE | 0.751 (baseline naive: 0.929) |
| Spearman rho | 0.664 |
| Bucket accuracy (exact) | 44.6% |
| Bucket accuracy (±1 tier) | 91.8% |
| MdAE | 269 |
| R² | 0.164 |

### Changes from v3 (feature engineering overhaul)
- **Reduced features 27 -> 15** to improve sample/feature ratio (5.3:1 -> 9.5:1)
- **Removed raw price features** (`avg_price`, `price_range_min`, `price_range_max`) — were dominating importance via currency artifact (USD/COP), not predictive signal. Replaced by `log_avg_price` + `price_range_ratio`
- **Added `is_usd_origin`** binary flag — explicit marker for stores with USD prices
- **Added `platform_group`** (shopify/vtex/other) — collapsed from 7 to 3 levels; now has importance 1,001 (was 0 in V3)
- **Removed `category`** from model — 23 levels with ~6 samples each, zero importance
- **Removed redundant features**: binary flags (has_catalog, has_instagram, etc.), duplicate log/raw pairs
- **Ablation study validated**: dropping price features costs 0 WAPE but improves Spearman +4%, bucket accuracy +2.4pp
- Best hyperparams: learning_rate=0.1, max_depth=3, reg_lambda=20
- Top features: ig_engagement_rate, price_range_ratio, meta_active_ads_count, number_employes, log_avg_price

### Changes from v2 (v3)
- Fixed critical bug in `backfill_meta_ads.py`: was passing full Instagram URLs to Meta Ad Library API
- `meta_active_ads_count` now 86% non-zero (was ~20% before fix)
- Cleaned contaminated rows (social platform domains)

### Changes from v1 (v2)
- Added `meta_active_ads_count` to training data (backfilled via SearchAPI Meta Ad Library)
- Added `site_serp_coverage_score` to feature schema
- Training data: 142 Colombia stores

## Required Inputs

### For Training
- CSV with enrichment features + `Monthly_orderts (target)` column
- Must include: `platform`, `category` (required), all other features optional

### For Prediction
- CSV or Google Sheet with enrichment features
- OR enrichment Google Sheet URL with `--sheet` flag

## Entry Points (CLI)

```bash
# Train models from labeled data
python -m tools.orders_estimator.cli train "Traning data algorith order estimation V3.csv"

# Force retrain even if data unchanged
python -m tools.orders_estimator.cli train "Traning data algorith order estimation V3.csv" --force

# Skip hyperparameter sweep (faster, uses defaults)
python -m tools.orders_estimator.cli train "Traning data algorith order estimation V3.csv" --skip-sweep

# Evaluate only (no model saved)
python -m tools.orders_estimator.cli evaluate "Traning data algorith order estimation V3.csv"

# Predict from CSV, save to local file
python -m tools.orders_estimator.cli predict enrichment.csv --output-csv predictions.csv

# Predict from Google Sheet and write predictions back
python -m tools.orders_estimator.cli predict --sheet "https://docs.google.com/..." --worksheet "results"
```

## Tools Used
| Tool | File | Purpose |
|---|---|---|
| config | `tools/orders_estimator/config.py` | Schema, parameters, bucket definitions |
| features | `tools/orders_estimator/features.py` | Schema validation, derived features |
| train | `tools/orders_estimator/train.py` | Full training pipeline |
| predict | `tools/orders_estimator/predict.py` | Load models, batch prediction |
| evaluate | `tools/orders_estimator/evaluate.py` | Metrics, cross-validation, leakage checks |
| export | `tools/orders_estimator/export_predictions.py` | Google Sheets prediction export |
| cli | `tools/orders_estimator/cli.py` | CLI entry point |
| google_sheets_writer | `tools/export/google_sheets_writer.py` | Shared Google Sheets auth/write |
| backfill_meta_ads | `tools/orders_estimator/backfill_meta_ads.py` | Backfill META ads count for training data |
| backfill_serp_coverage | `tools/orders_estimator/backfill_serp_coverage.py` | Backfill SERP coverage + demand scores for training data |

## Output Columns
| Column | Type | Description |
|---|---|---|
| `predicted_orders_p50` | int | Median predicted monthly orders |
| `predicted_orders_p10` | int | Conservative estimate (10th percentile) |
| `predicted_orders_p90` | int | Optimistic estimate (90th percentile) |
| `prediction_confidence` | str | "high" / "medium" / "low" |
| `model_version` | str | Model version identifier |

## Ops Interpretation
- **P50**: Use for capacity planning and headcount allocation
- **P90**: Use for warehouse space and peak planning (over-prepare to this level)
- **P10**: Use for minimum guaranteed volume commitments
- **confidence = "low"**: Rough estimate only — flag for manual review
- **P50 = 0**: Model sees no order signal — manual review required

## Order Tiers
| Tier | Monthly Orders |
|---|---|
| Micro | 0–50 |
| Small | 51–300 |
| Medium | 301–1,500 |
| Large | 1,501–5,000 |
| Enterprise | 5,001+ |

## Confidence Flags
- **high**: Has catalog data + Instagram + traffic + META ads data (typically Shopify stores with ad presence)
- **medium**: Has Instagram + traffic (non-Shopify with social presence)
- **low**: Missing key signals

## Guardrails
- **No LLM inside the estimator** — LLM only for upstream enrichment (category classification)
- **Fail loud on missing target** — `ValueError` with row-level detail, never drops rows silently
- **Fail loud on missing model** — clear error message directing to `cli.py train`
- **Schema validation** — maps unknown platforms to "other", collapses to platform_group (shopify/vtex/other)
- **Caps extreme predictions** — P50 > 2x max training target gets capped + warning
- **Zero-prediction alert** — if >80% predictions are zero, logs CRITICAL warning

## Saved Artifacts
After training, saved to `.tmp/orders_estimator/models/`:
- `model_p10.txt`, `model_p50.txt`, `model_p90.txt` — LightGBM model files
- `feature_schema.json` — frozen feature schema
- `training_meta.json` — training metadata, metrics, params
- `feature_importance.json` — feature importance ranking

## Retraining Schedule
- **Quarterly** when Melonn provides updated Monthly_orderts ground truth
- Run `train` → compare WAPE to previous version → verify no degradation
- Training data snapshots saved to `.tmp/orders_estimator/datasets/` with SHA-256 hash

### Backfill Procedure (before retraining)
1. Backfill META ads: `python -m tools.orders_estimator.backfill_meta_ads --delay 2`
   - Cost: ~175 SearchAPI calls. Fill empty cells with 0 after (no result = no ads).
2. Backfill SERP coverage: `python -m tools.orders_estimator.backfill_serp_coverage --delay 2`
   - Cost: 3 Serper queries per store (free tier: 2,500/month)
3. Export sheet to CSV, merge target column from previous training CSV
4. Retrain: `python tools/orders_estimator/cli.py train "V3.csv" --force`

## Known Limitations
- ~142 training samples — high variance on rare categories
- Non-Shopify stores lack catalog features (~30% of data) → lower accuracy
- Model is **Colombia-only** — do NOT use for Mexico stores
- Overfitting risk detected (46% train/CV gap in v4, down from 52% in v3) — improving with fewer features
- Top features (v4): ig_engagement_rate, price_range_ratio, meta_active_ads_count, number_employes, log_avg_price, platform_group, log_monthly_visits, log_product_count, ig_health_score, log_ig_followers
- All 15 features have non-zero importance (unlike v3 where 6/27 had zero)
- `site_serp_coverage_score` has low importance due to low variance (75% of values are 0.386) — will improve after full re-enrichment
- `is_usd_origin` and `brand_demand_score` are lowest-ranked but retained for signal diversity
- `ig_health_score` scoring formula may be too harsh for large accounts (see enrichment.md) — planned for future iteration

## Dependencies
```
lightgbm>=4.0.0
scikit-learn>=1.4.0
scipy>=1.12.0
numpy>=1.26.0
pandas>=2.2.0
```
