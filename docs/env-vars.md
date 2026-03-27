# Variables de Entorno

Fuentes: `.env.example`, búsqueda de `os.getenv` en todo el código.

## APIs de AI

| Variable | Requerida | Privada | Servicio | Descripción |
|----------|-----------|---------|----------|-------------|
| `ANTHROPIC_API_KEY` | Sí | Sí | Anthropic | API key para Claude (clasificación de categoría) |
| `OPENAI_API_KEY` | No | Sí | OpenAI | Listada en .env.example pero no se usa activamente |

## APIs de Búsqueda y Scraping

| Variable | Requerida | Privada | Servicio | Descripción |
|----------|-----------|---------|----------|-------------|
| `SERPER_API_KEY` | Sí | Sí | Serper | Google Search API (2,500/mes free). Resolución de URLs, demand scoring, social links |
| `SEARCHAPI_API_KEY` | Sí | Sí | SearchAPI.io | Meta Ads, TikTok Ads, Google Shopping, Instagram profiles (100/mes free) |
| `APIFY_API_TOKEN` | Sí | Sí | Apify | Instagram comments scraping, Meta Ads fallback (créditos) |
| `APIFY_INSTAGRAM_ENDPOINT` | No | Sí | Apify | Endpoint custom para Instagram scraper (override) |

## CRM y Contactos

| Variable | Requerida | Privada | Servicio | Descripción |
|----------|-----------|---------|----------|-------------|
| `APOLLO_API_KEY` | Sí | Sí | Apollo.io | Enriquecimiento de contactos y empresa (10K créditos/mes) |
| `HUBSPOT_TOKEN` | Sí | Sí | HubSpot | Bearer token para CRM API v3 |
| `HUBSPOT_PORTAL_ID` | No | No | HubSpot | ID del portal (default: 9359507) |

## Base de Datos

| Variable | Requerida | Privada | Servicio | Descripción |
|----------|-----------|---------|----------|-------------|
| `SUPABASE_URL` | Sí | No | Supabase | URL del proyecto (e.g., `https://cbgqwnxwwzqfetpxkomr.supabase.co`) |
| `SUPABASE_SERVICE_KEY` | Sí | Sí | Supabase | Service role key (acceso completo a la DB) |
| `SUPABASE_ANON_KEY` | No | Sí | Supabase | Anonymous key (fallback, acceso limitado) |
| `REDIS_URL` | No | No | Redis | URL de conexión (default: `redis://localhost:6379`) |

## Google (Deprecated)

| Variable | Requerida | Privada | Servicio | Descripción |
|----------|-----------|---------|----------|-------------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | No | Sí | Google Sheets | JSON raw del service account (deprecated → Supabase) |
| `GOOGLE_APPLICATION_CREDENTIALS` | No | Sí | Google Sheets | Path al archivo de credenciales (alternativa) |

## Servidor y Seguridad

| Variable | Requerida | Privada | Servicio | Descripción |
|----------|-----------|---------|----------|-------------|
| `API_KEYS` | No | Sí | FastAPI | Lista de Bearer tokens separados por coma. Si vacío, acceso abierto |
| `API_SECRET_KEY` | No | Sí | FastAPI | Secret key para auth |
| `API_CORS_ORIGINS` | No | No | FastAPI | Orígenes CORS permitidos (separados por coma) |

## Feature Flags y Configuración

| Variable | Requerida | Privada | Servicio | Descripción |
|----------|-----------|---------|----------|-------------|
| `ENABLE_AI_ANALYSIS` | No | No | Feature flag | Habilitar/deshabilitar análisis AI |
| `CACHE_TTL_HOURS` | No | No | Cache | Duración del cache en horas (default: 24 en .env, 168 en código = 7 días) |
| `MAX_CONCURRENT_JOBS` | No | No | Worker | Máximo de jobs paralelos (default: 5) |
| `REQUESTS_PER_SECOND` | No | No | Scraper | Rate limiting de requests HTTP (default: 2) |
| `USER_AGENT` | No | No | Scraper | User agent custom para requests |
| `PLAYWRIGHT_HEADLESS` | No | No | Playwright | Modo headless del browser (default: true) |

## Frontend

| Variable | Requerida | Privada | Servicio | Descripción |
|----------|-----------|---------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Sí | No | Next.js | URL del backend API (default: `http://localhost:8000`) |

## Notas
- Todas las variables privadas van en `.env` (gitignored)
- `NEXT_PUBLIC_*` son las únicas expuestas al browser
- Para producción en Railway, las variables se configuran en el dashboard
- `SIMILARWEB_API_KEY` existe en .env.example pero no se usa (stub)
