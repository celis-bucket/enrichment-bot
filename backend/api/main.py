"""
FastAPI Application - E-commerce Enrichment API

Main application entry point with routes, middleware, and configuration.
"""

import os
import sys
import time
import uuid
import json
import asyncio
import queue
import threading
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import redis

# Add tools directory to path for imports
TOOLS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'tools')
sys.path.insert(0, TOOLS_PATH)

# Import enrichment tools
from core.url_normalizer import normalize_url, extract_domain
from core.web_scraper import scrape_website
from detection.detect_ecommerce_platform import detect_platform_from_html
from detection.detect_geography import detect_geography_from_html
from social.extract_social_links import extract_social_links_from_html
from social.apify_instagram import get_instagram_metrics, extract_instagram_username
from ecommerce.scrape_product_catalog import scrape_product_catalog
from core.resolve_brand_url import resolve_brand_url
from export.google_sheets_writer import (
    get_gspread_client,
    create_or_open_spreadsheet,
    append_rows as sheets_append_rows,
    enrichment_result_to_row,
    read_existing_domains,
)
from orchestrator.run_enrichment import run_enrichment

from api.models.schemas import (
    HealthResponse,
    EnrichmentRequest,
    SyncEnrichmentRequest,
    JobResponse,
    JobDetailResponse,
    JobListResponse,
    ExportResponse,
    JobStatus,
    EnrichmentResults,
    PlatformInfo,
    GeographyInfo,
    SocialMediaInfo,
    SocialMediaProfile,
    CatalogInfo,
    WorkflowStep,
    BatchRequest,
    BatchResponse,
    BatchStatusResponse,
    OrdersPrediction,
    EnrichmentV2Results,
    DuplicateCheckResponse,
)


# Load environment variables
load_dotenv()

# Redis connection
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    global redis_client
    try:
        redis_client = redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
        print(f"[OK] Connected to Redis at {redis_url}")
    except Exception as e:
        print(f"[WARN] Redis not available (sync endpoint will still work): {e}")
        redis_client = None

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
cors_origins = os.getenv('API_CORS_ORIGINS', 'http://localhost:3000,http://localhost:3001').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

    return HealthResponse(
        status="healthy" if redis_status == "connected" else "degraded",
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
            "enrichment": "/api/v1/enrichment"
        }
    }


# ===== Instagram Scoring Functions =====

def calculate_ig_size_score(followers: int, posts_last_30d: int, engagement_rate: float) -> int:
    """
    IG Size Score (0-100): structural scale proxy.
    70% followers (log scale), 20% posting activity, 10% engagement presence.
    """
    import math

    # Component A: Followers Scale (70%)
    if followers > 0:
        foll_score = min(100.0, 100 * math.log(followers + 1) / math.log(1_000_001))
    else:
        foll_score = 0.0

    # Component B: Posting Activity (20%) — 5 posts/week = 100%
    posts_per_week = posts_last_30d / 4.3
    freq_score = 100 * min(1.0, posts_per_week / 5)

    # Component C: Engagement Presence (10%) — 5% engagement = 100%
    eng_score = 100 * min(1.0, engagement_rate / 5)

    return round(0.70 * foll_score + 0.20 * freq_score + 0.10 * eng_score)


def calculate_ig_health_score(engagement_rate: float, posts_last_30d: int, followers: int) -> int:
    """
    IG Health Score (0-100): community quality + momentum proxy.
    50% engagement quality (saturating exp), 30% consistency, 20% minimum scale bonus.
    """
    import math

    # Component A: Engagement Quality (50%) — saturating exponential
    eng_health = 100 * (1 - math.exp(-engagement_rate / 2))

    # Component B: Consistency (30%) — 3 posts/week = 100%
    posts_per_week = posts_last_30d / 4.3
    consistency = 100 * min(1.0, posts_per_week / 3)

    # Component C: Minimum Scale Bonus (20%) — saturates ~50K followers
    if followers > 0:
        scale_bonus = min(100.0, 100 * math.log(followers + 1) / math.log(50_001))
    else:
        scale_bonus = 0.0

    return round(0.50 * eng_health + 0.30 * consistency + 0.20 * scale_bonus)


