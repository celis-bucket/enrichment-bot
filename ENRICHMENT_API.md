# Melonn Enrichment API — Integration Guide

> **Last updated:** 2026-04-10

This document describes how to integrate with Melonn's Enrichment API. Use it to enrich e-commerce companies with data about their platform, social media, ads, traffic, contacts, and estimated order volume.

## Setup

### Environment Variable
Add this to your `.env` file:
```
ENRICHMENT_API_KEY=<your-api-key>
ENRICHMENT_API_URL=https://enrichment-bot-production-943a.up.railway.app
```

### Authentication
All requests require a Bearer token:
```
Authorization: Bearer <ENRICHMENT_API_KEY>
```

---

## Endpoints

### 1. Enrich a company (streaming)

**`POST /api/v2/enrichment/analyze-stream`**

Takes a URL or domain and runs the full enrichment pipeline (~15-30 seconds cold, ~2-5 seconds if cached). Returns real-time progress events via Server-Sent Events (SSE), ending with the full result. Steps run in parallel where possible.

**Request:**
```json
{
  "url": "thehairg.com",
  "geography": "COL"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `url` | Yes | Domain, full URL, or brand name |
| `geography` | Yes | `"COL"` or `"MEX"` — determines marketplace detection and store lists |

**cURL example:**
```bash
curl -X POST "${ENRICHMENT_API_URL}/api/v2/enrichment/analyze-stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ENRICHMENT_API_KEY}" \
  -d '{"url": "thehairg.com", "geography": "COL"}'
```

**Response (SSE stream):**

The response is a stream of `data:` lines. Each line is a JSON object with a `type` field:

```
data: {"type": "step", "step": "scrape", "status": "running", "duration_ms": 0, "detail": ""}
data: {"type": "step", "step": "scrape", "status": "ok", "duration_ms": 492, "detail": "470KB"}
data: {"type": "step", "step": "platform", "status": "ok", "duration_ms": 172, "detail": "Shopify (0.50)"}
...
data: {"type": "result", "data": { ...full enrichment result... }}
```

- `type: "step"` — progress update (status: `running`, `ok`, `warn`, `fail`, `skip`)
- `type: "result"` — final enrichment data (see Response Schema below)
- `type: "error"` — pipeline error with `detail` message

### 2. Get an already-enriched company

**`GET /api/v2/enrichment/companies/{domain}`**

Returns cached enrichment data without re-running the pipeline. Fast (< 200ms).

```bash
curl "${ENRICHMENT_API_URL}/api/v2/enrichment/companies/thehairg.com" \
  -H "Authorization: Bearer ${ENRICHMENT_API_KEY}"
```

### 3. Check if a domain was already enriched

**`GET /api/v2/enrichment/check-duplicate?domain={domain}`**

```bash
curl "${ENRICHMENT_API_URL}/api/v2/enrichment/check-duplicate?domain=thehairg.com" \
  -H "Authorization: Bearer ${ENRICHMENT_API_KEY}"
```

**Response:**
```json
{
  "exists": true,
  "domain": "thehairg.com",
  "last_analyzed": "2026-03-21T17:20:00Z"
}
```

### 4. List all enriched companies

**`GET /api/v2/enrichment/companies`**

Query params: `page` (default 1), `limit` (default 25, max 100), `search`, `category`, `geography`

```bash
curl "${ENRICHMENT_API_URL}/api/v2/enrichment/companies?page=1&limit=10&geography=COL" \
  -H "Authorization: Bearer ${ENRICHMENT_API_KEY}"
```

### 5. Health check (no auth required)

**`GET /health`**

```bash
curl "${ENRICHMENT_API_URL}/health"
```

### 6. Integration guide (no auth required)

**`GET /api/v2/enrichment/docs/integration-guide`**

Returns this document (`ENRICHMENT_API.md`) directly from the API. Useful when you need to check the current API contract without accessing the repo.

| Param | Default | Description |
|-------|---------|-------------|
| `format` | `markdown` | `markdown` returns raw text; `html` returns a styled page for browsers |

```bash
# Raw markdown
curl "${ENRICHMENT_API_URL}/api/v2/enrichment/docs/integration-guide"

