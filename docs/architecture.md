# Arquitectura del Sistema

## Visión General

Enrichment Agent analiza sitios e-commerce en LATAM (Colombia/México) para predecir volumen de pedidos y evaluar aptitud de fulfillment. Sigue el patrón **WAT** (Workflows, Agents, Tools):

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Workflows   │ ──→ │   Agents    │ ──→ │    Tools    │
│  (markdown)  │     │ (AI/Claude) │     │  (Python)   │
│  Instrucciones│     │ Coordinación│     │  Ejecución  │
└─────────────┘     └─────────────┘     └─────────────┘
```

**Principio clave**: AI razona y coordina, scripts ejecutan. Esto evita degradación de accuracy en pipelines largos.

---

## Flujo de Datos Principal

### Enrichment Individual (SSE Streaming)
```
Frontend (Next.js)
  │ POST /api/v2/enrichment/analyze-stream {url: "dominio.com"}
  ▼
FastAPI (backend/api/main.py)
  │ verify_api_key() → run_enrichment() en thread
  ▼
Orchestrator (tools/orchestrator/run_enrichment.py)
  │ 14 steps secuenciales, cada uno con on_step callback
  │
  ├─ Step 0: Resolve URL (Serper si es nombre de marca)
  ├─ Step 1: Normalize URL → domain
  ├─ Step 2: Scrape website → HTML
  ├─ Step 3: Detect platform (Shopify/VTEX/WooCommerce/Magento)
  ├─ Step 4: Detect geography (COL/MEX)
  ├─ Step 5a: Extract social links del HTML
  ├─ Step 5b: Instagram metrics (SearchAPI → followers, engagement)
  ├─ Step 6: META Ads count (SearchAPI → Meta Ad Library)
  ├─ Step 6b: TikTok Ads count (SearchAPI → TikTok Ads Library)
  ├─ Step 7: Scrape product catalog (product_count, prices)
  ├─ Step 8: Estimate traffic (señales indirectas)
  ├─ Step 9: Google Demand scoring (3 queries Serper)
  ├─ Step 10: Detect fulfillment provider (pasivo, del HTML)
  ├─ Step 11: Classify category (Claude Sonnet tool_use)
  ├─ Step 12: Apollo enrichment (contacts, company info)
  ├─ Step 12b: Geography reconciliation (fallbacks: currency, TLD, Apollo)
  └─ Step 13: HubSpot lookup (company, deals, contacts)
  │
  ▼
Orders Estimator (tools/orders_estimator/predict.py)
  │ LightGBM quantile regression → P10, P50, P90
  ▼
Supabase Writer (tools/export/supabase_writer.py)
  │ Upsert en tabla enriched_companies
  ▼
SSE Response → Frontend muestra resultado
```

### Batch Processing
```
CLI: python tools/orchestrator/batch_runner.py urls.txt
  │ Lee URLs, deduplica, resume desde sheet
  │ Para cada URL: run_enrichment() serial
  │ Buffer de 10 → flush a Google Sheets/Supabase
  └─ Resumen final con stats
```

---

## Pipeline de 14 Pasos — Decisiones de Diseño

### Nunca lanza excepciones
El orchestrator (`run_enrichment.py`) captura TODAS las excepciones por step. Si un tool falla, el campo correspondiente queda `None` y el pipeline continúa. Esto garantiza que siempre se obtiene un resultado parcial.

### Cache de 7 días
Cada tool tiene cache independiente: `.tmp/cache/{domain}/{tool_name}.json`
- Metadata: `{domain, tool_name, cached_at, expires_at, ttl, cache_version}`
- Se puede saltar con `--skip-cache`
- Ahorra créditos de APIs en re-ejecuciones

### Geography Reconciliation
Si `detect_geography` retorna UNKNOWN, se aplican fallbacks en orden:
1. Parámetro `country` explícito
2. País de Apollo (`organization.country`)
3. Currency del catálogo (COP → COL, MXN → MEX)
4. TLD del dominio (.co, .mx, .com.co, .com.mx)

### Callback Pattern (SSE)
```python
def on_step(name: str, status: str, duration_ms: int, detail: str):
    # Emitido como SSE event al frontend
    yield {"type": "step", "step": name, "status": status, ...}