def analyze_instagram_posts(posts_data: list) -> dict:
    """
    Extract post-level insights: product tagging frequency and posting consistency.

    Args:
        posts_data: List of recent posts from Apify (if available in response)

    Returns:
        dict with product_tags_count and avg_days_between_posts
    """
    if not posts_data or len(posts_data) == 0:
        return {
            'product_tags_count': 0,
            'avg_days_between_posts': None
        }

    # Count product tags (posts with 1+ tagged users)
    product_tags_count = sum(
        1 for post in posts_data
        if post.get('taggedUsers') and len(post.get('taggedUsers', [])) > 0
    )

    # Calculate posting consistency (average days between posts)
    timestamps = []
    for post in posts_data:
        ts = post.get('timestamp')
        if ts:
            try:
                post_date = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                timestamps.append(post_date)
            except:
                pass

    avg_days = None
    if len(timestamps) >= 2:
        timestamps.sort()
        gaps = [(timestamps[i+1] - timestamps[i]).days for i in range(len(timestamps)-1)]
        avg_days = sum(gaps) / len(gaps) if gaps else None

    return {
        'product_tags_count': product_tags_count,
        'avg_days_between_posts': round(avg_days, 1) if avg_days else None
    }


# ===== Enrichment API Endpoints (Placeholder) =====

@app.post("/api/v1/enrichment/analyze", response_model=JobResponse, tags=["Enrichment"])
async def create_enrichment_job(request: EnrichmentRequest):
    """
    Create a new enrichment job for analyzing an e-commerce URL.

    This endpoint creates an asynchronous job that will:
    1. Normalize and validate the URL
    2. Scrape the website
    3. Detect e-commerce platform
    4. Detect geographic operations
    5. Extract social media links
    6. Analyze product catalog (if enabled)
    7. Analyze quality metrics (if enabled)
    8. Generate summary and recommendations
    """
    # TODO: Implement job creation logic
    # For now, return a placeholder response
    import uuid

    job_id = str(uuid.uuid4())

    # Store job in Redis (placeholder)
    if redis_client:
        redis_client.hset(
            f"job:{job_id}",
            mapping={
                "status": JobStatus.queued.value,
                "url": request.url,
                "depth": request.depth.value,
                "include_social": str(request.include_social),
                "include_quality": str(request.include_quality),
                "created_at": datetime.utcnow().isoformat()
            }
        )

    return JobResponse(
        job_id=job_id,
        status=JobStatus.queued,
        created_at=datetime.utcnow()
    )


@app.get("/api/v1/enrichment/jobs/{job_id}", response_model=JobDetailResponse, tags=["Enrichment"])
async def get_job_status(job_id: str):
    """
    Get the status and results of an enrichment job.
    """
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis connection unavailable")

    # Get job from Redis
    job_data = redis_client.hgetall(f"job:{job_id}")

    if not job_data:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # TODO: Parse results from Redis and return full job detail
    # For now, return basic info
    return JobDetailResponse(
        job_id=job_id,
        status=JobStatus(job_data.get('status', 'queued')),
        progress=int(job_data.get('progress', 0)),
        current_step=job_data.get('current_step'),
        started_at=datetime.fromisoformat(job_data['created_at']) if 'created_at' in job_data else None,
        completed_at=None,
        results=None,
        errors=[]
    )


@app.get("/api/v1/enrichment/jobs", response_model=JobListResponse, tags=["Enrichment"])
async def list_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[JobStatus] = None
):
    """
    List all enrichment jobs with pagination.
    """
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis connection unavailable")

    # TODO: Implement job listing with pagination and filtering
    # For now, return empty list
    return JobListResponse(
        jobs=[],
        total=0,
        page=page,
        per_page=per_page
    )


@app.post("/api/v1/enrichment/jobs/{job_id}/export", response_model=ExportResponse, tags=["Enrichment"])
async def export_job_to_sheets(job_id: str):
    """
    Export job results to Google Sheets.
    """
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis connection unavailable")

    # Check if job exists
    job_exists = redis_client.exists(f"job:{job_id}")
    if not job_exists:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # TODO: Implement Google Sheets export
    # For now, return placeholder
    raise HTTPException(status_code=501, detail="Google Sheets export not yet implemented")


@app.delete("/api/v1/enrichment/jobs/{job_id}", tags=["Enrichment"])
async def delete_job(job_id: str):
    """
    Delete an enrichment job and its results.
    """
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis connection unavailable")

    # Delete job from Redis
    deleted = redis_client.delete(f"job:{job_id}")

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return {"message": f"Job {job_id} deleted successfully"}


# ===== In-Memory Batch State (lost on restart — Sheets is source of truth) =====
BATCH_STORE: dict[str, dict] = {}


# ===== Batch Utility Functions =====

