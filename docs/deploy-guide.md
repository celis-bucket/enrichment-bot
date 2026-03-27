# Guía de Deploy

## Entornos

### Local (Desarrollo)
**Comando**: `docker-compose up`

**Servicios**:
| Servicio | Puerto | Imagen | Descripción |
|----------|--------|--------|-------------|
| Redis | 6379 | redis:7-alpine | Cache + job queue |
| Backend | 8000 | Dockerfile (root) | FastAPI API |
| Worker | — | Mismo que backend | `python workers/enrichment_worker.py` |
| Frontend | 3002 | Dockerfile (frontend/) | Next.js dev server |

**Volúmenes** (hot reload): `./backend`, `./tools`, `./workflows`, `./.tmp`

**Requisitos**:
1. Docker + Docker Compose instalados
2. `.env` con todas las API keys (copiar de `.env.example`)
3. `frontend/.env.local` con `NEXT_PUBLIC_API_URL=http://localhost:8000`

**Comandos**:
```bash
# Iniciar todo
docker-compose up

# Solo backend + redis (sin frontend)
docker-compose up redis backend

# Rebuild después de cambios en requirements
docker-compose up --build

# Ver logs de un servicio
docker-compose logs -f backend
```

---

### Producción (Railway.app)
**URL**: `enrichment-bot-production-943a.up.railway.app`
**Builder**: Dockerfile (Python 3.11-slim)
**Workers**: 2 (Uvicorn)

**Configuración** (`railway.toml`):
```toml
[build]
builder = "DOCKERFILE"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

**Health check**: `GET /health` → verifica Redis + Supabase + workers

**Variables de entorno**: Se configuran en el dashboard de Railway (Settings → Variables)

**Deploy automático**: Push a `main` → Railway detecta el Dockerfile → build → deploy

---

## CI/CD

### GitHub Actions
**Archivo**: `.github/workflows/logistics-cron.yml`
**Schedule**: Lunes 8:00 UTC (3:00 AM Colombia)
**Trigger manual**: Sí (workflow_dispatch con inputs --force y --limit)

**Lo que hace**:
1. Checkout del repo
2. Instala Python 3.11 + dependencias
3. Ejecuta `python tools/logistics/supabase_cron_runner.py`
4. Escanea Instagram comments de empresas en Supabase
5. Clasifica quejas logísticas con Claude

**Secrets requeridos**: `APIFY_API_TOKEN`, `ANTHROPIC_API_KEY`, `SEARCHAPI_API_KEY`, `SERPER_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`

---

## Proceso de Deploy (paso a paso)

### Backend (Railway)
1. Hacer cambios en `tools/`, `backend/`, o `workflows/`
2. Commit y push a `main`
3. Railway detecta el push y hace build automático
4. Verificar health check: `GET /health` → status OK
5. Verificar logs en Railway dashboard

### Frontend
- **Local only** por ahora (no desplegado en producción separada)
- Se ejecuta dentro de docker-compose en desarrollo
- [TODO: Deploy frontend a Vercel o similar]

---

## Rollback

### Railway
1. Ir al dashboard de Railway → Deployments
2. Seleccionar el deployment anterior
3. Click "Redeploy" en ese deployment
4. Alternativamente: `git revert HEAD && git push`

### Local
```bash
# Revertir al commit anterior
git log --oneline -5  # Ver commits recientes
git revert HEAD        # Revertir último commit
docker-compose up --build
```

---

## Troubleshooting

### Backend no inicia
- Verificar que `.env` tiene todas las keys requeridas
- Verificar que Redis está corriendo: `docker-compose ps`
- Ver logs: `docker-compose logs backend`

### Health check falla
- `redis: false` → Redis no está corriendo o `REDIS_URL` incorrecto
- `supabase: false` → `SUPABASE_URL` o `SUPABASE_SERVICE_KEY` inválidos
- Verificar conectividad de red desde Railway

### Enrichment falla silenciosamente
- Revisar `workflow_execution_log` en el resultado — cada step reporta status
- Campos None = el tool correspondiente falló
- Verificar créditos de APIs (Apify, Apollo, Serper)

### Cache stale
- Cache dura 7 días por dominio por tool
- Ubicación: `.tmp/cache/{domain}/{tool}.json`
- Para forzar refresh: `--skip-cache` en CLI o borrar `.tmp/cache/`

### Rate limits
| API | Límite | Síntoma |
|-----|--------|---------|
| Serper | 2,500/mes | HTTP 429 |
| SearchAPI | 100/mes | HTTP 429 |
| Apollo | 10K créditos/mes | HTTP 429 |
| Apify | Por créditos | Actor fails |

---

## Pre-deploy Checklist
- [ ] `.env` actualizado con todas las keys
- [ ] `docker-compose up` funciona localmente
- [ ] Health check `GET /health` retorna status OK
- [ ] [TODO: Agregar lint automatizado]
- [ ] [TODO: Agregar tests en CI/CD]
- [ ] [TODO: Deploy frontend separado]