# Browser-friendly HTML
curl "${ENRICHMENT_API_URL}/api/v2/enrichment/docs/integration-guide?format=html"
```

---

## Response Schema

The enrichment result (`type: "result"` in the stream, or the GET company response) has these fields:

```typescript
interface EnrichmentResult {
  // Identity
  company_name: string | null;      // "The Hair Generation"
  domain: string | null;             // "thehairg.com"

  // Platform detection
  platform: string | null;           // "Shopify", "VTEX", "WooCommerce", etc.
  platform_confidence: number | null; // 0.0 - 1.0

  // Geography
  geography: string | null;          // ISO 3166 alpha-3: "COL", "MEX", "BRA"
  geography_confidence: number | null;

  // Category
  category: string | null;           // "Beauty", "Fashion", "Electronics", etc.
  category_confidence: number | null;
  category_evidence: string | null;

  // Social media
  instagram_url: string | null;      // "https://instagram.com/thehairgeneration"
  ig_followers: number | null;       // 379917
  ig_size_score: number | null;      // 0-100 scale
  ig_health_score: number | null;    // 0-100 scale
  fb_followers: number | null;       // Facebook page followers
  tiktok_followers: number | null;   // TikTok profile followers (MEX only)

  // Company info (from Apollo.io)
  company_linkedin: string | null;
  contact_name: string | null;       // Primary contact
  contact_email: string | null;
  number_employes: number | null;
  contacts: ApolloContact[];         // All contacts found

  // Meta Ads
  meta_active_ads_count: number | null;  // 10404
  meta_ad_library_url: string | null;

  // Product catalog
  product_count: number | null;      // 14
  avg_price: number | null;          // 149600.0
  price_range_min: number | null;
  price_range_max: number | null;
  currency: string | null;           // "COP", "MXN", "USD"

  // Traffic
  estimated_monthly_visits: number | null;  // 114135
  traffic_confidence: number | null;
  signals_used: string | null;

  // Google demand signals
  brand_demand_score: number | null;        // 0.0 - 1.0
  site_serp_coverage_score: number | null;  // 0.0 - 1.0
  google_confidence: number | null;

  // HubSpot CRM
  hubspot_company_id: string | null;
  hubspot_company_url: string | null;
  hubspot_deal_count: number | null;
  hubspot_deal_stage: string | null;
  hubspot_contact_exists: number | null;  // 1 or 0
  hubspot_lifecycle_label: string | null;
  hubspot_last_contacted: string | null;

  // Retail Channels
  has_distributors: boolean | null;       // Brand has distributor/wholesale program
  has_own_stores: boolean | null;         // Brand has own physical stores
  own_store_count_col: number | null;     // Store count in Colombia
  own_store_count_mex: number | null;     // Store count in Mexico
  has_multibrand_stores: boolean | null;  // Brand sold in department stores
  multibrand_store_names: string[];       // ["Liverpool", "Walmart", ...]
  on_mercadolibre: boolean | null;        // COL + MEX
  on_amazon: boolean | null;              // MEX only (not available in COL)
  on_rappi: boolean | null;              // COL only
  on_walmart: boolean | null;            // MEX only
  on_liverpool: boolean | null;          // MEX only
  on_coppel: boolean | null;             // MEX only
  on_tiktok_shop: boolean | null;        // MEX only
  marketplace_names: string[];           // ["MercadoLibre", "Rappi", ...]
  retail_confidence: number | null;      // 0.0 - 1.0

  // Orders prediction
  prediction: {
    predicted_orders_p10: number;
    predicted_orders_p50: number;
    predicted_orders_p90: number;
    prediction_confidence: "high" | "medium" | "low";
  } | null;

  // Potential Scoring
  ecommerce_size_score: number | null;     // 0-100
  retail_size_score: number | null;        // 0-100
  combined_size_score: number | null;      // 0-100
  fit_score: number | null;               // 0-100
  overall_potential_score: number | null;  // 0-100
  potential_tier: string | null;          // "Extraordinary", "Very Good", "Good", "Low"