def normalize_and_deduplicate(raw_urls: list[str]) -> list[str]:
    """
    Strip whitespace, skip empty, normalize, deduplicate by root domain.
    Invalid URLs are kept as-is (they'll fail gracefully in the pipeline).
    First occurrence wins.
    """
    seen_domains = set()
    result = []

    for raw in raw_urls:
        stripped = raw.strip()
        if not stripped:
            continue

        norm_result = normalize_url(stripped)
        if norm_result["success"]:
            url = norm_result["data"]["url"]
            domain = extract_domain(url)
        else:
            url = stripped
            domain = stripped.lower()

        if domain not in seen_domains:
            seen_domains.add(domain)
            result.append(url)

    return result


def run_single_url_workflow(raw_url: str) -> dict:
    """
    Run the full enrichment pipeline for a single URL.

    NEVER raises exceptions. Always returns a dict with at minimum:
    url, cms, cms_confidence, geography, geography_confidence,
    instagram_url, instagram_followers, instagram_engagement_rate,
    instagram_size_score, instagram_health_score, product_count,
    avg_price, price_range, workflow_log, error.
    """
    result = {
        "url": raw_url,
        "cms": None,
        "cms_confidence": None,
        "geography": None,
        "geography_confidence": None,
        "instagram_url": None,
        "instagram_followers": None,
        "instagram_engagement_rate": None,
        "instagram_size_score": None,
        "instagram_health_score": None,
        "product_count": None,
        "avg_price": None,
        "price_range": None,
        "workflow_log": "",
        "error": None,
    }
    steps = []

    try:
        # Step 0: Resolve brand URL
        t0 = time.time()
        resolve_result = resolve_brand_url(raw_url)
        ms = int((time.time() - t0) * 1000)
        if not resolve_result["success"]:
            steps.append(f"Resolve: FAIL ({ms}ms) {resolve_result.get('error', '')}")
            result["error"] = resolve_result.get("error")
            result["workflow_log"] = "; ".join(steps)
            return result
        resolved_url = resolve_result["data"]["url"]
        was_searched = resolve_result["data"].get("was_searched", False)
        steps.append(f"Resolve: ok ({ms}ms){' [searched]' if was_searched else ''}")

        # Step 1: Normalize URL
        t0 = time.time()
        norm_result = normalize_url(resolved_url)
        ms = int((time.time() - t0) * 1000)
        if not norm_result["success"]:
            steps.append(f"Normalize: FAIL ({ms}ms) {norm_result.get('error', '')}")
            result["error"] = norm_result.get("error")
            result["workflow_log"] = "; ".join(steps)
            return result
        url = norm_result["data"]["url"]
        result["url"] = url
        steps.append(f"Normalize: ok ({ms}ms) {url}")

        # Step 2: Scrape website
        t0 = time.time()
        scrape_result = scrape_website(url, timeout=60)
        ms = int((time.time() - t0) * 1000)
        if not scrape_result["success"]:
            steps.append(f"Scrape: FAIL ({ms}ms) {scrape_result.get('error', '')}")
            result["error"] = scrape_result.get("error")
            result["workflow_log"] = "; ".join(steps)
            return result
        html = scrape_result["data"]["html"]
        headers = scrape_result["data"].get("headers", {})
        steps.append(f"Scrape: ok ({ms}ms) {len(html) // 1024}KB")

        # Step 3: Detect platform
        t0 = time.time()
        try:
            platform_result = detect_platform_from_html(html, url, headers)
            ms = int((time.time() - t0) * 1000)
            if platform_result["success"] and platform_result["data"].get("platform"):
                pd = platform_result["data"]
                result["cms"] = pd["platform"]
                result["cms_confidence"] = pd.get("confidence", 0)
                steps.append(f"Platform: ok ({ms}ms) {pd['platform']}")
            else:
                steps.append(f"Platform: warn ({ms}ms) no platform detected")
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            steps.append(f"Platform: fail ({ms}ms) {str(e)}")

        # Step 4: Detect geography
        t0 = time.time()
        try:
            geo_result = detect_geography_from_html(html, url)
            ms = int((time.time() - t0) * 1000)
            if geo_result["success"] and geo_result["data"].get("primary_country"):
                gd = geo_result["data"]
                result["geography"] = gd["primary_country"]
                result["geography_confidence"] = gd.get("confidence", 0)
                steps.append(f"Geography: ok ({ms}ms) {gd['primary_country']}")
            else:
                steps.append(f"Geography: warn ({ms}ms) no geography detected")
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            steps.append(f"Geography: fail ({ms}ms) {str(e)}")

        # Step 5: Extract social links + Instagram metrics
        t0 = time.time()
        try:
            social_result = extract_social_links_from_html(html, url)
            ms = int((time.time() - t0) * 1000)
            if social_result["success"] and social_result["data"].get("instagram"):
                ig_url = social_result["data"]["instagram"]
                result["instagram_url"] = ig_url
                steps.append(f"Social: ok ({ms}ms) IG found")

                # Fetch Instagram metrics
                t0 = time.time()
                try:
                    username = extract_instagram_username(ig_url)
                    if username:
                        insta_result = get_instagram_metrics(username, include_posts=True, posts_limit=20)
                        ms = int((time.time() - t0) * 1000)
                        if insta_result["success"]:
                            insta_data = insta_result["data"]
                            result["instagram_followers"] = insta_data.get("followers")
                            result["instagram_engagement_rate"] = insta_data.get("engagement_rate")
                            result["instagram_size_score"] = calculate_ig_size_score(
                                followers=insta_data.get("followers", 0),
                                posts_last_30d=insta_data.get("posts_last_30d", 0),
                                engagement_rate=insta_data.get("engagement_rate", 0),
                            )
                            result["instagram_health_score"] = calculate_ig_health_score(
                                engagement_rate=insta_data.get("engagement_rate", 0),
                                posts_last_30d=insta_data.get("posts_last_30d", 0),
                                followers=insta_data.get("followers", 0),
                            )
                            followers_str = f"{insta_data.get('followers', 0):,}"
                            steps.append(f"Instagram: ok ({ms}ms) @{username} {followers_str} followers")
                        else:
                            steps.append(f"Instagram: warn ({ms}ms) {insta_result.get('error', '')}")
                    else:
                        ms = int((time.time() - t0) * 1000)
                        steps.append(f"Instagram: skip ({ms}ms) no username extracted")
                except Exception as e:
                    ms = int((time.time() - t0) * 1000)
                    steps.append(f"Instagram: fail ({ms}ms) {str(e)}")
            else:
                steps.append(f"Social: warn ({ms}ms) no Instagram found")
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            steps.append(f"Social: fail ({ms}ms) {str(e)}")

        # Step 6: Scrape product catalog
        t0 = time.time()
        try:
            catalog_result = scrape_product_catalog(url)
            ms = int((time.time() - t0) * 1000)
            if catalog_result["success"] and catalog_result["data"].get("product_count", 0) > 0:
                cd = catalog_result["data"]
                result["product_count"] = cd["product_count"]
                result["avg_price"] = cd.get("avg_price", 0)
                pr = cd.get("price_range", {})
                currency = cd.get("currency", "USD")
                result["price_range"] = f"{currency} {pr.get('min', 0):,.2f} - {currency} {pr.get('max', 0):,.2f}"
                steps.append(f"Catalog: ok ({ms}ms) {cd['product_count']} products")
            else:
                steps.append(f"Catalog: warn ({ms}ms) no products found")
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            steps.append(f"Catalog: fail ({ms}ms) {str(e)}")

    except Exception as e:
        steps.append(f"FATAL: {str(e)}")
        result["error"] = str(e)

    result["workflow_log"] = "; ".join(steps)
    return result


