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
)
from orchestrator.run_enrichment import run_enrichment

from api.models.schemas import (
    HealthResponse,
    SyncEnrichmentRequest,
    WorkflowStep,
    DuplicateCheckResponse,
    CompanyListItem,
    CompanyListResponse,
    FeedbackRequest,
    FeedbackItem,
    FeedbackListResponse,
)


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
        # Prediction
        "prediction": pred_model,
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

        # Fetch all matching rows (PostgREST doesn't support ILIKE via simple eq)
        columns = (
            "id,domain,company_name,platform,category,geography,"
            "ig_followers,ig_size_score,ig_health_score,meta_active_ads_count,"
            "contact_name,contact_email,predicted_orders_p50,predicted_orders_p90,prediction_confidence,"
            "tool_coverage_pct,updated_at"
        )
        rows = client.select(
            "enriched_companies",
            columns=columns,
            eq=eq_filters if eq_filters else None,
            order="updated_at.desc",
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
            "prediction": prediction,
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


# Run with: uvicorn api.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
