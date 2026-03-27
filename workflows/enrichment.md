# Enrichment Workflow

## Objective
Analyze e-commerce companies — from URL or brand name — through a 14-step pipeline that detects platform, geography, social presence, catalog, traffic, demand, fulfillment, and category. Ends with an orders prediction (P10/P50/P90) and writes results to Google Sheets.

## Entry Points

### Frontend (Single Company)
SSE streaming endpoint: `POST /api/v2/enrichment/analyze-stream`
- Runs full pipeline + orders prediction + writes to Sheet V2
- Streams step-by-step progress to the frontend

### CLI — Single Company
```bash
cd tools && python -m orchestrator.run_enrichment "armatura.com.co"
```

### CLI — Batch
```bash
python run_batch.py urls.txt
python run_batch.py urls.txt --dry-run 3
python run_batch.py urls.txt --sheet "https://docs.google.com/..." --country Colombia
```
Or directly:
```bash
python tools/orchestrator/batch_runner.py urls.txt --sheet URL --batch-id my-run
```

## Pipeline Steps (tools/orchestrator/run_enrichment.py)

| # | Step | Tool | Fields Populated |
|---|------|------|-----------------|
| 0 | Resolve | `core/resolve_brand_url.py` | (intermediate — resolved URL) |
| 1 | Normalize | `core/url_normalizer.py` | clean_url, domain |
| 2 | Scrape | `core/web_scraper.py` | (intermediate — HTML for passive tools) |
| 3 | Platform | `detection/detect_ecommerce_platform.py` | platform, platform_confidence |
| 4 | Geography | `detection/detect_geography.py` | geography, geography_confidence |
| 5a | Social Links | `social/extract_social_links.py` | instagram_url |
| 5b | Instagram | `social/apify_instagram.py` + `scoring/instagram_scoring.py` | ig_followers, ig_engagement_rate, ig_size_score, ig_health_score |
| 6 | META Ads | `social/apify_meta_ads.py` | meta_active_ads_count |
| 7 | Catalog | `ecommerce/scrape_product_catalog.py` | product_count, avg_price, price_range_min/max, currency |
| 8 | Traffic | `traffic/estimate_traffic.py` | estimated_monthly_visits, traffic_confidence, signals_used |
| 9 | Google Demand | `google_demand/score_demand.py` (3 Serper queries) | brand_demand_score, site_serp_coverage_score, google_confidence |
| 10 | Fulfillment | `detection/detect_fulfillment_provider.py` (passive) | fulfillment_provider, fulfillment_confidence |
| 11 | Category | `ai/classify_category.py` (Claude Sonnet, tool_use) | category, category_confidence, category_evidence, company_name |
| 12 | Apollo | `contacts/apollo_enrichment.py` (OFF by default in batch) | contact_name, contact_email, company_linkedin, number_employes |
| 12b | Geo Reconcile | (inline in orchestrator) | geography, geography_confidence (fallback when HTML detection fails) |
| 13 | HubSpot | `hubspot/hubspot_lookup.py` (ON by default) | hubspot_company_id, hubspot_company_url, hubspot_deal_count, hubspot_deal_stage, hubspot_contact_exists |

**Geography reconciliation** (Step 12b): Fires only when geography is UNKNOWN. Uses fallback signals in priority order: (1) explicit `country` parameter, (2) Apollo company country, (3) catalog currency (COP→COL, MXN→MEX), (4) domain TLD.

**Apollo contact search**: Uses bilingual titles (English + Spanish) and retries with seniority-based filter (owner/founder/c_suite/vp/director) when title search returns 0 results.

**HubSpot CRM lookup** (Step 13): Checks if the enriched company already exists in HubSpot CRM. Uses `domain` from Step 1 to search companies (EQ match, then fallback to `hs_additional_domains` CONTAINS_TOKEN). If found, fetches associated deals and their stages. Also checks if `contact_email` from Apollo exists as a HubSpot contact. Controlled via `skip_hubspot` parameter (default: False). Requires `HUBSPOT_TOKEN` and `HUBSPOT_PORTAL_ID` in `.env`.

**Post-pipeline** (API endpoint and batch CLI):
| Step | Tool | Fields |
|------|------|--------|
| Prediction | `orders_estimator/predict.py` (LightGBM) | predicted_orders_p10/p50/p90, prediction_confidence |
| Export | `export/google_sheets_writer.py` | Row appended to Google Sheet |

