# Feedback Review Workflow

## Objective
Recoger todo el feedback no resuelto de usuarios del Enrichment Agent, organizarlo por sección/dashboard, y producir un prompt estructurado para Claude Code donde se planifican los arreglos.

## Required Inputs
Ninguno — lee directamente de la tabla `enrichment_feedback` en Supabase.

## Tools Used

| Step | Tool | Purpose |
|------|------|---------|
| 1 | `tools/feedback/fetch_unresolved.py` | Traer feedback no resuelto de Supabase |
| 2 | *(agente)* | Presentar resumen y prompt al usuario |

## Steps

### Step 1: Fetch Unresolved Feedback
```bash
cd tools && python -m feedback.fetch_unresolved
```

El tool retorna:
- `by_section`: feedback agrupado por sección (overview, instagram, catalog, contacts, meta_ads, prediction, traffic, hubspot, tiktok_ads, general, leads)
- `total`: cantidad total de items pendientes
- `prompt`: texto formateado listo para pegar en Claude Code

Si `total == 0`, reportar "No hay feedback pendiente" y terminar.

### Step 2: Presentar al Usuario
Mostrar:
1. Resumen con conteo por sección
2. El prompt completo generado

El usuario copia el prompt a Claude Code para planificar qué arreglar.

### Step 3: Resolver Feedback
Después de implementar arreglos, marcar cada item como resuelto:

```
PATCH /api/v2/feedback/{feedback_id}/resolve
Body: {"resolved_note": "Descripción del arreglo aplicado"}
```

O vía Python:
```python
from export.supabase_writer import get_client, resolve_feedback
client = get_client()
resolve_feedback(client, "feedback-uuid", "Corregido en commit abc123")
```

## Secciones de Feedback

| Section Key | Dashboard | Descripción |
|-------------|-----------|-------------|
| `overview` | Analyze | Datos generales de la empresa |
| `instagram` | Analyze | Métricas de Instagram |
| `catalog` | Analyze | Catálogo de productos |
| `contacts` | Analyze | Contactos de Apollo |
| `meta_ads` | Analyze | Anuncios de Meta |
| `prediction` | Analyze | Estimación de órdenes |
| `traffic` | Analyze | Tráfico y demanda |
| `hubspot` | Analyze | Datos de HubSpot CRM |
| `tiktok_ads` | Analyze | Anuncios de TikTok |
| `general` | Analyze | Feedback general |
| `leads` | Leads | Feedback sobre leads |

## Edge Cases
- Sin feedback pendiente → reportar y terminar
- Falla de conexión a Supabase → retornar error, no crashear
- Feedback de dominios eliminados → mostrar igual (puede indicar datos perdidos)
