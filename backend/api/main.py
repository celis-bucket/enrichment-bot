"""
FastAPI Application - E-commerce Enrichment API

Main application entry point with routes, middleware, and configuration.
"""

import os
import sys
import time
import json
import asyncio
import queue
import threading
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Security, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
import redis

# Add tools directory to path for imports
TOOLS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'tools')
sys.path.insert(0, TOOLS_PATH)

# Import enrichment tools
from export.supabase_writer import (
    get_client as get_supabase_client,
    upsert_enrichment,
    check_domain_exists as sb_check_domain,
    ping as supabase_ping,
    insert_feedback,
    get_feedback,
    get_all_unresolved_feedback,
    resolve_feedback,
)
from orchestrator.run_enrichment import run_enrichment

from pydantic import BaseModel as PydanticBaseModel, Field as PydanticField
from api.models.schemas import (
    HealthResponse,
    SyncEnrichmentRequest,
    WorkflowStep,
    DuplicateCheckResponse,
    CompanyListItem,
    CompanyListResponse,
    LeadListItem,
    LeadListResponse,
    FeedbackRequest,
    FeedbackItem,
    FeedbackListResponse,
    FeedbackResolveRequest,
    UnresolvedFeedbackResponse,
    HubSpotDetailResponse,
    TikTokShopWeeklyItem,
    TikTokWeeklyResponse,
    TikTokShopHistoryResponse,
    TikTokShopHistoryItem,
    TikTokShopForDomainResponse,
)
from hubspot.hubspot_lookup import get_company_detail


# Load environment variables
load_dotenv()

# Redis connection
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_client = None


supabase_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    global redis_client, supabase_client
    try:
        redis_client = redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
        print(f"[OK] Connected to Redis at {redis_url}")
    except Exception as e:
        print(f"[WARN] Redis not available (sync endpoint will still work): {e}")
        redis_client = None

    try:
        supabase_client = get_supabase_client()
        supabase_ping(supabase_client)
        print("[OK] Connected to Supabase")
    except Exception as e:
        print(f"[WARN] Supabase not available: {e}")
        supabase_client = None

    yield

    # Shutdown
    if redis_client:
        redis_client.close()
        print("[OK] Redis connection closed")


# Initialize FastAPI app
app = FastAPI(
    title="E-commerce Enrichment API",
    description="API for analyzing e-commerce websites and extracting business intelligence",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
cors_origins = os.getenv('API_CORS_ORIGINS', 'http://localhost:3000,http://localhost:3001,http://localhost:3002,https://enrichment-bot-psi.vercel.app').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== API Key Authentication =====

security = HTTPBearer()

# Load valid API keys from env (comma-separated)
_valid_api_keys = set(
    k.strip() for k in os.getenv('API_KEYS', '').split(',') if k.strip()
)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security),
):
    """Validate Bearer token against configured API_KEYS."""
    if not _valid_api_keys:
        # No keys configured = auth disabled (open access)
        return credentials.credentials if credentials else None
    if credentials.credentials not in _valid_api_keys:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials


