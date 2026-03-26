# Workflow: Enrichment Lite

## Objetivo
Triage rápido y barato de listas grandes de leads (800+) para identificar cuáles merecen enrichment completo.

## Cuándo usar
- Listas grandes de HubSpot o CRM con datos ruidosos
- Cuando necesitas filtrar rápido antes de invertir en enrichment full
- Presupuesto limitado de API credits

## Cuándo NO usar
- Una sola empresa (usa el enrichment normal)
- Necesitas datos completos (Apollo, catálogo, tráfico, etc.)
- Ya tienes URLs limpias y verificadas

## Input
CSV con 3 columnas (auto-detectadas):
- **Name**: nombre de empresa/marca (`company`, `nombre`, `empresa`, `brand`)
- **Website URL**: URL de la página web (`website`, `url`, `web`, `domain`)
- **Instagram URL**: URL de Instagram (`instagram`, `ig`)

Valores pueden estar vacíos, rotos, o mezclados. El pipeline maneja todo.

## Pipeline (7 pasos)

| # | Paso | Tool | Costo | Tiempo | Qué hace |
|---|------|------|-------|--------|----------|
| 0 | URL Resolution | `url_normalizer` + `google_search` | 0-$0.01 | 0-3s | Normaliza URL o busca en Google si no hay |
| 1 | Quick Scrape | `web_scraper` | $0 | 2-5s | Scraping rápido (15s timeout, 1 retry) |
| 2 | Platform Detection | `detect_ecommerce_platform` | $0 | <100ms | Shopify, VTEX, WooCommerce, etc. |
| 3 | Social Links | `extract_social_links` | $0 | <100ms | Extrae IG/FB/TikTok del HTML |
| 4 | Instagram Profile | `apify_instagram` + `instagram_scoring` | ~$0.005 | 5-10s | Followers, engagement, size/health score |
| 5 | Google Quick Check | `google_search` | $0.01 | 2-3s | 1 query: marca en top 10 de Google? |
| 6 | HubSpot Lookup | `hubspot_lookup` | $0 | 1-3s | Ya está en CRM? deals? stage? |
| 7 | Lite Scoring | inline | $0 | <1ms | Triage score 0-100 |

## Tools
- `tools/core/csv_reader.py` — Parser de CSV con auto-detección
- `tools/orchestrator/run_enrichment_lite.py` — Pipeline lite single company
- `tools/orchestrator/batch_runner_lite.py` — Runner concurrente + CLI

## Output
- Upsert a `enriched_companies` en Supabase (subset de campos)
- Campos nuevos: `enrichment_type`, `lite_triage_score`, `worth_full_enrichment`
- CSV resumen en `.tmp/lite_results_{batch_id}.csv`

## Scoring (lite_triage_score)

| Señal | Puntos | Criterio |
|-------|--------|----------|
| Platform target | +30 | Shopify o VTEX |
| Facebook Commerce | +15 | Solo IG, sin web, >500 followers |
| Instagram grande | +30 | >= 5,000 followers |
| Instagram mediano | +15 | >= 1,000 followers |
| Google top 10 | +20 | Marca en primeros 10 resultados orgánicos |
| URL resuelta | +10 | Se pudo llegar a la página web |
| Geografía COL/MEX | +10 | Colombia o México |
| Ya es cliente | -50 | HubSpot deal stage avanzado |

**worth_full_enrichment = score >= 40**

## Costos

| 800 leads | Costo |
|-----------|-------|
| Google Quick Check | ~$8 |
| URL Resolution (Google) | ~$3 |
| Instagram Profile | ~$3 |
| Otros | $0 |
| **Total** | **~$14 (~$0.02/empresa)** |

## Tiempo
- ~5-10s por empresa
- Con 5 workers concurrentes: ~20 minutos para 800 leads
- vs Full enrichment: ~10 horas, ~$400+

## CLI

```bash
# Básico
python tools/orchestrator/batch_runner_lite.py leads.csv

# Test con 10 leads
python tools/orchestrator/batch_runner_lite.py leads.csv --dry-run 10

# Personalizado
python tools/orchestrator/batch_runner_lite.py leads.csv \
  --workers 8 \
  --batch-id hubspot-mar26 \
  --country Colombia

# Columnas explícitas
python tools/orchestrator/batch_runner_lite.py leads.csv \
  --name-col "Company name" \
  --website-col "Website URL" \
  --ig-col "Instagram"
```

## Edge Cases
- **URL rota**: intenta Google search con nombre; si falla, solo procesa IG
- **Solo IG, sin web**: clasifica como `facebook_commerce`, usa bio para buscar website
- **Sin URL ni IG**: intenta Google search; si falla, score=0, skip
- **Ya tiene full enrichment**: salta (no sobreescribe)
- **HubSpot cliente existente**: penaliza -50 puntos (no vale la pena re-enriquecer)
- **CSV con BOM**: maneja utf-8-sig automáticamente
- **Duplicados**: dedup por dominio o por IG username

## Migración Supabase
Ejecutar **antes** del primer uso:
```sql
-- tools/export/migration_enrichment_lite.sql
ALTER TABLE enriched_companies
ADD COLUMN IF NOT EXISTS enrichment_type TEXT,
ADD COLUMN IF NOT EXISTS lite_triage_score SMALLINT,
ADD COLUMN IF NOT EXISTS worth_full_enrichment BOOLEAN;

CREATE INDEX IF NOT EXISTS idx_ec_enrichment_type ON enriched_companies (enrichment_type);
CREATE INDEX IF NOT EXISTS idx_ec_lite_score ON enriched_companies (lite_triage_score DESC NULLS LAST);
```
