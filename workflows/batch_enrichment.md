# Batch Enrichment Workflow

## Objective
Process e-commerce URLs in batch, running the full enrichment pipeline for each and persisting results to Google Sheets incrementally. Produces a training dataset with enrichment features + LLM-derived category.

## Required Inputs
- **urls**: List of raw URLs or brand names (may include duplicates, missing schemes, invalid entries)
- **spreadsheet_url** (optional): Existing Google Sheets URL to append results to. If omitted, a new sheet is created.

## Entry Points

### CLI (Primary for batch runs)
```bash
python tools/orchestrator/batch_runner.py urls.txt
python tools/orchestrator/batch_runner.py urls.txt --dry-run 5
python tools/orchestrator/batch_runner.py urls.txt --sheet "https://docs.google.com/..." --batch-id my-run
python tools/orchestrator/batch_runner.py urls.txt --no-demand  # skip Google Demand scoring
```

### API (Backend)
- `POST /api/batch` — submit batch, returns batch_id + sheet_url immediately
- `GET /api/batch/{batch_id}/status` — poll processing counters

## Tools Used (in order, per URL)

### Pipeline Steps (tools/orchestrator/run_enrichment.py)
| Step | Tool | Fields Populated |
|------|------|-----------------|
| 0. Resolve | `tools/core/resolve_brand_url.py` | (intermediate) |
| 1. Normalize | `tools/core/url_normalizer.py` | clean_url, domain |
| 2. Scrape | `tools/core/web_scraper.py` | (intermediate: HTML for all passive tools) |
| 3. Platform | `tools/detection/detect_ecommerce_platform.py` | platform, platform_confidence |
| 4. Geography | `tools/detection/detect_geography.py` | geography, geography_confidence |
| 5. Social Links | `tools/social/extract_social_links.py` | instagram_url |
| 6. Instagram | `tools/social/apify_instagram.py` + `tools/scoring/instagram_scoring.py` | ig_followers, ig_engagement_rate, ig_size_score, ig_health_score |
| 7. Catalog | `tools/ecommerce/scrape_product_catalog.py` | product_count, avg_price, price_range_min, price_range_max, currency |
| 8. Traffic | `tools/traffic/estimate_traffic.py` | estimated_monthly_visits, traffic_confidence, signals_used |
| 9. Google Demand | `tools/google_demand/score_demand.py` | brand_demand_score, site_serp_coverage_score, google_confidence |
| 10. Fulfillment | `tools/detection/detect_fulfillment_provider.py` (passive only) | fulfillment_provider, fulfillment_confidence |
| 11. Category | `tools/ai/classify_category.py` (Claude 3.5 Sonnet, tool_use) | category, category_confidence, category_evidence |
| 12. Apollo | `tools/contacts/apollo_enrichment.py` (OFF by default) | contact_name, contact_email, company_linkedin |

### Supporting Tools
- `tools/core/cache_manager.py` — 7-day TTL file cache per domain per tool
- `tools/models/enrichment_result.py` — canonical output schema (EnrichmentResult dataclass)
- `tools/export/google_sheets_writer.py` — Google Sheets write + resume support
- `tools/core/input_reader.py` — read and deduplicate plain text URL lists

## Output Schema (36 columns)
Defined in `tools/models/enrichment_result.py` (SHEET_HEADERS — single source of truth).

| Group | Columns |
|-------|---------|
| Identity | run_id, batch_id, clean_url, domain |
| Platform | platform, platform_confidence |
| Geography | geography, geography_confidence |
| Category (LLM) | category, category_confidence, category_evidence |
| Social | instagram_url, ig_followers, ig_engagement_rate, ig_size_score, ig_health_score |
| Catalog | product_count, avg_price, price_range_min, price_range_max, currency |
| Traffic | estimated_monthly_visits, traffic_confidence, signals_used |
| Google Demand | brand_demand_score, site_serp_coverage_score, google_confidence |
| Fulfillment | fulfillment_provider, fulfillment_confidence |
| Apollo | contact_name, contact_email, company_linkedin |
| Execution Meta | tool_coverage_pct, total_runtime_sec, cost_estimate_usd, workflow_execution_log |