## Output Schema

Canonical schema: `tools/models/enrichment_result.py` (SHEET_HEADERS — 39 columns).

| Group | Columns |
|-------|---------|
| Identity | run_id, batch_id, clean_url, domain, company_name |
| Platform | platform, platform_confidence |
| Geography | geography, geography_confidence |
| Category | category, category_confidence, category_evidence |
| Social | instagram_url, ig_followers, ig_engagement_rate, ig_size_score, ig_health_score |
| Catalog | product_count, avg_price, price_range_min, price_range_max, currency |
| Traffic | estimated_monthly_visits, traffic_confidence, signals_used |
| Google Demand | brand_demand_score, site_serp_coverage_score, google_confidence |
| Fulfillment | fulfillment_provider, fulfillment_confidence |
| META Ads | meta_active_ads_count |
| Apollo | contact_name, contact_email, company_linkedin, number_employes |
| Execution | tool_coverage_pct, total_runtime_sec, cost_estimate_usd, workflow_execution_log |

## Orders Estimation

### Model
- **Backend**: LightGBM quantile regression (P10, P50, P90)
- **Features**: 25 (14 raw + 11 derived) — platform, category, IG metrics, META ads, catalog, traffic, demand, employees
- **Training data**: ~142 Colombia stores with ops ground truth
- **Performance**: WAPE 0.80, Bucket accuracy (±1 tier) 88%

### Ops Interpretation
- **P50**: Capacity planning and headcount allocation
- **P90**: Warehouse space and peak planning
- **P10**: Minimum guaranteed volume
- **confidence = "low"**: Flag for manual review

### Order Tiers
| Tier | Monthly Orders |
|------|---------------|
| Micro | 0–50 |
| Small | 51–300 |
| Medium | 301–1,500 |
| Large | 1,501–5,000 |
| Enterprise | 5,001+ |

### Confidence Flags
- **high**: catalog + Instagram + traffic + META ads
- **medium**: Instagram + traffic
- **low**: missing key signals

### Retraining
Quarterly when Melonn provides updated ground truth. CLI:
```bash
python -m tools.orders_estimator.cli train "training_data.csv"
python -m tools.orders_estimator.cli evaluate "training_data.csv"
```
Artifacts saved to `.tmp/orders_estimator/models/`.

## Processing Rules
- URLs processed **serially** (avoids rate limits)
- Results flushed to Sheets every **10 URLs**
- Failed URLs produce a row with nulls + error in workflow_execution_log
- **7-day cache** per domain per tool (saves API credits)
- **Resume from sheet**: reads existing domains, skips them
- **Apollo**: OFF by default in batch (saves credits)
- **Fulfillment**: passive HTML detection only (no Playwright)

## Error Handling
- Pipeline **never crashes** — all errors caught, fields stay None
- Individual step failures don't block other steps
- Worst-case data loss: last 0-9 URLs not yet flushed

## Rate Limits
| API | Limit | Notes |
|-----|-------|-------|
| SearchAPI | Plan-based credits | Google Search/Maps/Shopping, Meta Ads, TikTok Ads |
| Apify Instagram | Credits-based | ~$0.10/profile, only when IG found |
| Apify META Ads | Credits-based | ~$0.05-0.20/search |
| Anthropic | Token-based | ~$0.01/classification |
| Apollo | 10K credits/month free | OFF by default |
| Google Sheets | 100 req/100s | 10-row buffer is safe |

## Environment Variables
- `SEARCHAPI_API_KEY` — Google Search, Google Maps, Meta Ads, TikTok Ads, Google Shopping
- `APIFY_API_TOKEN` — Instagram scraping
- `ANTHROPIC_API_KEY` — category classification
- `GOOGLE_SERVICE_ACCOUNT_JSON` — Google Sheets auth
- `APOLLO_API_KEY` (optional) — contact enrichment
- `SHEET_V2_URL` (optional) — pre-existing Sheet V2 URL

## Known Limitations
- Orders model is **Colombia-only** — do not use for Mexico
- ~142 training samples — high variance on rare categories
- Non-Shopify stores lack catalog features (~30% of data)
- Traffic estimation is indirect (no SimilarWeb API in free tier)