  // Execution metadata
  enrichment_type: string | null;       // "full" or "lite"
  tool_coverage_pct: number | null;
  total_runtime_sec: number | null;
  cost_estimate_usd: number | null;
  workflow_log: WorkflowStep[];
  updated_at: string | null;            // ISO 8601 timestamp

  // Lead fields (present when source=hubspot_leads)
  lite_triage_score: number | null;     // 0-100, lite enrichment score
  worth_full_enrichment: boolean | null;
  hs_lead_stage: string | null;        // "Nuevo", "Enrichment", "Conectado", etc.
  hs_lead_label: string | null;
  hs_lead_owner: string | null;
  hs_lead_created_at: string | null;
  hs_last_activity_date: string | null;
  hs_activity_count: number | null;
  hs_open_tasks_count: number | null;
}

interface ApolloContact {
  name: string;
  title: string;
  email: string | null;
  linkedin_url: string | null;
  phone: string | null;
}

interface WorkflowStep {
  step: string;
  status: "ok" | "warn" | "fail" | "skip";
  duration_ms: number;
  detail: string | null;
}
```

---

## Integration Patterns

### Pattern A: Enrich on lead submission (recommended)

When a lead comes in with a website URL, call the streaming endpoint and wait for the result:

```typescript
async function enrichLead(url: string, geography: "COL" | "MEX"): Promise<EnrichmentResult> {
  const response = await fetch(
    `${process.env.ENRICHMENT_API_URL}/api/v2/enrichment/analyze-stream`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${process.env.ENRICHMENT_API_KEY}`,
      },
      body: JSON.stringify({ url, geography }),
    }
  );

  if (!response.ok) {
    throw new Error(`Enrichment failed: HTTP ${response.status}`);
  }

  // Read SSE stream and extract the final result
  const text = await response.text();
  const lines = text.split('\n');

  for (const line of lines) {
    if (!line.startsWith('data: ')) continue;
    const msg = JSON.parse(line.slice(6));
    if (msg.type === 'result') {
      return msg.data;
    }
    if (msg.type === 'error') {
      throw new Error(msg.detail);
    }
  }

  throw new Error('No result received from enrichment');
}
```

### Pattern B: Check cache first, then enrich

```typescript
async function getOrEnrichCompany(domain: string, geography: "COL" | "MEX"): Promise<EnrichmentResult> {
  const headers = { 'Authorization': `Bearer ${process.env.ENRICHMENT_API_KEY}` };

  // Check if already enriched
  const check = await fetch(
    `${process.env.ENRICHMENT_API_URL}/api/v2/enrichment/check-duplicate?domain=${domain}`,
    { headers }
  );
  const { exists } = await check.json();

  if (exists) {
    // Return cached data
    const res = await fetch(
      `${process.env.ENRICHMENT_API_URL}/api/v2/enrichment/companies/${domain}`,
      { headers }
    );
    return res.json();
  }

  // Run fresh enrichment
  return enrichLead(domain, geography);
}
```

---

## Real Example

**Input:** `thehairg.com`

**Key output fields:**
| Field | Value |
|---|---|
| platform | Shopify |
| geography | COL |
| ig_followers | 379,917 |
| meta_active_ads_count | 10,404 |
| product_count | 14 |
| avg_price | 149,600 COP |
| estimated_monthly_visits | 114,135 |
| predicted_orders_p50 | 1,010 |
| prediction_confidence | high |
| total_runtime_sec | 22 |
| cost_estimate_usd | $0.05 |

---

## Notes

- Each enrichment takes ~15-30 seconds (cold) or ~2-5 seconds (cached) and costs ~$0.05 USD in API credits
- The pipeline runs 14 steps in parallel using ThreadPoolExecutor, coordinated by dependency events
- Results are cached in the database — use `check-duplicate` or `GET /companies/{domain}` to avoid re-running
- The `geography` field is required and determines which marketplaces are evaluated:
  - **COL**: MercadoLibre, Rappi
  - **MEX**: MercadoLibre, Amazon, Walmart, Liverpool, Coppel, TikTok Shop
- The API processes one enrichment at a time per domain
- If a domain doesn't respond, the pipeline automatically tries the `www.` variant (and vice versa)
- Interactive API docs available at: `${ENRICHMENT_API_URL}/docs`