# ===== Health Check Endpoint =====

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint to verify API and dependencies are running.
    """
    # Check Redis connection
    redis_status = "disconnected"
    if redis_client:
        try:
            redis_client.ping()
            redis_status = "connected"
        except:
            redis_status = "error"

    # Check worker count (from Redis queue)
    worker_count = 0
    if redis_client and redis_status == "connected":
        try:
            # This would be populated by workers registering themselves
            worker_count = len(redis_client.smembers('active_workers'))
        except:
            worker_count = 0

    # Check Supabase connection
    supabase_status = "disconnected"
    if supabase_client:
        try:
            supabase_ping(supabase_client)
            supabase_status = "connected"
        except:
            supabase_status = "error"

    is_healthy = supabase_status == "connected"
    return HealthResponse(
        status="healthy" if is_healthy else "degraded",
        redis=redis_status,
        workers=worker_count,
        timestamp=datetime.utcnow()
    )


# ===== Root Endpoint =====

@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "name": "E-commerce Enrichment API",
        "version": "1.0.0",
        "description": "Analyze e-commerce websites for Melonn enrichment team",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "enrichment": "/api/v2/enrichment/analyze-stream"
        }
    }



# ===== V2: Enrichment Flow V2 =====





def _run_prediction(enrichment_result) -> dict:
    """Run the orders estimator on an enrichment result. Returns prediction dict."""
    try:
        import pandas as pd
        import numpy as np

        # Add orders_estimator parent to path
        estimator_path = os.path.join(TOOLS_PATH, "..")
        if estimator_path not in sys.path:
            sys.path.insert(0, estimator_path)

        from tools.orders_estimator.predict import load_models, predict_batch

        # Build a single-row DataFrame from enrichment result
        row = {
            "platform": enrichment_result.platform,
            "category": enrichment_result.category,
            "ig_followers": enrichment_result.ig_followers,
            "ig_engagement_rate": enrichment_result.ig_engagement_rate,
            "ig_size_score": enrichment_result.ig_size_score,
            "ig_health_score": enrichment_result.ig_health_score,
            "product_count": enrichment_result.product_count,
            "avg_price": enrichment_result.avg_price,
            "price_range_min": enrichment_result.price_range_min,
            "price_range_max": enrichment_result.price_range_max,
            "estimated_monthly_visits": enrichment_result.estimated_monthly_visits,
            "brand_demand_score": enrichment_result.brand_demand_score,
            "site_serp_coverage_score": enrichment_result.site_serp_coverage_score,
            "number_employes": enrichment_result.number_employes,
            "meta_active_ads_count": enrichment_result.meta_active_ads_count,
            "currency": enrichment_result.currency,
        }
        df = pd.DataFrame([row])

        models = load_models()
        result_df = predict_batch(df, loaded=models)

        return {
            "predicted_orders_p10": int(result_df["predicted_orders_p10"].iloc[0]),
            "predicted_orders_p50": int(result_df["predicted_orders_p50"].iloc[0]),
            "predicted_orders_p90": int(result_df["predicted_orders_p90"].iloc[0]),
            "prediction_confidence": result_df["prediction_confidence"].iloc[0],
        }
    except Exception as e:
        import traceback
        print(f"[WARN] Orders prediction failed: {e}", flush=True)
        traceback.print_exc()
        return None


def _write_to_supabase(enrichment_result, prediction: dict) -> None:
    """Upsert a single enrichment result into Supabase."""
    try:
        client = supabase_client or get_supabase_client()
        upsert_enrichment(client, enrichment_result, prediction)
    except Exception as e:
        print(f"[WARN] Supabase write failed: {e}")


def _build_v2_response(enrichment_result, prediction: dict) -> dict:
    """Build the V2 results dict for the frontend."""
    pred_model = None
    if prediction:
        pred_model = {
            "predicted_orders_p10": prediction["predicted_orders_p10"],
            "predicted_orders_p50": prediction["predicted_orders_p50"],
            "predicted_orders_p90": prediction["predicted_orders_p90"],
            "prediction_confidence": prediction["prediction_confidence"],
        }

    # Build Meta Ad Library URL from company name or domain
    meta_ad_library_url = None
    if enrichment_result.meta_active_ads_count is not None:
        search_term = enrichment_result.company_name or enrichment_result.domain or ""
        if search_term:
            import urllib.parse
            encoded = urllib.parse.quote(search_term)
            meta_ad_library_url = (
                f"https://www.facebook.com/ads/library/"
                f"?active_status=active&ad_type=all&country=CO"
                f"&q={encoded}&search_type=keyword_unordered&media_type=all"
            )

    # Build TikTok Ads Library URL from company name or domain
    tiktok_ads_library_url = None
    if enrichment_result.tiktok_active_ads_count is not None:
        search_term = enrichment_result.company_name or enrichment_result.domain or ""
        if search_term:
            import urllib.parse
            encoded = urllib.parse.quote(search_term)
            tiktok_ads_library_url = (
                f"https://library.tiktok.com/ads"
                f"?region=all&adv_name={encoded}&sort_by=last_shown_date"
            )

    return {
        # Identity
        "company_name": enrichment_result.company_name,
        "domain": enrichment_result.domain,
        # Platform
        "platform": enrichment_result.platform,
        "platform_confidence": enrichment_result.platform_confidence,
        # Geography
        "geography": enrichment_result.geography,
        "geography_confidence": enrichment_result.geography_confidence,
        # Category
        "category": enrichment_result.category,
        "category_confidence": enrichment_result.category_confidence,
        "category_evidence": enrichment_result.category_evidence,
        # Social
        "instagram_url": enrichment_result.instagram_url,
        "ig_followers": enrichment_result.ig_followers,
        "ig_size_score": enrichment_result.ig_size_score,
        "ig_health_score": enrichment_result.ig_health_score,
        "fb_followers": enrichment_result.fb_followers,
        "tiktok_followers": enrichment_result.tiktok_followers,
        # Company / Apollo
        "company_linkedin": enrichment_result.company_linkedin,
        "contact_name": enrichment_result.contact_name,
        "contact_email": enrichment_result.contact_email,
        "number_employes": enrichment_result.number_employes,
        "contacts": enrichment_result.contacts_list or [],
        # Meta Ads
        "meta_active_ads_count": enrichment_result.meta_active_ads_count,
        "meta_ad_library_url": meta_ad_library_url,
        # TikTok Ads
        "tiktok_active_ads_count": enrichment_result.tiktok_active_ads_count,
        "tiktok_ads_library_url": tiktok_ads_library_url,
        # Catalog
        "product_count": enrichment_result.product_count,
        "avg_price": enrichment_result.avg_price,
        "price_range_min": enrichment_result.price_range_min,
        "price_range_max": enrichment_result.price_range_max,
        "currency": enrichment_result.currency,
        # Traffic
        "estimated_monthly_visits": enrichment_result.estimated_monthly_visits,
        "traffic_confidence": enrichment_result.traffic_confidence,
        "signals_used": enrichment_result.signals_used,
        # Google Demand
        "brand_demand_score": enrichment_result.brand_demand_score,
        "site_serp_coverage_score": enrichment_result.site_serp_coverage_score,
        "google_confidence": enrichment_result.google_confidence,
        # HubSpot CRM
        "hubspot_company_id": enrichment_result.hubspot_company_id,
        "hubspot_company_url": enrichment_result.hubspot_company_url,
        "hubspot_deal_count": enrichment_result.hubspot_deal_count,
        "hubspot_deal_stage": enrichment_result.hubspot_deal_stage,
        "hubspot_contact_exists": enrichment_result.hubspot_contact_exists,
        "hubspot_lifecycle_label": enrichment_result.hubspot_lifecycle_label,
        "hubspot_last_contacted": enrichment_result.hubspot_last_contacted,
        # Retail Channels
        "has_distributors": enrichment_result.has_distributors,
        "has_own_stores": enrichment_result.has_own_stores,
        "own_store_count_col": enrichment_result.own_store_count_col,
        "own_store_count_mex": enrichment_result.own_store_count_mex,
        "has_multibrand_stores": enrichment_result.has_multibrand_stores,
        "multibrand_store_names": enrichment_result.multibrand_store_names or [],
        "on_mercadolibre": enrichment_result.on_mercadolibre,
        "on_amazon": enrichment_result.on_amazon,
        "on_rappi": enrichment_result.on_rappi,
        "on_walmart": enrichment_result.on_walmart,
        "on_liverpool": enrichment_result.on_liverpool,
        "on_coppel": enrichment_result.on_coppel,
        "on_tiktok_shop": enrichment_result.on_tiktok_shop,
        "marketplace_names": enrichment_result.marketplace_names or [],
        "retail_confidence": enrichment_result.retail_confidence,
        # Prediction
        "prediction": pred_model,
        # Potential Scoring
        "ecommerce_size_score": enrichment_result.ecommerce_size_score,
        "retail_size_score": enrichment_result.retail_size_score,
        "combined_size_score": enrichment_result.combined_size_score,
        "fit_score": enrichment_result.fit_score,
        "overall_potential_score": enrichment_result.overall_potential_score,
        "potential_tier": enrichment_result.potential_tier,
        # Execution meta
        "tool_coverage_pct": enrichment_result.tool_coverage_pct,
        "total_runtime_sec": enrichment_result.total_runtime_sec,
        "cost_estimate_usd": enrichment_result.cost_estimate_usd,
        # Workflow
        "workflow_log": json.loads(enrichment_result.workflow_execution_log or "[]"),
    }


@app.post("/api/v2/enrichment/analyze-stream", tags=["Enrichment V2"])
async def analyze_stream_v2(request: SyncEnrichmentRequest, api_key: str = Depends(verify_api_key)):
    """
    V2 SSE streaming enrichment endpoint.

    Runs the full enrichment pipeline (including Apollo + category + traffic +
    demand) with real-time step-by-step progress via Server-Sent Events.
    After enrichment, runs the orders estimator and saves to Supabase.
    """
    step_queue: queue.Queue = queue.Queue()

    def on_step(name: str, status: str, duration_ms: int, detail: str = ""):
        step_queue.put({"type": "step", "step": name, "status": status,
                        "duration_ms": duration_ms, "detail": detail})

    def run_pipeline():
        """Run the synchronous pipeline in a background thread."""
        try:
            result = run_enrichment(
                raw_url=request.url,
                country=request.geography,
                skip_apollo=False,
                enable_google_demand=True,
                on_step=on_step,
            )
            step_queue.put({"type": "_enrichment_done", "result": result})
        except Exception as e:
            step_queue.put({"type": "error", "detail": str(e)})

    async def event_generator():
        # Start pipeline in a thread so we don't block the event loop
        loop = asyncio.get_event_loop()
        pipeline_thread = threading.Thread(target=run_pipeline, daemon=True)
        pipeline_thread.start()

        enrichment_result = None

        # Stream step events as they arrive
        while True:
            try:
                msg = await loop.run_in_executor(None, lambda: step_queue.get(timeout=300))
            except Exception:
                yield f"data: {json.dumps({'type': 'error', 'detail': 'Pipeline timeout'})}\n\n"
                break

            if msg["type"] == "step":
                yield f"data: {json.dumps(msg)}\n\n"
            elif msg["type"] == "_enrichment_done":
                enrichment_result = msg["result"]
                break
            elif msg["type"] == "error":
                yield f"data: {json.dumps(msg)}\n\n"
                break

        if enrichment_result is None:
            return

        # Run orders estimator
        yield f"data: {json.dumps({'type': 'step', 'step': 'Orders estimation', 'status': 'running', 'duration_ms': 0, 'detail': ''})}\n\n"
        t0 = time.time()
        prediction = await loop.run_in_executor(None, _run_prediction, enrichment_result)
        ms = int((time.time() - t0) * 1000)
        pred_status = "ok" if prediction else "warn"
        yield f"data: {json.dumps({'type': 'step', 'step': 'Orders estimation', 'status': pred_status, 'duration_ms': ms, 'detail': ''})}\n\n"

        # Save to Supabase
        yield f"data: {json.dumps({'type': 'step', 'step': 'Saving to database', 'status': 'running', 'duration_ms': 0, 'detail': ''})}\n\n"
        t0 = time.time()
        await loop.run_in_executor(None, _write_to_supabase, enrichment_result, prediction)
        ms = int((time.time() - t0) * 1000)
        yield f"data: {json.dumps({'type': 'step', 'step': 'Saving to database', 'status': 'ok', 'duration_ms': ms, 'detail': ''})}\n\n"

        # Send final results
        final = _build_v2_response(enrichment_result, prediction)
        yield f"data: {json.dumps({'type': 'result', 'data': final})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/v2/enrichment/check-duplicate", response_model=DuplicateCheckResponse,
         tags=["Enrichment V2"])
async def check_duplicate(domain: str = Query(..., description="Domain to check"), api_key: str = Depends(verify_api_key)):
    """Check if a domain already exists in the enriched_companies table."""
    try:
        client = supabase_client or get_supabase_client()
        result = sb_check_domain(client, domain)
        return DuplicateCheckResponse(**result)
    except Exception:
        return DuplicateCheckResponse(exists=False)


# ===== Company List Endpoints =====

@app.get("/api/v2/enrichment/companies", response_model=CompanyListResponse,
         tags=["Companies"])
async def list_companies(
    api_key: str = Depends(verify_api_key),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    search: str = Query("", description="Search by company name or domain"),
    category: str = Query("", description="Filter by category"),
    geography: str = Query("", description="Filter by geography"),
    potential_tier: str = Query("", description="Filter by potential tier"),
    sort_by: str = Query("updated_at", description="Sort by: updated_at, overall_potential_score, predicted_orders_p90"),
    hide_in_hubspot: bool = Query(False, description="Hide companies already in HubSpot CRM"),
):
    """Paginated list of enriched companies."""
    try:
        client = supabase_client or get_supabase_client()

        # Build filters
        eq_filters = {}
        if category:
            eq_filters["category"] = category
        if geography:
            eq_filters["geography"] = geography
        if potential_tier:
            eq_filters["potential_tier"] = potential_tier

        # NULL filters (hide companies already in HubSpot)
        null_filters = None
        if hide_in_hubspot:
            null_filters = {"hubspot_company_id": True}

        # Sort order
        valid_sort_fields = {"updated_at", "overall_potential_score", "predicted_orders_p90"}
        sort_field = sort_by if sort_by in valid_sort_fields else "updated_at"
        order = f"{sort_field}.desc.nullslast"

        # Fetch all matching rows (PostgREST doesn't support ILIKE via simple eq)
        columns = (
            "id,domain,company_name,platform,category,geography,"
            "ig_followers,ig_size_score,ig_health_score,meta_active_ads_count,"
            "contact_name,contact_email,predicted_orders_p50,predicted_orders_p90,prediction_confidence,"
            "hubspot_company_id,hubspot_deal_count,hubspot_deal_stage,"
            "has_distributors,has_own_stores,has_multibrand_stores,multibrand_store_names,"
            "on_mercadolibre,on_amazon,on_rappi,on_walmart,on_liverpool,on_coppel,on_tiktok_shop,"
            "marketplace_names,retail_confidence,"
            "ecommerce_size_score,retail_size_score,combined_size_score,"
            "fit_score,overall_potential_score,potential_tier,"
            "tool_coverage_pct,updated_at"
        )
        rows = client.select(
            "enriched_companies",
            columns=columns,
            eq=eq_filters if eq_filters else None,
            is_null=null_filters,
            order=order,
        )

        # Client-side search filter (PostgREST text search requires FTS setup)
        if search:
            s = search.lower()
            rows = [r for r in rows if s in (r.get("company_name") or "").lower()
                    or s in (r.get("domain") or "").lower()]

        total = len(rows)

        # Paginate
        start = (page - 1) * limit
        page_rows = rows[start:start + limit]

        companies = [CompanyListItem(**r) for r in page_rows]
        return CompanyListResponse(companies=companies, total=total, page=page, limit=limit)
    except Exception as e:
        print(f"[WARN] Company list failed: {e}")
        return CompanyListResponse(companies=[], total=0, page=page, limit=limit)


# ===== Leads Dashboard Endpoints =====

@app.get("/api/v2/leads", response_model=LeadListResponse, tags=["Leads"])
async def list_leads(
    api_key: str = Depends(verify_api_key),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=5000),
    search: str = Query("", description="Search by company name or domain"),
    platform: str = Query("", description="Filter by platform"),
    worth_full_enrichment: str = Query("", description="Filter: true/false"),
    enrichment_type: str = Query("", description="Filter: lite/full"),
    lead_stage: str = Query("", description="Filter by lead stage"),
    sort_by: str = Query("lite_triage_score", description="Sort by: lite_triage_score, ig_followers, updated_at"),
):
    """Paginated list of leads (source=hubspot_leads)."""
    try:
        client = supabase_client or get_supabase_client()

        eq_filters = {"source": "hubspot_leads"}
        if platform:
            eq_filters["platform"] = platform
        if enrichment_type:
            eq_filters["enrichment_type"] = enrichment_type
        if lead_stage:
            eq_filters["hs_lead_stage"] = lead_stage

        valid_sort = {"lite_triage_score", "ig_followers", "updated_at"}
        sort_field = sort_by if sort_by in valid_sort else "lite_triage_score"
        order = f"{sort_field}.desc.nullslast"

        columns = (
            "id,domain,clean_url,company_name,platform,geography,"
            "ig_followers,ig_size_score,lite_triage_score,worth_full_enrichment,"
            "enrichment_type,hubspot_company_id,hubspot_deal_stage,hubspot_deal_count,"
            "hs_lead_stage,hs_lead_label,hs_lead_owner,hs_last_lost_deal_date,hs_lead_created_at,"
            "hs_last_activity_date,hs_activity_count,hs_open_tasks_count,"
            "overall_potential_score,potential_tier,predicted_orders_p90,"
            "has_distributors,has_own_stores,has_multibrand_stores,multibrand_store_names,"
            "on_mercadolibre,on_amazon,on_rappi,on_walmart,on_liverpool,on_coppel,on_tiktok_shop,"
            "marketplace_names,retail_confidence,"
            "tool_coverage_pct,updated_at"
        )
        rows = client.select(
            "enriched_companies",
            columns=columns,
            eq=eq_filters,
            order=order,
        )

        # Client-side filters
        if search:
            s = search.lower()
            rows = [r for r in rows if s in (r.get("company_name") or "").lower()
                    or s in (r.get("domain") or "").lower()]

        if worth_full_enrichment:
            wfe = worth_full_enrichment.lower() == "true"
            rows = [r for r in rows if r.get("worth_full_enrichment") == wfe]

        # Exclude companies with Cierre ganado or active deals (already being worked)
        _exclude_stages = {"cierre ganado", "consideracion", "parametrización", "onboarding"}
        rows = [r for r in rows if not (
            r.get("hubspot_deal_stage") and r["hubspot_deal_stage"].lower() in _exclude_stages
        )]

        total = len(rows)
        worth_full_count = sum(1 for r in rows if r.get("worth_full_enrichment"))
        fully_enriched_count = sum(1 for r in rows if r.get("enrichment_type") == "full")

        start = (page - 1) * limit
        page_rows = rows[start:start + limit]

        companies = [LeadListItem(**r) for r in page_rows]
        return LeadListResponse(
            companies=companies,
            total=total,
            page=page,
            limit=limit,
            total_leads=total,
            worth_full_count=worth_full_count,
            fully_enriched_count=fully_enriched_count,
        )
    except Exception as e:
        print(f"[WARN] Leads list failed: {e}")
        return LeadListResponse()


@app.post("/api/v2/leads/sync", tags=["Leads"])
async def sync_leads_endpoint(api_key: str = Depends(verify_api_key)):
    """Sync leads from HubSpot and run lite enrichment for new ones. Returns SSE stream."""
    from starlette.responses import StreamingResponse
    import json as _json
    import queue
    import threading

    progress_queue = queue.Queue()

    def _on_progress(msg: str):
        progress_queue.put({"type": "progress", "detail": msg})

    def _run_sync():
        try:
            from hubspot.sync_leads import sync_leads
            result = sync_leads(on_progress=_on_progress, max_enrich=0)
            progress_queue.put({"type": "result", "data": result})
        except Exception as e:
            progress_queue.put({"type": "error", "detail": str(e)})
        finally:
            progress_queue.put(None)  # sentinel

    thread = threading.Thread(target=_run_sync, daemon=True)
    thread.start()

    async def event_generator():
        while True:
            try:
                msg = progress_queue.get(timeout=600)
            except queue.Empty:
                yield f"data: {_json.dumps({'type': 'error', 'detail': 'Sync timeout'})}\n\n"
                break
            if msg is None:
                break
            yield f"data: {_json.dumps(msg)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/v2/enrichment/companies/{domain}", tags=["Companies"])
async def get_company(domain: str, api_key: str = Depends(verify_api_key)):
    """Get full enrichment data for a single company by domain."""
    try:
        client = supabase_client or get_supabase_client()
        rows = client.select(
            "enriched_companies",
            eq={"domain": domain.lower().strip()},
            limit=1,
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"Company not found: {domain}")

        row = rows[0]
        # Build prediction sub-object
        prediction = None
        if row.get("predicted_orders_p50") is not None:
            prediction = {
                "predicted_orders_p10": row.get("predicted_orders_p10"),
                "predicted_orders_p50": row.get("predicted_orders_p50"),
                "predicted_orders_p90": row.get("predicted_orders_p90"),
                "prediction_confidence": row.get("prediction_confidence"),
            }

        # Build Meta Ad Library URL
        meta_ad_library_url = None
        if row.get("meta_active_ads_count") is not None:
            import urllib.parse
            search_term = row.get("company_name") or row.get("domain") or ""
            if search_term:
                encoded = urllib.parse.quote(search_term)
                meta_ad_library_url = (
                    f"https://www.facebook.com/ads/library/"
                    f"?active_status=active&ad_type=all&country=CO"
                    f"&q={encoded}&search_type=keyword_unordered&media_type=all"
                )

        # Build TikTok Ads Library URL
        tiktok_ads_library_url = None
        if row.get("tiktok_active_ads_count") is not None:
            import urllib.parse
            search_term = row.get("company_name") or row.get("domain") or ""
            if search_term:
                encoded = urllib.parse.quote(search_term)
                tiktok_ads_library_url = (
                    f"https://library.tiktok.com/ads"
                    f"?region=all&adv_name={encoded}&sort_by=last_shown_date"
                )

        return {
            "company_name": row.get("company_name"),
            "domain": row.get("domain"),
            "platform": row.get("platform"),
            "platform_confidence": row.get("platform_confidence"),
            "geography": row.get("geography"),
            "geography_confidence": row.get("geography_confidence"),
            "category": row.get("category"),
            "category_confidence": row.get("category_confidence"),
            "category_evidence": row.get("category_evidence"),
            "instagram_url": row.get("instagram_url"),
            "ig_followers": row.get("ig_followers"),
            "ig_size_score": row.get("ig_size_score"),
            "ig_health_score": row.get("ig_health_score"),
            "fb_followers": row.get("fb_followers"),
            "tiktok_followers": row.get("tiktok_followers"),
            "company_linkedin": row.get("company_linkedin"),
            "contact_name": row.get("contact_name"),
            "contact_email": row.get("contact_email"),
            "number_employes": row.get("number_employes"),
            "contacts": row.get("contacts_list") or [],
            "meta_active_ads_count": row.get("meta_active_ads_count"),
            "meta_ad_library_url": meta_ad_library_url,
            "tiktok_active_ads_count": row.get("tiktok_active_ads_count"),
            "tiktok_ads_library_url": tiktok_ads_library_url,
            "product_count": row.get("product_count"),
            "avg_price": row.get("avg_price"),
            "price_range_min": row.get("price_range_min"),
            "price_range_max": row.get("price_range_max"),
            "currency": row.get("currency"),
            "estimated_monthly_visits": row.get("estimated_monthly_visits"),
            "traffic_confidence": row.get("traffic_confidence"),
            "signals_used": row.get("signals_used"),
            "brand_demand_score": row.get("brand_demand_score"),
            "site_serp_coverage_score": row.get("site_serp_coverage_score"),
            "google_confidence": row.get("google_confidence"),
            "hubspot_company_id": row.get("hubspot_company_id"),
            "hubspot_company_url": row.get("hubspot_company_url"),
            "hubspot_deal_count": row.get("hubspot_deal_count"),
            "hubspot_deal_stage": row.get("hubspot_deal_stage"),
            "hubspot_contact_exists": row.get("hubspot_contact_exists"),
            "hubspot_lifecycle_label": row.get("hubspot_lifecycle_label"),
            "hubspot_last_contacted": row.get("hubspot_last_contacted"),
            # Retail
            "has_distributors": row.get("has_distributors"),
            "has_own_stores": row.get("has_own_stores"),
            "own_store_count_col": row.get("own_store_count_col"),
            "own_store_count_mex": row.get("own_store_count_mex"),
            "has_multibrand_stores": row.get("has_multibrand_stores"),
            "multibrand_store_names": row.get("multibrand_store_names") or [],
            "on_mercadolibre": row.get("on_mercadolibre"),
            "on_amazon": row.get("on_amazon"),
            "on_rappi": row.get("on_rappi"),
            "on_walmart": row.get("on_walmart"),
            "on_liverpool": row.get("on_liverpool"),
            "on_coppel": row.get("on_coppel"),
            "on_tiktok_shop": row.get("on_tiktok_shop"),
            "retail_confidence": row.get("retail_confidence"),
            "prediction": prediction,
            # Potential Scoring
            "ecommerce_size_score": row.get("ecommerce_size_score"),
            "retail_size_score": row.get("retail_size_score"),
            "combined_size_score": row.get("combined_size_score"),
            "fit_score": row.get("fit_score"),
            "overall_potential_score": row.get("overall_potential_score"),
            "potential_tier": row.get("potential_tier"),
            "tool_coverage_pct": row.get("tool_coverage_pct"),
            "total_runtime_sec": row.get("total_runtime_sec"),
            "cost_estimate_usd": row.get("cost_estimate_usd"),
            "workflow_log": row.get("workflow_execution_log") or [],
            "updated_at": row.get("updated_at"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== HubSpot Detail Endpoint =====

@app.get("/api/v2/enrichment/hubspot/{company_id}", response_model=HubSpotDetailResponse,
         tags=["HubSpot"])
async def hubspot_detail(company_id: str, api_key: str = Depends(verify_api_key)):
    """Get extended HubSpot company detail for the history modal."""
    try:
        result = get_company_detail(company_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error", "Not found"))
        return result["data"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== Feedback Endpoints =====

@app.post("/api/v2/enrichment/{domain}/feedback", tags=["Feedback"])
async def submit_feedback(domain: str, request: FeedbackRequest, api_key: str = Depends(verify_api_key)):
    """Submit feedback on a specific enrichment section for a domain."""
    try:
        client = supabase_client or get_supabase_client()
        result = insert_feedback(
            client,
            domain=domain,
            section=request.section,
            comment=request.comment,
            suggested_value=request.suggested_value,
            created_by=request.created_by or "anonymous",
        )
        return {"id": result.get("id"), "saved": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v2/enrichment/{domain}/feedback", response_model=FeedbackListResponse, tags=["Feedback"])
async def list_feedback(domain: str, api_key: str = Depends(verify_api_key)):
    """Get all feedback for a domain."""
    try:
        client = supabase_client or get_supabase_client()
        rows = get_feedback(client, domain)
        items = [FeedbackItem(**r) for r in rows]
        return FeedbackListResponse(domain=domain, feedback=items, total=len(items))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v2/feedback/unresolved", response_model=UnresolvedFeedbackResponse, tags=["Feedback"])
async def list_unresolved_feedback(api_key: str = Depends(verify_api_key)):
    """Get all unresolved feedback across all domains."""
    try:
        client = supabase_client or get_supabase_client()
        rows = get_all_unresolved_feedback(client)
        items = [FeedbackItem(**r) for r in rows]
        return UnresolvedFeedbackResponse(feedback=items, total=len(items))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/v2/feedback/{feedback_id}/resolve", tags=["Feedback"])
async def resolve_feedback_item(feedback_id: str, request: FeedbackResolveRequest, api_key: str = Depends(verify_api_key)):
    """Mark a feedback item as resolved."""
    try:
        client = supabase_client or get_supabase_client()
        result = resolve_feedback(client, feedback_id, request.resolved_note)
        if not result:
            raise HTTPException(status_code=404, detail="Feedback not found")
        return {"resolved": True, "id": feedback_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== Retail Enrichment Endpoint =====

from retail.run_retail_enrichment import run_retail_enrichment


class RetailAnalyzeRequest(PydanticBaseModel):
    domain: str = PydanticField(..., description="E-commerce domain (e.g., youaresavvy.com)")
    geography: str = PydanticField("", description="Country code: COL, MEX, or empty for both")


@app.post("/api/v2/retail/analyze-stream", tags=["Retail"])
async def retail_analyze_stream(request: RetailAnalyzeRequest, api_key: str = Depends(verify_api_key)):
    """
    SSE streaming retail channel enrichment.
    Detects distributors, own stores, multi-brand stores, and marketplace presence.
    """
    step_queue: queue.Queue = queue.Queue()

    def on_step(name: str, status: str, duration_ms: int, detail: str = ""):
        step_queue.put({"type": "step", "step": name, "status": status,
                        "duration_ms": duration_ms, "detail": detail})

    def run_pipeline():
        try:
            # Read brand name from enriched_companies if available
            brand_name = request.domain.split(".")[0]
            geography = request.geography or None
            category = None
            try:
                client = supabase_client or get_supabase_client()
                rows = client.select(
                    "enriched_companies",
                    columns="company_name,geography,category",
                    eq={"domain": request.domain},
                    limit=1,
                )
                if rows:
                    brand_name = rows[0].get("company_name") or brand_name
                    geography = geography or rows[0].get("geography")
                    category = rows[0].get("category")
            except Exception:
                pass

            result = run_retail_enrichment(
                domain=request.domain,
                brand_name=brand_name,
                geography=geography,
                category=category,
                skip_cache=True,
                on_step=on_step,
            )
            step_queue.put({"type": "result", "data": result["data"], "steps": result["steps"]})
        except Exception as e:
            step_queue.put({"type": "error", "detail": str(e)})

    async def event_generator():
        loop = asyncio.get_event_loop()
        pipeline_thread = threading.Thread(target=run_pipeline, daemon=True)
        pipeline_thread.start()

        while True:
            try:
                msg = await loop.run_in_executor(None, lambda: step_queue.get(timeout=300))
            except Exception:
                yield f"data: {json.dumps({'type': 'error', 'detail': 'Pipeline timeout'})}\n\n"
                break

            if msg["type"] == "step":
                yield f"data: {json.dumps(msg)}\n\n"
            elif msg["type"] in ("result", "error"):
                yield f"data: {json.dumps(msg)}\n\n"
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ===== TikTok Shop Dashboard Endpoints =====

@app.get("/api/v2/tiktok/weekly", response_model=TikTokWeeklyResponse, tags=["TikTok"])
async def tiktok_weekly(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    category: str = Query("", description="Filter by category"),
    sort_by: str = Query("gmv", description="Sort: gmv, sales_count, wow_sales, wow_gmv"),
    search: str = Query("", description="Search shop name"),
    filter: str = Query("all", description="Filter: all, new, rising, falling"),
    api_key: str = Depends(verify_api_key),
):
    """Weekly TikTok Shop ranking with WoW deltas."""
    import requests as _requests

    try:
        client = supabase_client or get_supabase_client()

        # Get the two most recent week_start values
        weeks_resp = _requests.get(
            f"{client.rest_url}/tiktok_shop_weekly",
            headers=client.headers,
            params={"select": "week_start", "order": "week_start.desc", "limit": "2",
                    "week_start": "not.is.null"},
            timeout=15,
        )
        week_dates = list({r["week_start"] for r in weeks_resp.json()})
        week_dates.sort(reverse=True)

        if not week_dates:
            return TikTokWeeklyResponse()

        current_week = week_dates[0]
        prev_week = week_dates[1] if len(week_dates) > 1 else None

        # Fetch current week data
        params = {
            "select": "shop_name,company_name,category,rating,sales_count,gmv,products,influencers,fastmoss_url,week_start,matched_domain",
            "week_start": f"eq.{current_week}",
            "order": f"{'gmv' if sort_by in ('gmv', 'wow_gmv') else 'sales_count'}.desc.nullslast",
        }
        if category:
            params["category"] = f"ilike.*{category}*"
        if search:
            params["shop_name"] = f"ilike.*{search}*"

        cur_resp = _requests.get(
            f"{client.rest_url}/tiktok_shop_weekly",
            headers={**client.headers, "Prefer": "count=exact"},
            params=params,
            timeout=15,
        )
        current_shops = cur_resp.json()
        total_count = int(cur_resp.headers.get("content-range", "0-0/0").split("/")[-1])

        # Fetch previous week for deltas
        prev_lookup = {}
        if prev_week:
            prev_resp = _requests.get(
                f"{client.rest_url}/tiktok_shop_weekly",
                headers=client.headers,
                params={
                    "select": "shop_name,sales_count,gmv",
                    "week_start": f"eq.{prev_week}",
                },
                timeout=15,
            )
            for r in prev_resp.json():
                prev_lookup[r["shop_name"]] = r

        # Build items with deltas
        items = []
        for shop in current_shops:
            prev = prev_lookup.get(shop["shop_name"])
            is_new = prev is None and prev_week is not None

            wow_sales = None
            wow_gmv = None
            if prev:
                prev_sales = prev.get("sales_count")
                cur_sales = shop.get("sales_count")
                if prev_sales and cur_sales and prev_sales > 0:
                    wow_sales = round(((cur_sales - prev_sales) / prev_sales) * 100, 1)

                prev_gmv = prev.get("gmv")
                cur_gmv = shop.get("gmv")
                if prev_gmv and cur_gmv and prev_gmv > 0:
                    wow_gmv = round(((cur_gmv - prev_gmv) / prev_gmv) * 100, 1)

            items.append(TikTokShopWeeklyItem(
                shop_name=shop["shop_name"],
                company_name=shop.get("company_name"),
                category=shop.get("category"),
                rating=shop.get("rating"),
                sales_count=shop.get("sales_count"),
                gmv=shop.get("gmv"),
                products=shop.get("products"),
                influencers=shop.get("influencers"),
                fastmoss_url=shop.get("fastmoss_url"),
                week_start=shop.get("week_start", current_week),
                matched_domain=shop.get("matched_domain"),
                wow_sales_pct=wow_sales,
                wow_gmv_pct=wow_gmv,
                is_new=is_new,
            ))

        # Apply filter
        if filter == "new":
            items = [i for i in items if i.is_new]
        elif filter == "rising":
            items = [i for i in items if i.wow_sales_pct is not None and i.wow_sales_pct > 0]
        elif filter == "falling":
            items = [i for i in items if i.wow_sales_pct is not None and i.wow_sales_pct < 0]

        # Sort by WoW if requested
        if sort_by == "wow_sales":
            items.sort(key=lambda x: x.wow_sales_pct or 0, reverse=True)
        elif sort_by == "wow_gmv":
            items.sort(key=lambda x: x.wow_gmv_pct or 0, reverse=True)

        total_new = sum(1 for i in items if i.is_new) if filter == "all" else 0
        total_filtered = len(items)

        # Paginate
        start = (page - 1) * limit
        items = items[start:start + limit]

        return TikTokWeeklyResponse(
            shops=items,
            total=total_filtered if filter != "all" else total_count,
            page=page,
            limit=limit,
            week_start=current_week,
            prev_week_start=prev_week,
            total_new=total_new,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v2/tiktok/shop/{shop_name}/history", response_model=TikTokShopHistoryResponse, tags=["TikTok"])
async def tiktok_shop_history(shop_name: str, api_key: str = Depends(verify_api_key)):
    """Get weekly time-series for a single TikTok shop."""
    import requests as _requests

    try:
        client = supabase_client or get_supabase_client()
        resp = _requests.get(
            f"{client.rest_url}/tiktok_shop_weekly",
            headers=client.headers,
            params={
                "select": "shop_name,matched_domain,category,week_start,sales_count,gmv,products,rating",
                "shop_name": f"eq.{shop_name}",
                "order": "week_start.asc",
            },
            timeout=15,
        )
        rows = resp.json()
        if not rows:
            raise HTTPException(status_code=404, detail=f"Shop not found: {shop_name}")

        return TikTokShopHistoryResponse(
            shop_name=shop_name,
            matched_domain=rows[0].get("matched_domain"),
            category=rows[0].get("category"),
            history=[TikTokShopHistoryItem(
                week_start=r["week_start"],
                sales_count=r.get("sales_count"),
                gmv=r.get("gmv"),
                products=r.get("products"),
                rating=r.get("rating"),
            ) for r in rows],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v2/tiktok/shop-for-domain/{domain}", response_model=TikTokShopForDomainResponse, tags=["TikTok"])
async def tiktok_shop_for_domain(domain: str, api_key: str = Depends(verify_api_key)):
    """Get TikTok Shop data for a company by its domain (for enrichment card).

    Searches by matched_domain first, then falls back to fuzzy name matching
    against the company_name in enriched_companies.
    """
    import requests as _requests

    try:
        client = supabase_client or get_supabase_client()
        clean_domain = domain.lower().strip()

        # Strategy 1: Search by matched_domain (pre-computed during import)
        resp = _requests.get(
            f"{client.rest_url}/tiktok_shop_weekly",
            headers=client.headers,
            params={
                "select": "shop_name,sales_count,gmv,products,rating,influencers,fastmoss_url,week_start",
                "matched_domain": f"eq.{clean_domain}",
                "order": "week_start.desc",
                "limit": "2",
            },
            timeout=15,
        )
        rows = resp.json()

        # Strategy 2: If no match by domain, try by company name
        if not rows:
            # Get the company_name for this domain
            company_rows = client.select(
                "enriched_companies",
                columns="company_name",
                eq={"domain": clean_domain},
                limit=1,
            )
            company_name = (company_rows[0].get("company_name") or "") if company_rows else ""

            if company_name:
                # Search tiktok_shop_weekly by shop_name matching company_name
                resp = _requests.get(
                    f"{client.rest_url}/tiktok_shop_weekly",
                    headers=client.headers,
                    params={
                        "select": "shop_name,sales_count,gmv,products,rating,influencers,fastmoss_url,week_start",
                        "shop_name": f"ilike.{company_name}",
                        "order": "week_start.desc",
                        "limit": "2",
                    },
                    timeout=15,
                )
                rows = resp.json()

                # If exact match didn't work, try partial match
                if not rows:
                    resp = _requests.get(
                        f"{client.rest_url}/tiktok_shop_weekly",
                        headers=client.headers,
                        params={
                            "select": "shop_name,sales_count,gmv,products,rating,influencers,fastmoss_url,week_start",
                            "shop_name": f"ilike.*{company_name}*",
                            "order": "week_start.desc",
                            "limit": "2",
                        },
                        timeout=15,
                    )
                    rows = resp.json()

                # Update matched_domain for future lookups if we found a match
                if rows:
                    try:
                        _requests.patch(
                            f"{client.rest_url}/tiktok_shop_weekly",
                            headers=client.headers,
                            params={"shop_name": f"eq.{rows[0]['shop_name']}"},
                            json={"matched_domain": clean_domain},
                            timeout=10,
                        )
                    except Exception:
                        pass

        if not rows:
            return TikTokShopForDomainResponse(has_data=False)

        latest = rows[0]
        wow_sales = None
        wow_gmv = None

        if len(rows) > 1:
            prev = rows[1]
            if prev.get("sales_count") and latest.get("sales_count") and prev["sales_count"] > 0:
                wow_sales = round(((latest["sales_count"] - prev["sales_count"]) / prev["sales_count"]) * 100, 1)
            if prev.get("gmv") and latest.get("gmv") and prev["gmv"] > 0:
                wow_gmv = round(((latest["gmv"] - prev["gmv"]) / prev["gmv"]) * 100, 1)

        return TikTokShopForDomainResponse(
            shop_name=latest.get("shop_name"),
            sales_count=latest.get("sales_count"),
            gmv=latest.get("gmv"),
            products=latest.get("products"),
            rating=latest.get("rating"),
            influencers=latest.get("influencers"),
            fastmoss_url=latest.get("fastmoss_url"),
            week_start=latest.get("week_start"),
            wow_sales_pct=wow_sales,
            wow_gmv_pct=wow_gmv,
            has_data=True,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Run with: uvicorn api.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
