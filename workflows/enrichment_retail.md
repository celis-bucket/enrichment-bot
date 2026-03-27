# Workflow: Retail Channel Enrichment

## Objective
Detect if an e-commerce brand sells through physical/retail channels in Mexico and Colombia. Evaluates 4 retail channels + 3 supplementary signals, producing binary flags and structured data per channel.

## Entry Points

### Single domain (CLI)
```bash
python -m tools.retail.run_retail_enrichment "armatura.com.co"
```

### Batch (all pending domains)
```bash
python -m tools.retail.run_retail_enrichment --batch
python -m tools.retail.run_retail_enrichment --batch --limit 50
```

### Programmatic (from main pipeline)
```python
from retail.run_retail_enrichment import run_retail_enrichment
result = run_retail_enrichment(
    domain="armatura.com.co",
    brand_name="Armatura",
    html=html,                  # reuse from step 2
    geography="COL",            # from step 4
    category="Cosmeticos-belleza",  # from step 12
    ig_bio=ig_bio,              # from step 6
    knowledge_graph=kg_data,    # from step 10
)
```

## Required Inputs
| Input | Required | Source |
|-------|----------|--------|
| `domain` | Yes | URL normalization (step 1) |
| `brand_name` | Yes | Category classification (step 12) or domain extraction |
| `html` | No (auto-scraped) | Web scraper (step 2) |
| `geography` | No | Geography detection (step 4) |
| `category` | No | Category classification (step 12) |
| `ig_bio` | No | Instagram metrics (step 6) |
| `knowledge_graph` | No | Google Demand scoring (step 10) |

## Pipeline Steps

| Step | Channel | Tool | API Queries | Output |
|------|---------|------|-------------|--------|
| R0 | — | `web_scraper` (cached) | 0 | HTML for all subsequent steps |
| R0.5 | Shopping | `google_shopping_sellers` | 1 SearchAPI | Sellers classified: multibrand, marketplace, other |
| R1 | Distribuidores | `detect_distributors` | 0-1 Serper | `has_distributors: bool` |
| R2 | Tiendas Propias | `detect_own_stores` | 1-2 Serper (Places) | `has_own_stores: bool`, `own_store_count_col: int`, `own_store_count_mex: int` |
| R3 | Tiendas Multimarca | `detect_multibrand_stores` | 0 | `has_multibrand_stores: bool`, `multibrand_store_names: list` |
| R4 | Marketplaces | `detect_marketplaces` | 0-7 Serper (skips if Shopping found) | COL: `on_mercadolibre`, `on_amazon`, `on_rappi`; MEX: `on_mercadolibre`, `on_amazon`, `on_walmart`, `on_liverpool`, `on_coppel`, `on_tiktok_shop` |

**Total queries per brand**: 1 SearchAPI + 1-5 Serper (average ~4, down from ~6)

### R0.5: Google Shopping Sellers
Uses SearchAPI `engine=google_shopping` to find who sells the brand's products. One query returns up to 40 product listings with seller names. Sellers are classified as:
- **Marketplace**: MercadoLibre, Amazon, Rappi, Linio, Dafiti → feeds R4
- **Multibrand store**: matched against `retail_department_stores` vocabulary → feeds R3
- **Self**: the brand's own store → skipped
- **Other retailers**: unclassified stores (saved as supplementary info)

## Detection Heuristics

### R1: Distribuidores/Mayoristas
1. **HTML scan**: Look for links containing "distribuidor", "mayorista", "donde comprar", "inicia tu negocio", "wholesale", etc.
2. **Page confirmation**: If candidate link found, scrape the page and check for forms, "pedido mínimo", "precio mayorista" patterns.
3. **Google fallback**: `"{brand}" "distribuidor" OR "donde comprar" OR "mayorista"` — check if results point back to brand domain.

### R2: Tiendas Propias
1. **HTML scan**: Find store locator links ("tiendas", "sucursales", "store-locator", "ubicaciones").
2. **Store count**: Scrape the store locator page, count addresses/locations using address regex + city name matching (separate COL/MEX lists).
3. **Serper Places**: `"{brand}" tienda` with country filter — returns physical locations with addresses.
4. **Google Business Profile**: Check knowledge graph for physical address or store type.
5. **IG bio**: Check for "tienda física", "sucursales", "visítanos en".

### R3: Tiendas Multimarca
1. **Brand website**: Find "donde comprar"/"tiendas autorizadas" page → extract store names from text, image alt text, image filenames → match against controlled vocabulary in Supabase.
2. **Homepage logos**: Some brands show retail partner logos on their homepage.
3. **Supabase DB**: Fuzzy brand matching against `retail_store_brands` via cascade (see below).
4. **IG bio**: Check for mentions of known department store names.

**Controlled vocabulary**: `retail_department_stores` table in Supabase, seeded with major stores for COL and MEX.

#### Fuzzy Brand Matching (Source 3)
Brand names vary across sources (domain, LLM extraction, store APIs, Apollo). The matching uses a cascade in `tools/retail/fuzzy_brand_match.py`:

| Stage | Strategy | Example | Min name length |
|-------|----------|---------|-----------------|
| 1 | Exact on normalized name | "savvy" = "savvy" | any |
| 2 | Exact on candidate variants (domain, IG, Apollo, stripped suffixes) | "armatura" from "armatura colombia" | any |
| 3a | Token containment (subset of words) | "beauty boost" ⊆ "beauty boost colombia" | 2+ words |
| 3b | Substring containment | "savvy" in "youaresavvy" | 5+ chars, DB brand >= 4 chars, ratio >= 40% |
| 4 | Fuzzy (`rapidfuzz.token_set_ratio` >= 85) | "loreal" ~ "l oreal" | 5+ chars |

**False positive protection**: Names with <= 3 chars only use Stage 1. Names with <= 4 chars skip Stages 3b and 4. Substring match requires the shorter name to be >= 40% of the longer name's length.

### R4: Marketplaces
Marketplaces vary by geography:
- **COL**: MercadoLibre, Amazon, Rappi
- **MEX**: MercadoLibre, Amazon, Walmart, Liverpool, Coppel, TikTok Shop

1. **HTML links**: Check for outbound links to marketplace domains.
2. **Google site: search**: `site:{marketplace_domain} "{brand}"` — filtered by geography.
3. **Rappi filtering** (COL only): Only searched for CPG-relevant categories (Alimentos, Bebidas, Cosmeticos-belleza, Salud y Bienestar, Suplementos, Mascotas, Farmacéutica, Hogar, Infantiles y Bebés).
4. **TikTok Shop** (MEX only): 3-tier detection — (a) HTML links to `shop.tiktok.com`, (b) TikTok profile bio link inspection, (c) Google `site:shop.tiktok.com "{brand}"` fallback. Accepts optional `tiktok_profile_data` for tier (b).

## Output Schema

All outputs are written to `enriched_companies` table via upsert on domain:

| Column | Type | Description |
|--------|------|-------------|
| `has_distributors` | BOOLEAN | Brand has distributor/wholesale program |
| `has_own_stores` | BOOLEAN | Brand has own physical stores |
| `own_store_count_col` | INTEGER | Number of own stores in Colombia |
| `own_store_count_mex` | INTEGER | Number of own stores in Mexico |
| `has_multibrand_stores` | BOOLEAN | Brand sold in department stores |
| `multibrand_store_names` | JSONB | List of store names from controlled vocabulary |
| `on_mercadolibre` | BOOLEAN | Brand present on MercadoLibre |
| `on_amazon` | BOOLEAN | Brand present on Amazon |
| `on_rappi` | BOOLEAN | Brand present on Rappi (COL only, NULL if not CPG) |
| `on_walmart` | BOOLEAN | Brand present on Walmart (MEX only) |
| `on_liverpool` | BOOLEAN | Brand present on Liverpool (MEX only) |
| `on_coppel` | BOOLEAN | Brand present on Coppel (MEX only) |
| `on_tiktok_shop` | BOOLEAN | Brand present on TikTok Shop (MEX only) |
| `retail_confidence` | NUMERIC | Ratio of channels successfully evaluated |
| `retail_enriched_at` | TIMESTAMPTZ | When retail enrichment was last run |

## Supabase Tables

### `retail_department_stores`
Registry of multi-brand stores. Used for matching and future scraping.

| Column | Description |
|--------|-------------|
| `name` | Canonical store name (e.g., "Falabella") |
| `name_normalized` | Lowercase, no accents, for matching |
| `country` | COL or MEX |
| `website_url` | Store website |
| `scraper_active` | Whether periodic scraping is enabled |
| `scraper_config` | JSONB with CSS selectors for brand extraction |
| `last_scraped_at` | Last time scraper ran |

### `retail_store_brands`
Brands found per store (populated by scrapers, future implementation).

| Column | Description |
|--------|-------------|
| `store_id` | FK to retail_department_stores |
| `brand_name` | Brand name as found |
| `brand_name_normalized` | For matching |
| UNIQUE | (store_id, brand_name_normalized) |

## Cost & Rate Limits

| Resource | Per Brand | Monthly (300 brands) |
|----------|-----------|---------------------|
| Serper queries | ~6 | ~1,800 |
| HTTP requests | 2-5 | ~1,200 |
| Supabase reads | 2-4 | ~1,000 |
| Supabase writes | 1 | 300 |

Free tier Serper (2,500/month) supports ~400 retail enrichments.

## Caching
Each channel result is cached per domain with 7-day TTL:
- `retail_distributors`
- `retail_own_stores`
- `retail_multibrand`
- `retail_marketplaces`

## Error Handling
- Each channel runs independently; one failure doesn't block others
- Failed channels produce NULL values (not False)
- `retail_confidence` reflects the ratio of channels that returned data
- The orchestrator never raises exceptions

## Future Integration

### As Step 13 in main pipeline
Add to `run_enrichment.py` after Apollo/geo reconciliation:
```python
# Pass available context from earlier steps
retail_result = run_retail_enrichment(
    domain=domain, brand_name=result.company_name,
    html=html, geography=result.geography,
    category=result.category, ig_bio=ig_bio,
    knowledge_graph=demand_data.get("knowledge_graph"),
)
```

### Department store scrapers (Phase 3)
Generic scraper driven by `scraper_config` JSONB. Runs monthly, populates `retail_store_brands`. Each store can yield 200-2000 brands.

## Known Limitations
- Store count from website parsing is approximate (depends on page structure)
- Rappi detection via Google site: search has latency (new listings may not be indexed)
- Multi-brand detection is strongest when Supabase `retail_store_brands` is populated by scrapers
- Places search may return non-brand-owned stores (e.g., unauthorized resellers)
