# Integraciones con APIs Externas

## 1. Serper (Google Search)

- **Propósito**: Resolución de URLs desde nombres de marca, búsqueda de redes sociales, demand scoring
- **Base URL**: `https://google.serper.dev/`
- **Auth**: Header `X-API-KEY: {SERPER_API_KEY}`
- **Archivo principal**: `tools/core/google_search.py`
- **Rate limit**: 2,500 queries/mes (tier gratuito)

**Endpoints usados**:
| Endpoint | Método | Uso en el proyecto |
|----------|--------|-------------------|
| `/search` | POST | Búsqueda general (resolución de marca → URL) |
| `/places` | POST | Detección de tiendas físicas (`tools/retail/detect_own_stores.py`) |

**Flujo típico**:
```
google_search(query, num=5, gl="co") → requests.post(URL, headers, json) → response["organic"]
```

**Parámetros comunes**: `q` (query), `num` (resultados), `gl` (país: co/mx), `hl` (idioma), `page`

**Manejo de errores**: Retorna `{'success': False, 'results': [], 'error': str}` si falla. No lanza excepciones.

---

## 2. SearchAPI.io

- **Propósito**: Meta Ad Library, TikTok Ads Library, Instagram profiles, Google Shopping
- **Base URL**: `https://www.searchapi.io/api/v1/search`
- **Auth**: Query param `api_key={SEARCHAPI_API_KEY}`
- **Rate limit**: 100 búsquedas/mes (tier gratuito)

**Endpoints usados**:
| Engine | Archivo | Uso |
|--------|---------|-----|
| `engine=meta_ad_library` | `tools/social/apify_meta_ads.py` | Contar anuncios activos META |
| `engine=tiktok_ads_library` | `tools/social/searchapi_tiktok_ads.py` | Contar anuncios activos TikTok |
| `engine=google_shopping` | `tools/retail/google_shopping_sellers.py` | Detectar sellers en Google Shopping |
| `engine=google_profiles` | `tools/social/apify_instagram.py` | Perfil Instagram (followers, engagement) |

**Flujo típico (Meta Ads)**:
```python
params = {"engine": "meta_ad_library", "search_terms": company_name, "ad_status": "active", "api_key": key}
response = requests.get(BASE_URL, params=params, timeout=30)
count = len(response.json().get("ads", []))
```

**Manejo de errores**: Timeout 30s, retorna 0 ads si falla. Log en workflow_execution_log.

---

## 3. Apify

- **Propósito**: Scraping de Instagram (comments) y Meta Ads (fallback)
- **Base URL**: `https://api.apify.com/v2/`
- **Auth**: Query param `token={APIFY_API_TOKEN}`
- **Archivos**: `tools/social/apify_instagram_comments.py`

**Endpoints usados**:
| Endpoint | Uso |
|----------|-----|
| `acts/apidojo~instagram-comments-scraper/run-sync-get-dataset-items` | Scrape comments (sync) |
| `acts/apidojo~instagram-comments-scraper/runs` | Scrape comments (async) |
| `actor-runs/{runId}` | Polling de estado |
| `datasets/{datasetId}` | Obtener resultados |

**Flujo típico (comments async)**:
```
1. POST /runs con input {directUrls, resultsLimit: 50}
2. Poll GET /actor-runs/{runId} cada 10s hasta SUCCEEDED
3. GET /datasets/{datasetId}/items → lista de comments
```

**Manejo de errores**: Timeout 300s para async. Si falla, retorna lista vacía. Créditos: ~$0.10-0.20 por perfil.

---

## 4. Apollo.io

- **Propósito**: Enriquecimiento de contactos (decision-makers) e info de empresa
- **Base URL**: `https://api.apollo.io/api/v1/`
- **Auth**: Header `X-Api-Key: {APOLLO_API_KEY}` + `Content-Type: application/json`
- **Archivo**: `tools/contacts/apollo_enrichment.py`
- **Rate limit**: 10,000 créditos/mes

**Endpoints usados**:
| Endpoint | Método | Créditos | Uso |
|----------|--------|----------|-----|
| `/organizations/enrich` | GET | 1/call | Info empresa (employees, founded, LinkedIn, industry) |
| `/mixed_people/api_search` | POST | 0 (gratis) | Buscar personas por empresa + título |
| `/people/match` | POST | 1/call | Enriquecer persona (email verificado) |

**Flujo típico**:
```
1. GET /organizations/enrich?domain={domain} → company info
2. POST /mixed_people/api_search con títulos bilingües (CEO, Founder, Director Logística...)
   → Busca seniority: owner → c_suite → vp → director → manager
3. POST /people/match con person_id → email verificado, LinkedIn
4. Retorna: contact_name, contact_email, company_linkedin, number_employes, founded_year, contacts_list
```

**Manejo de errores**: Si no hay API key, retorna stub con datos vacíos. Timeout 30s por request.

---

## 5. HubSpot CRM

- **Propósito**: Verificar si empresa existe en CRM, obtener deals y contactos
- **Base URL**: `https://api.hubapi.com/`
- **Auth**: Header `Authorization: Bearer {HUBSPOT_TOKEN}`
- **Archivo**: `tools/hubspot/hubspot_lookup.py`
- **Portal ID**: `HUBSPOT_PORTAL_ID` (default: 9359507)