### Category Classification
- **Model**: Claude 3.5 Sonnet via Anthropic API
- **Method**: tool_use (structured output) with enum constraint
- **23 Allowed Categories**: Accesorios, Alimentos, Alimentos refrigerados, Autopartes, Bebidas, Cosmeticos-belleza, Deporte, Electrónicos, Farmacéutica, Hogar, Infantiles y Bebés, Joyeria/Bisuteria, Juguetes, Juguetes Sexuales, Libros, Mascotas, Papeleria, Ropa, Salud y Bienestar, Suplementos, Tecnología, Textil Hogar, Zapatos
- **Inputs to LLM**: domain, meta title/description/H1, up to 20 product titles, IG bio+name
- **Fallback**: empty string if classification fails (never blocks batch)

### Google Demand Scoring
- **3 Serper queries per company**:
  - Q1: `"{brand_name}"` — brand organic presence (knowledge graph, top 10 results)
  - Q2: `"{brand_name} reviews opiniones"` — social proof signals
  - Q3: `"site:{domain}"` — indexed pages count
- **brand_demand_score** = 0.5 * brand_presence + 0.5 * social_proof (0-1)
- **site_serp_coverage_score** = normalized indexed page count (0-1)

## Processing Rules
- URLs are processed **serially** (one at a time) to avoid rate limiting
- Results are flushed to Google Sheets every **10 URLs**
- Processing continues even if individual URLs fail
- Failed URLs still produce a row (nulls + error in workflow_execution_log)
- **Cache check** runs before each tool — 7-day TTL
- **Resume from sheet**: on restart, reads existing domains from sheet and skips them
- **Fulfillment**: passive-only in batch mode (no Playwright checkout flow)
- **Apollo**: OFF by default (fields stay null)

## Error Handling
- **Empty/whitespace URLs**: skipped during deduplication
- **Duplicate domains**: deduplicated (first occurrence wins)
- **Invalid URLs**: kept in batch — fail gracefully, produce row with nulls + error log
- **Scrape failures**: downstream passive tools skipped; error captured in workflow log
- **Individual step failures**: that step's fields are null, other steps continue
- **API key missing** (Anthropic, Serper, Apify): tool returns error, fields stay null
- **LLM failures**: category set to empty string, reason logged
- **Sheets write failures**: buffer lost (max 9 rows), processing continues
- **Fatal errors**: captured in workflow_execution_log, batch continues to next URL

## Caching Strategy
- Cache stored in `.tmp/cache/{domain}/{tool_name}.json`
- Default TTL: 7 days
- Cache keys per tool: `web_scraper`, `detect_platform`, `detect_geography`, `social_links`, `apify_instagram`, `product_catalog`, `traffic`, `google_demand`, `fulfillment`, `classify_category`
- Cache is checked before each tool runs to save API credits
- Cache can be cleared per-domain or globally via `cache_manager.py`

## Persistence & Limitations
- **No database** — Google Sheets is the only persistent storage
- Worst-case data loss on crash: last 0-9 URLs not yet flushed to Sheets
- Resume-safe: restart picks up where it left off by reading sheet domains
- Each row has run_id (UUID per company) + batch_id (shared per run)

## Rate Limits to Watch
- **Serper API**: 2,500 queries/month free tier. Google Demand uses 3 queries/company. Budget: ~800 companies/month with demand ON
- **Apify Instagram**: each profile fetch ~30-120s, costs credits. Only called when IG link found
- **Anthropic API**: ~500 tokens/call for category classification. ~$0.30 total for 400 companies
- **Apollo.io**: 10,000 credits/month free tier (OFF by default in batch)
- **Google Sheets API**: 100 requests per 100 seconds (10-row buffer stays well within)
- **Target websites**: natural delay between serial requests avoids anti-bot triggers

## Environment Variables Required
- `GOOGLE_SERVICE_ACCOUNT_JSON` — raw JSON string for Google service account
- `SERPER_API_KEY` — for brand resolution + Google Demand scoring
- `APIFY_API_TOKEN` — for Instagram metrics
- `ANTHROPIC_API_KEY` — for LLM category classification
- `APOLLO_API_KEY` (optional) — for contact enrichment
- `SIMILARWEB_API_KEY` (optional) — for traffic estimation
- `PLAYWRIGHT_HEADLESS` (optional, default: true) — for browser-based fulfillment detection