```
Permite al frontend mostrar progreso en tiempo real.

---

## Modelo de Predicción de Órdenes

**Algoritmo**: LightGBM Quantile Regression (3 modelos: P10, P50, P90)
**Training data**: ~142 empresas de Colombia con datos reales de operaciones
**Performance**: WAPE 0.80, bucket accuracy ±1 tier 88%

### Features (15 principales)
| Grupo | Features |
|-------|----------|
| Social | ig_followers, ig_engagement_rate, ig_size_score, ig_health_score |
| Ads | meta_active_ads_count, tiktok_active_ads_count |
| Catalog | product_count, avg_price, price_range (max-min) |
| Traffic | estimated_monthly_visits |
| Demand | brand_demand_score, site_serp_coverage_score |
| Company | number_employes, platform (encoded), currency |

### Limitaciones
- **Solo Colombia** — No usar para México (datos insuficientes)
- ~142 muestras — alta varianza en categorías raras
- Tiendas no-Shopify tienen menos features de catálogo

### Confidence Flags
- **high**: Todos los signals principales presentes
- **medium**: Instagram + traffic presentes
- **low**: Faltan signals importantes

---

## Retail Channel Detection (5 canales)

Pipeline separado (`tools/retail/run_retail_enrichment.py`):

| Canal | Método | Queries |
|-------|--------|---------|
| R0.5 Google Shopping | SearchAPI → sellers | 1 |
| R1 Distribuidores | Serper → "{brand} distribuidor" | 0-1 |
| R2 Tiendas Propias | Serper Places → ubicaciones | 1-2 |
| R3 Multimarca | Supabase → fuzzy matching contra registry | 0 |
| R4 Marketplaces | Serper → MercadoLibre, Amazon, Rappi, Linio | 0-6 |

### Fuzzy Matching Cascade (R3)
1. Exact normalized match
2. Exact variants (domain name)
3. Token containment / Substring (40% ratio)
4. Fuzzy (85% token_set_ratio con rapidfuzz)

---

## Backend API

### Endpoints principales
| Método | Ruta | Propósito |
|--------|------|-----------|
| POST | `/api/v2/enrichment/analyze-stream` | Enrichment con SSE streaming |
| GET | `/api/v2/enrichment/check-duplicate?domain=` | Verificar si dominio ya existe |
| GET | `/api/v2/enrichment/companies` | Lista paginada (page, limit, search) |
| GET | `/api/v2/enrichment/companies/{domain}` | Detalle completo de empresa |
| POST | `/api/v2/retail/analyze-stream` | Retail channel detection con SSE |
| POST | `/api/v2/enrichment/{domain}/feedback` | Feedback sobre accuracy |
| GET | `/api/v2/enrichment/hubspot/{company_id}` | Detalle HubSpot modal |
| GET | `/health` | Status de Redis, Supabase, workers |

### Auth
- `HTTPBearer` → valida contra `API_KEYS` env var (comma-separated)
- Si `API_KEYS` está vacío, acceso abierto

### CORS
Configurado para: `localhost:3000`, `localhost:3001`, `localhost:3002`, dominio de producción

---

## Patrones Clave

### Return Contract de Tools
```python
{"success": True, "data": {...}, "error": None}
{"success": False, "data": {}, "error": "mensaje de error"}
```

### EnrichmentResult (39 campos)
Definido en `tools/models/enrichment_result.py` como dataclass Python. Es el contrato canónico entre el orchestrator, la API, y Supabase.

### Costo por empresa
~$0.05 promedio (Serper $0.015 + Anthropic $0.01 + overhead). Apollo y Apify añaden $0.10-0.20 cuando se usan.

---

## Diagrama de Dependencias Externas

```
                    ┌──── Serper (Google Search)
                    ├──── SearchAPI.io (Meta/TikTok Ads, IG, Shopping)
Enrichment Agent ───├──── Apify (IG Comments)
                    ├──── Apollo.io (Contacts)
                    ├──── HubSpot (CRM)
                    ├──── Anthropic (Claude, Category)
                    ├──── Supabase (PostgreSQL DB)
                    └──── Redis (Cache/Queue)
```