**Endpoints usados**:
| Endpoint | Método | Uso |
|----------|--------|-----|
| `crm/v3/objects/companies/search` | POST | Buscar empresa por dominio |
| `crm/v4/objects/companies/{id}/associations/deals` | GET | Obtener deals asociados |
| `crm/v3/objects/deals/batch/read` | POST | Leer deals en batch |
| `crm/v3/objects/contacts/{email}?idProperty=email` | GET | Verificar si contacto existe |

**Flujo típico**:
```
1. Search company: filterGroups con EQ domain → fallback CONTAINS_TOKEN hs_additional_domains
2. Si encuentra: GET associations/deals → batch read deals → extraer pipeline + stage
3. Check contact: GET contacts/{email}?idProperty=email → exists true/false
4. Retorna: company_id, company_url, deal_count, deal_stage, contact_exists, lifecycle_label
```

**Pipelines conocidos**: Ventas 2025, Adyacent Revenue, Expansión, Partnership Program

**Manejo de errores**: 404 = no encontrado (normal). Timeout 30s. Dominio normalizado (sin www.).

---

## 6. Anthropic (Claude API)

- **Propósito**: Clasificación de categoría de producto usando LLM con tool_use
- **Auth**: Env var `ANTHROPIC_API_KEY` (vía SDK anthropic)
- **Modelo**: `claude-sonnet-4-6`
- **Archivo**: `tools/ai/classify_category.py`

**Flujo típico**:
```python
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-6",
    tools=[classify_tool_schema],  # Tool use con 24 categorías permitidas
    messages=[{"role": "user", "content": prompt_con_contexto}]
)
# Extrae: category, confidence (0-1), evidence, company_name
```

**24 categorías permitidas**: Ropa, Calzado, Cosmeticos-belleza, Alimentos-bebidas, Electrónicos, Hogar-decoración, Deportes-fitness, Mascotas, Salud-bienestar, Joyería-accesorios, Bebés-niños, Juguetes, Libros-papelería, Automotriz, Jardín-exterior, Tecnología-gadgets, Arte-manualidades, Instrumentos-música, Licores, Farmacia, Sex-shop, Industrial-B2B, Servicios, Otro

**Costo**: ~$0.01 por clasificación (~500 tokens)

---

## 7. Supabase (PostgreSQL)

- **Propósito**: Base de datos principal (reemplazó Google Sheets)
- **Base URL**: `{SUPABASE_URL}/rest/v1/`
- **Auth**: Headers `apikey: {SUPABASE_SERVICE_KEY}` + `Authorization: Bearer {SUPABASE_SERVICE_KEY}`
- **Archivos**: `tools/export/supabase_writer.py`, `tools/logistics/supabase_client.py`, `backend/api/main.py`

**Tabla principal: `enriched_companies`**
- Campos: domain (PK), company_name, platform, category, geography, ig_followers, ig_size_score, ig_health_score, meta_active_ads_count, tiktok_active_ads_count, contact_name, contact_email, predicted_orders_p10/p50/p90, hubspot_company_id, workflow_execution_log, updated_at, etc.
- Upsert por dominio (ON CONFLICT domain DO UPDATE)

**Operaciones**:
| Operación | Método HTTP | Uso |
|-----------|-------------|-----|
| Upsert resultado | POST con `Prefer: resolution=merge-duplicates` | Guardar enrichment |
| Listar empresas | GET con `?select=*&order=updated_at.desc` | API companies list |
| Buscar por dominio | GET con `?domain=eq.{domain}` | Duplicate check |

---

## 8. Google Sheets (DEPRECATED)

- **Propósito**: Almacenamiento de resultados (reemplazado por Supabase)
- **Auth**: Service account JSON (`GOOGLE_SERVICE_ACCOUNT_JSON` env var o archivo `credentials.json`)
- **Archivo**: `tools/export/google_sheets_writer.py`
- **Librería**: gspread 6.0.0
- **Estado**: Código mantenido por retrocompatibilidad, pero Supabase es el destino principal

---

## 9. SimilarWeb (STUB)

- **Propósito**: Estimación de tráfico web
- **Base URL**: `https://api.similarweb.com/v1/website/{domain}/total-traffic/monthly`
- **Auth**: Query param (requiere API key de pago)
- **Archivo**: `tools/traffic/estimate_traffic.py`
- **Estado**: Implementación stub — actualmente estima tráfico con señales indirectas (sitemap, social, reviews)
- **TODO**: Integrar cuando se tenga API key de pago

---

## 10. Playwright (Browser Automation)

- **Propósito**: Renderizado de sitios con JavaScript pesado (fallback del scraper HTTP)
- **Librería**: playwright 1.40.0
- **Archivo**: `tools/core/browser_scraper.py`
- **Config**: `PLAYWRIGHT_HEADLESS=true` (default)
- **Timeouts**: Navegación 60s, default 30s
- **Uso**: Solo cuando el scraper HTTP no obtiene contenido suficiente. Pasivo en batch (no checkout detection).
