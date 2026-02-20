# Orders Estimation Workflow

## Objective
Predict monthly order volume (P10/P50/P90) for Melonn ecommerce stores in Colombia using enrichment features. Output is used by ops for logistics capacity planning.

## Model Details
- **Backend**: LightGBM quantile regression
- **Target**: `Monthly_orderts` (log1p-transformed)
- **Features**: 22 (13 raw + 9 derived) — platform, category, Instagram metrics, product catalog, traffic, demand, employee count
- **Sample weighting**: `log1p(orders) + 1` — big stores matter more
- **Training data**: ~142 Colombia stores with exact ops ground truth

## v1 Performance (Cross-Validation)
| Metric | Value |
|---|---|
| WAPE | 0.80 (baseline naive: 0.93) |
| Spearman rho | 0.56 |
| Bucket accuracy (exact) | 41% |
| Bucket accuracy (±1 tier) | 88% |
| R² | 0.13 |

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
python -m tools.orders_estimator.cli train "Traning data algorith order estimation V2.csv"

# Force retrain even if data unchanged
python -m tools.orders_estimator.cli train "Traning data algorith order estimation V2.csv" --force

# Skip hyperparameter sweep (faster, uses defaults)
python -m tools.orders_estimator.cli train "Traning data algorith order estimation V2.csv" --skip-sweep

# Evaluate only (no model saved)
python -m tools.orders_estimator.cli evaluate "Traning data algorith order estimation V2.csv"

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
- **high**: Has catalog data + Instagram + traffic (typically Shopify stores)
- **medium**: Has Instagram + traffic (non-Shopify with social presence)
- **low**: Missing key signals

## Guardrails
- **No LLM inside the estimator** — LLM only for upstream enrichment (category classification)
- **Fail loud on missing target** — `ValueError` with row-level detail, never drops rows silently
- **Fail loud on missing model** — clear error message directing to `cli.py train`
- **Schema validation** — rejects unknown categories, maps unknown platforms to "other"
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

## Known Limitations
- ~142 training samples — high variance on rare categories
- Non-Shopify stores lack catalog features (~30% of data) → lower accuracy
- Model is **Colombia-only** — do NOT use for Mexico stores
- Overfitting risk detected (34% train/CV gap) — monitor on retraining
- Top features: price_range_min, number_employes, ig_followers, product_count, estimated_monthly_visits

## Dependencies
```
lightgbm>=4.0.0
scikit-learn>=1.4.0
scipy>=1.12.0
numpy>=1.26.0
pandas>=2.2.0
```