def run_batch(batch_id: str, urls: list[str], worksheet) -> None:
    """
    Background task: process URLs serially, flush to Google Sheets every 10 rows.
    Updates BATCH_STORE counters after each URL.
    """
    buffer = []

    try:
        for url in urls:
            BATCH_STORE[batch_id]["current_url"] = url

            result = run_single_url_workflow(url)
            row = enrichment_result_to_row(result)
            buffer.append(row)

            BATCH_STORE[batch_id]["processed"] += 1
            if result.get("error"):
                BATCH_STORE[batch_id]["failed"] += 1
            else:
                BATCH_STORE[batch_id]["succeeded"] += 1

            # Flush every 10 rows
            if len(buffer) >= 10:
                try:
                    sheets_append_rows(worksheet, buffer)
                except Exception as e:
                    print(f"[ERROR] Batch {batch_id}: Failed to flush to Sheets: {e}")
                buffer = []

        # Flush remaining rows
        if buffer:
            try:
                sheets_append_rows(worksheet, buffer)
            except Exception as e:
                print(f"[ERROR] Batch {batch_id}: Failed to flush final rows to Sheets: {e}")

        BATCH_STORE[batch_id]["status"] = "completed"

    except Exception as e:
        print(f"[ERROR] Batch {batch_id}: Fatal batch error: {e}")
        BATCH_STORE[batch_id]["status"] = "failed"

    BATCH_STORE[batch_id]["current_url"] = None


