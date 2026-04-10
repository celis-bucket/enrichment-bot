# Enrichment Agent — Instrucciones para el Agente

## WAT Framework (Workflows, Agents, Tools)
Arquitectura de 3 capas que separa razonamiento AI de ejecución determinística.
- **Workflows** (`workflows/`): SOPs en Markdown — objetivo, inputs, tools, outputs, edge cases
- **Agents** (tú): Coordinación inteligente — lee el workflow, ejecuta tools en secuencia, maneja fallos
- **Tools** (`tools/`): Scripts Python determinísticos — API calls, transformaciones, queries
- **Principio**: AI orquesta, scripts ejecutan. Nunca intentes hacer directamente lo que un tool ya hace.

## Stack Tecnológico
- **Backend**: Python 3.11, FastAPI 0.109, Uvicorn, Pydantic 2.5
- **Frontend**: Next.js 16, React 19, TypeScript 5.9, Tailwind CSS 4
- **ML**: LightGBM (quantile regression P10/P50/P90), scikit-learn, scipy
- **DB**: Supabase (PostgreSQL vía PostgREST) — tabla principal: `enriched_companies`
- **Cache**: Redis 7 (job queue + cache 7 días por dominio/tool)
- **Scraping**: requests, BeautifulSoup4, Playwright (headless), Apify client
- **Deploy**: Railway.app (Dockerfile), docker-compose para local

## Estructura del Proyecto
```
tools/                    # 18 módulos Python (ejecución determinística)
├── orchestrator/         #   run_enrichment.py (pipeline 16 pasos: 0-15), batch_runner.py
├── core/                 #   url_normalizer, web_scraper, cache_manager, google_search
├── detection/            #   detect_ecommerce_platform, detect_geography, detect_fulfillment
├── social/               #   extract_social_links, apify_instagram, apify_meta_ads, tiktok_ads
├── ecommerce/            #   scrape_product_catalog
├── traffic/              #   estimate_traffic
├── google_demand/        #   score_demand (3 queries SearchAPI)
├── ai/                   #   classify_category (Claude Sonnet, tool_use)
├── contacts/             #   apollo_enrichment
├── hubspot/              #   hubspot_lookup
├── orders_estimator/     #   predict.py, train.py, config, features, evaluate
├── retail/               #   detect_distributors, own_stores, multibrand, marketplaces, import_fastmoss
├── export/               #   supabase_writer, google_sheets_writer (deprecated)
├── scoring/              #   instagram_scoring, potential_scoring, backfill_scores
├── logistics/            #   ig_complaints analysis, supabase_cron_runner
└── models/               #   enrichment_result.py (dataclass 39 campos)
workflows/                # SOPs: enrichment.md, enrichment_retail.md, orders_estimation.md
backend/                  # FastAPI API (api/main.py ~950 líneas)
├── api/models/schemas.py #   Pydantic models (request/response)
frontend/                 # Next.js app (app/, components/)
.tmp/                     # Cache, modelos LightGBM, datos intermedios (descartable)
docs/                     # Documentación técnica detallada
```

## APIs Externas (resumen)
| API | Propósito | Env Var | Archivo principal |
|-----|-----------|---------|-------------------|
| SearchAPI.io | Google Search, Google Maps/Places, Meta Ads, TikTok Ads, Google Shopping, IG profiles | `SEARCHAPI_API_KEY` | `tools/core/google_search.py`, `tools/social/apify_meta_ads.py` |
| Apify | Instagram scraping, comments | `APIFY_API_TOKEN` | `tools/social/apify_instagram_comments.py` |
| Apollo.io | Contactos, info empresa, LinkedIn | `APOLLO_API_KEY` | `tools/contacts/apollo_enrichment.py` |
| HubSpot | CRM lookup (companies, deals, contacts) | `HUBSPOT_TOKEN` | `tools/hubspot/hubspot_lookup.py` |
| Anthropic | Clasificación categoría (Claude Sonnet) | `ANTHROPIC_API_KEY` | `tools/ai/classify_category.py` |
| Supabase | DB PostgreSQL (enriched_companies) | `SUPABASE_URL` + `_SERVICE_KEY` | `tools/export/supabase_writer.py` |
| Redis | Cache + job queue | `REDIS_URL` | `backend/api/main.py` |

## Deploy
- **Producción**: Railway.app → `enrichment-bot-production-943a.up.railway.app`
- **Local**: `docker-compose up` → Redis:6379, Backend:8000, Frontend:3002
- **CI/CD**: GitHub Actions → `logistics-cron.yml` (lunes 8:00 UTC)
- **Health check**: `GET /health` (verifica Redis + Supabase)

## Convenciones de Código
- Todos los tools retornan `{'success': bool, 'data': dict, 'error': str|None}`
- Pipeline (`run_enrichment.py`) NUNCA lanza excepciones — siempre retorna EnrichmentResult
- Cache: 7 días TTL por dominio por tool en `.tmp/cache/{domain}/{tool}.json`
- Callbacks: `on_step(name, status, duration_ms, detail)` para streaming SSE
- EnrichmentResult: 86 campos canónicos (ver `tools/models/enrichment_result.py`), incluye retail + scoring
- Categorías permitidas: 24 categorías fijas en `tools/ai/classify_category.py`
- Geography: COL | MEX — obligatorio desde API (confianza 1.0). Fallback auto-detect solo en batch/CLI
- Marketplaces por país: COL (MercadoLibre, Rappi) | MEX (MercadoLibre, Amazon, Walmart, Liverpool, Coppel, TikTok Shop)

## Reglas Estrictas

### NUNCA
- Inventar datos de APIs — si un tool falla, el campo queda None
- Lanzar excepciones desde tools del pipeline — catch todo, log en workflow_execution_log
- Correr Apollo en batch sin preguntar (consume créditos pagos)
- Guardar secretos fuera de `.env`
- Usar puerto 3000 (ocupado por otro proyecto)
- Crear/sobreescribir workflows sin preguntar
- Usar el modelo de órdenes para México (solo Colombia, ~142 muestras)

### SIEMPRE
- Leer el workflow relevante antes de ejecutar una tarea
- Verificar `tools/` antes de crear scripts nuevos
- Incluir Apollo en enrichment individual (el usuario paga por ello)
- Documentar rate limits y errores nuevos en el workflow correspondiente
- Usar Supabase (no Google Sheets) para persistencia de resultados
- Respetar cache de 7 días salvo que se pase --skip-cache
- Preguntar antes de correr herramientas que consuman créditos pagos
- Actualizar `ENRICHMENT_API.md` cada vez que cambies endpoints, schemas de request/response, autenticación, o comportamiento del API en `backend/api/main.py` o `backend/api/models/schemas.py`

## Cómo Operar
1. Lee el workflow relevante en `workflows/`
2. Identifica qué tools necesitas en `tools/`
3. Ejecuta en secuencia, maneja fallos sin crashear
4. Si algo falla: lee el error, arregla, verifica, actualiza el workflow
5. Archivos finales van a Supabase. Todo en `.tmp/` es descartable.