# ===== Synchronous Enrichment Endpoint =====

@app.post("/api/v1/enrichment/analyze-sync", response_model=EnrichmentResults, tags=["Enrichment"])
async def analyze_sync(request: SyncEnrichmentRequest):
    """
    Synchronously analyze an e-commerce URL and return enrichment results.

    This endpoint runs the full enrichment pipeline and waits for completion:
    1. Normalize and validate the URL
    2. Scrape the website
    3. Detect e-commerce platform
    4. Detect geographic operations
    5. Extract social media links
    6. Analyze product catalog
    """
    workflow_log: list[WorkflowStep] = []

    def _track(step: str, status: str, duration_ms: int, detail: str = None):
        workflow_log.append(WorkflowStep(step=step, status=status, duration_ms=duration_ms, detail=detail))

    try:
        # Step 0: Resolve input
        t0 = time.time()
        resolve_result = resolve_brand_url(request.url)
        elapsed = int((time.time() - t0) * 1000)
        if not resolve_result['success']:
            _track("Resolve URL", "fail", elapsed, resolve_result.get('error'))
            raise HTTPException(status_code=400, detail=resolve_result.get('error', 'Could not resolve input to a URL'))

        resolved_url = resolve_result['data']['url']
        was_searched = resolve_result['data'].get('was_searched', False)
        _track("Resolve URL", "ok", elapsed,
               f"Searched: '{request.url}' -> {resolved_url}" if was_searched else f"Direct URL: {resolved_url}")
        if was_searched:
            print(f"[INFO] Resolved brand search '{request.url}' -> {resolved_url}")

        # Step 1: Normalize URL
        t0 = time.time()
        norm_result = normalize_url(resolved_url)
        elapsed = int((time.time() - t0) * 1000)
        if not norm_result['success']:
            _track("Normalize URL", "fail", elapsed, norm_result.get('error'))
            raise HTTPException(status_code=400, detail=f"Invalid URL: {norm_result.get('error')}")
        url = norm_result['data']['url']
        _track("Normalize URL", "ok", elapsed, url)

        # Step 2: Scrape website
        t0 = time.time()
        scrape_result = scrape_website(url, timeout=60)
        elapsed = int((time.time() - t0) * 1000)
        if not scrape_result['success']:
            _track("Scrape website", "fail", elapsed, scrape_result.get('error'))
            raise HTTPException(status_code=502, detail=f"Failed to scrape website: {scrape_result.get('error')}")
        html_content = scrape_result['data']['html']
        headers = scrape_result['data'].get('headers', {})
        html_kb = len(html_content) // 1024
        _track("Scrape website", "ok", elapsed, f"{html_kb} KB HTML")

        # Step 3: Detect platform
        t0 = time.time()
        platform_result = detect_platform_from_html(html_content, url, headers)
        elapsed = int((time.time() - t0) * 1000)
        platform_info = None
        if platform_result['success'] and platform_result['data'].get('platform'):
            pd = platform_result['data']
            platform_info = PlatformInfo(
                name=pd['platform'],
                confidence=pd.get('confidence', 0),
                version=pd.get('version'),
                evidence=pd.get('evidence', [])[:10]
            )
            _track("Detect platform", "ok", elapsed, f"{pd['platform']} ({int(pd.get('confidence', 0)*100)}%)")
        else:
            _track("Detect platform", "warn", elapsed, "No platform detected")

        # Step 4: Detect geography
        t0 = time.time()
        geo_result = detect_geography_from_html(html_content, url)
        elapsed = int((time.time() - t0) * 1000)
        geography_info = None
        if geo_result['success'] and geo_result['data'].get('countries'):
            gd = geo_result['data']
            geography_info = GeographyInfo(
                countries=gd['countries'],
                primary_country=gd.get('primary_country'),
                confidence=gd.get('confidence', 0),
                evidence=gd.get('evidence', {})
            )
            _track("Detect geography", "ok", elapsed, ', '.join(gd['countries']))
        else:
            _track("Detect geography", "warn", elapsed, "No geography detected")

        # Step 5: Extract social links
        t0 = time.time()
        social_result = extract_social_links_from_html(html_content, url)
        elapsed = int((time.time() - t0) * 1000)
        social_info = None
        if social_result['success'] and social_result['data']:
            sd = social_result['data']
            instagram_profile = None
            if sd.get('instagram'):
                instagram_profile = SocialMediaProfile(url=sd['instagram'])

            social_info = SocialMediaInfo(
                instagram=instagram_profile,
                facebook=SocialMediaProfile(url=sd['facebook']) if sd.get('facebook') else None,
                tiktok=SocialMediaProfile(url=sd['tiktok']) if sd.get('tiktok') else None,
                youtube=SocialMediaProfile(url=sd['youtube']) if sd.get('youtube') else None,
                linkedin=SocialMediaProfile(url=sd['linkedin']) if sd.get('linkedin') else None
            )
            found = [k for k in ['instagram', 'facebook', 'tiktok', 'youtube', 'linkedin'] if sd.get(k)]
            _track("Extract social links", "ok", elapsed, ', '.join(found))

            # Step 5b: Fetch Instagram metrics
            if instagram_profile:
                t0 = time.time()
                try:
                    instagram_username = extract_instagram_username(instagram_profile.url)
                    if instagram_username:
                        insta_result = get_instagram_metrics(instagram_username, include_posts=True, posts_limit=20)
                        elapsed = int((time.time() - t0) * 1000)

                        if insta_result['success']:
                            insta_data = insta_result['data']
                            size_score = calculate_ig_size_score(
                                followers=insta_data.get('followers', 0),
                                posts_last_30d=insta_data.get('posts_last_30d', 0),
                                engagement_rate=insta_data.get('engagement_rate', 0)
                            )
                            health_score = calculate_ig_health_score(
                                engagement_rate=insta_data.get('engagement_rate', 0),
                                posts_last_30d=insta_data.get('posts_last_30d', 0),
                                followers=insta_data.get('followers', 0)
                            )
                            post_insights = {'product_tags_count': 0, 'avg_days_between_posts': None}
                            if 'latestPosts' in insta_data:
                                post_insights = analyze_instagram_posts(insta_data['latestPosts'])

                            social_info.instagram = SocialMediaProfile(
                                url=insta_data['url'],
                                followers=insta_data.get('followers'),
                                posts_last_30d=insta_data.get('posts_last_30d'),
                                engagement_rate=insta_data.get('engagement_rate'),
                                ig_size_score=size_score,
                                ig_health_score=health_score,
                                full_name=insta_data.get('full_name'),
                                biography=insta_data.get('biography'),
                                is_verified=insta_data.get('is_verified'),
                                is_private=insta_data.get('is_private'),
                                product_tags_count=post_insights.get('product_tags_count'),
                                avg_days_between_posts=post_insights.get('avg_days_between_posts')
                            )
                            followers_str = f"{insta_data.get('followers', 0):,}"
                            _track("Instagram metrics (Apify)", "ok", elapsed,
                                   f"@{instagram_username}: {followers_str} followers, size={size_score} health={health_score}")
                        else:
                            _track("Instagram metrics (Apify)", "warn", elapsed, insta_result.get('error'))
                    else:
                        elapsed = int((time.time() - t0) * 1000)
                        _track("Instagram metrics (Apify)", "skip", elapsed, "Could not extract username")
                except Exception as e:
                    elapsed = int((time.time() - t0) * 1000)
                    _track("Instagram metrics (Apify)", "fail", elapsed, str(e))
                    print(f"[WARN] Instagram metrics fetch failed: {str(e)}")
            else:
                _track("Instagram metrics (Apify)", "skip", 0, "No Instagram profile found")
        else:
            _track("Extract social links", "warn", elapsed, "No social links found")
            _track("Instagram metrics (Apify)", "skip", 0, "No social links found")

        # Step 6: Scrape product catalog
        t0 = time.time()
        catalog_result = scrape_product_catalog(url)
        elapsed = int((time.time() - t0) * 1000)
        catalog_info = None
        if catalog_result['success'] and catalog_result['data'].get('product_count', 0) > 0:
            cd = catalog_result['data']
            catalog_info = CatalogInfo(
                product_count=cd['product_count'],
                avg_price=cd.get('avg_price', 0),
                price_range=cd.get('price_range', {'min': 0, 'max': 0}),
                currency=cd.get('currency', 'USD')
            )
            _track("Scrape catalog", "ok", elapsed, f"{cd['product_count']} products, {cd.get('currency', 'USD')}")
        else:
            _track("Scrape catalog", "warn", elapsed, "No products found")

        total_ms = sum(s.duration_ms for s in workflow_log)
        _track("Total", "ok", total_ms, f"{len(workflow_log) - 1} steps")

        return EnrichmentResults(
            url=url,
            platform=platform_info,
            geography=geography_info,
            social_media=social_info,
            catalog=catalog_info,
            workflow_log=workflow_log
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# ===== V2: Enrichment Flow V2 =====

# Sheet V2 configuration
SHEET_V2_NAME = "Enrichment Flow V2"
SHEET_V2_HEADERS = [
    "company_name", "domain", "platform", "category", "instagram_url",
    "ig_followers", "ig_size_score", "ig_health_score", "company_linkedin",
    "contact_name", "contact_email", "number_employes", "predicted_p10",
    "predicted_p50", "predicted_p90", "prediction_confidence",
    "workflow_execution_log",
]

# Store Sheet V2 URL (set via env or first-time creation)
_sheet_v2_url = os.getenv("SHEET_V2_URL", "")


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
            "number_employes": enrichment_result.number_employes,
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


def _write_to_sheet_v2(enrichment_result, prediction: dict) -> None:
    """Write a single result row to the Enrichment Flow V2 Google Sheet."""
    global _sheet_v2_url
    try:
        client = get_gspread_client()

        if _sheet_v2_url:
            spreadsheet = client.open_by_url(_sheet_v2_url)
        else:
            spreadsheet = client.create(SHEET_V2_NAME)
            spreadsheet.share("", perm_type="anyone", role="reader")

        try:
            worksheet = spreadsheet.worksheet("results")
        except Exception:
            worksheet = spreadsheet.add_worksheet(
                title="results", rows=1000, cols=len(SHEET_V2_HEADERS)
            )

        # Write headers if first row is empty
        first_row = worksheet.row_values(1)
        if not first_row:
            worksheet.append_row(SHEET_V2_HEADERS, value_input_option="USER_ENTERED")

        if not _sheet_v2_url:
            _sheet_v2_url = spreadsheet.url
            print(f"[INFO] Sheet V2 created: {_sheet_v2_url}")

        pred = prediction or {}
        row = [
            enrichment_result.company_name or "",
            enrichment_result.domain or "",
            enrichment_result.platform or "",
            enrichment_result.category or "",
            enrichment_result.instagram_url or "",
            enrichment_result.ig_followers or "",
            enrichment_result.ig_size_score or "",
            enrichment_result.ig_health_score or "",
            enrichment_result.company_linkedin or "",
            enrichment_result.contact_name or "",
            enrichment_result.contact_email or "",
            enrichment_result.number_employes or "",
            pred.get("predicted_orders_p10", ""),
            pred.get("predicted_orders_p50", ""),
            pred.get("predicted_orders_p90", ""),
            pred.get("prediction_confidence", ""),
            enrichment_result.workflow_execution_log or "",
        ]
        sheets_append_rows(worksheet, [row])
    except Exception as e:
        print(f"[WARN] Sheet V2 write failed: {e}")


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

    return {
        "company_name": enrichment_result.company_name,
        "domain": enrichment_result.domain,
        "platform": enrichment_result.platform,
        "category": enrichment_result.category,
        "instagram_url": enrichment_result.instagram_url,
        "ig_followers": enrichment_result.ig_followers,
        "ig_size_score": enrichment_result.ig_size_score,
        "ig_health_score": enrichment_result.ig_health_score,
        "company_linkedin": enrichment_result.company_linkedin,
        "contact_name": enrichment_result.contact_name,
        "contact_email": enrichment_result.contact_email,
        "number_employes": enrichment_result.number_employes,
        "prediction": pred_model,
        "workflow_log": json.loads(enrichment_result.workflow_execution_log or "[]"),
    }


@app.post("/api/v2/enrichment/analyze-stream", tags=["Enrichment V2"])
async def analyze_stream_v2(request: SyncEnrichmentRequest):
    """
    V2 SSE streaming enrichment endpoint.

    Runs the full enrichment pipeline (including Apollo + category + traffic +
    demand) with real-time step-by-step progress via Server-Sent Events.
    After enrichment, runs the orders estimator and writes to Sheet V2.
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
                msg = await loop.run_in_executor(None, lambda: step_queue.get(timeout=120))
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

        # Write to Google Sheet
        yield f"data: {json.dumps({'type': 'step', 'step': 'Saving to sheet', 'status': 'running', 'duration_ms': 0, 'detail': ''})}\n\n"
        t0 = time.time()
        await loop.run_in_executor(None, _write_to_sheet_v2, enrichment_result, prediction)
        ms = int((time.time() - t0) * 1000)
        yield f"data: {json.dumps({'type': 'step', 'step': 'Saving to sheet', 'status': 'ok', 'duration_ms': ms, 'detail': ''})}\n\n"

        # Send final results
        final = _build_v2_response(enrichment_result, prediction)
        yield f"data: {json.dumps({'type': 'result', 'data': final})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/v2/enrichment/check-duplicate", response_model=DuplicateCheckResponse,
         tags=["Enrichment V2"])
async def check_duplicate(domain: str = Query(..., description="Domain to check")):
    """Check if a domain already exists in the Enrichment Flow V2 Google Sheet."""
    global _sheet_v2_url
    if not _sheet_v2_url:
        return DuplicateCheckResponse(exists=False)

    try:
        client = get_gspread_client()
        sheet_result = create_or_open_spreadsheet(
            client,
            spreadsheet_url=_sheet_v2_url,
            worksheet_name="results",
        )
        if not sheet_result["success"]:
            return DuplicateCheckResponse(exists=False)

        worksheet = sheet_result["data"]["worksheet"]
        existing = read_existing_domains(worksheet)
        domain_clean = domain.lower().strip()
        exists = domain_clean in existing
        return DuplicateCheckResponse(exists=exists, domain=domain_clean)
    except Exception:
        return DuplicateCheckResponse(exists=False)


# ===== Batch Processing Endpoints =====

@app.post("/api/batch", response_model=BatchResponse, tags=["Batch"])
async def create_batch(request: BatchRequest, background_tasks: BackgroundTasks):
    """
    Submit a batch of URLs for enrichment. Processing runs in the background.

    - Normalizes and deduplicates URLs by root domain
    - Creates or opens a Google Sheet for results
    - Starts serial background processing (one URL at a time)
    - Writes results to Sheets in chunks of 10 rows
    - Returns batch_id and sheet_url immediately
    """
    # Normalize and deduplicate
    original_count = len([u for u in request.urls if u.strip()])
    urls = normalize_and_deduplicate(request.urls)

    if not urls:
        raise HTTPException(status_code=400, detail="No valid URLs provided after filtering")

    deduplicated_count = original_count - len(urls)

    # Set up Google Sheet
    try:
        client = get_gspread_client()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Google Sheets auth failed: {e}")

    batch_id = str(uuid.uuid4())
    batch_id_short = batch_id[:8]

    sheet_result = create_or_open_spreadsheet(
        client,
        spreadsheet_url=request.spreadsheet_url,
        batch_id_short=batch_id_short,
    )
    if not sheet_result["success"]:
        raise HTTPException(status_code=502, detail=sheet_result["error"])

    worksheet = sheet_result["data"]["worksheet"]
    sheet_url = sheet_result["data"]["sheet_url"]

    # Initialize in-memory state
    BATCH_STORE[batch_id] = {
        "batch_id": batch_id,
        "status": "processing",
        "total": len(urls),
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "sheet_url": sheet_url,
        "current_url": None,
        "_created_at": time.time(),
    }

    # Clean up old batches (older than 24h) to prevent memory leaks
    _cleanup_old_batches()

    # Start background processing
    background_tasks.add_task(run_batch, batch_id, urls, worksheet)

    return BatchResponse(
        batch_id=batch_id,
        sheet_url=sheet_url,
        status="processing",
        total=len(urls),
        deduplicated=deduplicated_count,
        message=f"Batch started. Processing {len(urls)} URLs. Results will appear in the Google Sheet.",
    )


@app.get("/api/batch/{batch_id}/status", response_model=BatchStatusResponse, tags=["Batch"])
async def get_batch_status(batch_id: str):
    """
    Get the current status of a batch processing job.
    Returns in-memory counters (lost on backend restart).
    """
    if batch_id not in BATCH_STORE:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found (may have expired or backend restarted)")

    state = BATCH_STORE[batch_id]
    return BatchStatusResponse(**state)


def _cleanup_old_batches():
    """Remove batch entries older than 24 hours to prevent memory leaks."""
    now = time.time()
    to_delete = []
    for bid, state in BATCH_STORE.items():
        created = state.get("_created_at", now)
        if now - created > 86400:  # 24 hours
            to_delete.append(bid)
    for bid in to_delete:
        del BATCH_STORE[bid]


# Run with: uvicorn api.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
