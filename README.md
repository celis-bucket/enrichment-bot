# E-Commerce Enrichment Web App

A comprehensive web application for analyzing e-commerce websites to assess potential clients for Melonn's fulfillment services in Mexico and Colombia. Built on the **WAT architecture** (Workflows, Agents, Tools) for reliable, deterministic execution.

## What This Does

Input any e-commerce URL and get a comprehensive analysis:

- **Platform Detection**: Shopify, VTEX, WooCommerce, Magento, or custom
- **Geographic Operations**: Does it ship to Mexico or Colombia?
- **Social Media Presence**: Instagram, Facebook, TikTok, YouTube, LinkedIn profiles
- **Product Catalog**: Size, pricing, categories
- **Quality Metrics**: Images, reviews, shipping policies, return policies
- **Social Engagement**: Follower counts, recent posts, engagement rates
- **Volume Assessment**: AI-powered scoring of business volume and quality

## Architecture Overview

The system uses a three-layer architecture:

```
┌──────────────────────────────────────┐
│  Next.js Frontend (TypeScript)       │  ← User Interface
│  - URL Input                         │
│  - Real-time Progress Tracking       │
│  - Results Dashboard                 │
└──────────────┬───────────────────────┘
               │ REST API
┌──────────────▼───────────────────────┐
│  FastAPI Backend + Redis             │  ← Orchestration
│  - Job Queue Management              │
│  - Rate Limiting & Caching           │
└──────────────┬───────────────────────┘
               │ Executes
┌──────────────▼───────────────────────┐
│  WAT Framework (Workflows + Tools)   │  ← Deterministic Execution
│  - Web Scraping                      │
│  - Platform Detection                │
│  - Apify Integration (Instagram)     │
│  - AI Analysis (Claude/GPT)          │
│  - Google Sheets Export              │
└──────────────────────────────────────┘
```

### WAT Framework

The WAT framework ensures reliability by separating concerns:

- **Workflows** (instructions): Define what needs to be done
- **Agents** (decision-making): Orchestrate and coordinate tasks
- **Tools** (execution): Handle the actual work deterministically

This separation prevents accuracy degradation that occurs when AI handles every step directly.

## Directory Structure

```
.
├── backend/            # FastAPI backend
│   ├── api/            # API routes and models
│   ├── workers/        # Background job workers
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/           # Next.js frontend (to be initialized)
│   ├── app/            # Next.js pages
│   ├── components/     # React components
│   ├── lib/            # Utilities and API client
│   ├── package.json
│   └── Dockerfile
├── tools/              # Python scripts for deterministic execution
│   ├── core/           # Core utilities (scraper, normalizer)
│   ├── detection/      # Platform and geography detection
│   ├── social/         # Social media extraction
│   ├── ecommerce/      # Product catalog analysis
│   ├── ai/             # AI-powered analysis
│   └── export/         # Google Sheets export
├── workflows/          # Markdown SOPs defining objectives and procedures
├── .tmp/               # Temporary files (scraped data, intermediates)
│   ├── html/           # Cached HTML
│   ├── images/         # Temporary images
│   └── jobs/           # Job data
├── .env                # API keys and environment variables (not in git)
├── docker-compose.yml  # Docker orchestration
├── requirements.txt    # Root Python dependencies
└── README.md           # This file
```

## Quick Start with Docker

The fastest way to get started is with Docker Compose:

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd "Enrichment Agent"
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys:
   # - ANTHROPIC_API_KEY (for Claude AI analysis)
   # - APIFY_API_TOKEN (for Instagram scraping)
   # - OPENAI_API_KEY (optional, for OpenAI analysis)
   # - GOOGLE_API_KEY (for Google Sheets export)
   ```

3. **Start all services**
   ```bash
   docker-compose up --build
   ```

   This will start:
   - **Frontend**: http://localhost:3000
   - **Backend API**: http://localhost:8000
   - **API Docs**: http://localhost:8000/docs
   - **Redis**: localhost:6379

4. **Access the web app**
   - Open http://localhost:3000 in your browser
   - Enter an e-commerce URL to analyze

## Manual Setup (Without Docker)

### Backend Setup

1. **Install Python dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Start Redis**
   ```bash
   # Using Docker
   docker run -d -p 6379:6379 redis:7-alpine

   # Or install Redis locally
   # macOS: brew install redis && redis-server
   # Ubuntu: sudo apt install redis && redis-server
   ```

3. **Run FastAPI server**
   ```bash
   cd backend
   uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Run background worker** (in another terminal)
   ```bash
   cd backend
   python workers/enrichment_worker.py
   ```

### Frontend Setup

1. **Initialize Next.js app** (first time only)
   ```bash
   cd frontend
   npx create-next-app@latest . --typescript --tailwind --app --no-src-dir
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Run development server**
   ```bash
   npm run dev
   ```

### Access Points
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **Alternative API Docs**: http://localhost:8000/redoc (ReDoc)

## Implementation Status

### ✅ Completed (Week 1 - Core Infrastructure)

- [x] Project directory structure
- [x] Docker Compose configuration (FastAPI + Redis + Next.js)
- [x] Backend requirements.txt with all dependencies
- [x] Environment variable configuration
- [x] FastAPI backend skeleton with health endpoint
- [x] Pydantic models for API requests/responses
- [x] Core tools:
  - [x] `tools/core/url_normalizer.py` - URL cleaning and validation
  - [x] `tools/core/web_scraper.py` - HTTP scraper with retry logic
- [x] API endpoints (placeholder implementations):
  - [x] POST `/api/v1/enrichment/analyze` - Create enrichment job
  - [x] GET `/api/v1/enrichment/jobs/{job_id}` - Get job status
  - [x] GET `/api/v1/enrichment/jobs` - List jobs
  - [x] POST `/api/v1/enrichment/jobs/{job_id}/export` - Export to Google Sheets
  - [x] DELETE `/api/v1/enrichment/jobs/{job_id}` - Delete job
  - [x] GET `/health` - Health check

### 🚧 In Progress (Week 2 - MVP Features)

- [ ] Next.js frontend initialization
- [ ] Platform detection tool (`tools/detection/detect_ecommerce_platform.py`)
- [ ] Geography detection tool (`tools/detection/detect_geography.py`)
- [ ] Social media extraction tool (`tools/social/extract_social_links.py`)
- [ ] Product catalog analyzer (`tools/ecommerce/scrape_product_catalog.py`)
- [ ] Workflows for Phase 1:
  - [ ] `workflows/normalize_url.md`
  - [ ] `workflows/detect_platform.md`
  - [ ] `workflows/detect_geography.md`
  - [ ] `workflows/extract_social_media.md`
  - [ ] `workflows/analyze_product_catalog.md`
  - [ ] `workflows/enrich_ecommerce_url.md` (main orchestration)

### 📋 Planned

**Phase 2 (Weeks 3-4)**: Quality Metrics & Async Processing
- Product image analysis
- Review system detection
- Shipping/return policy analysis
- Redis job queue implementation
- Background worker
- Real-time progress tracking

**Phase 3 (Week 5)**: Social Media Metrics
- Apify Instagram integration
- Facebook/TikTok/YouTube scrapers
- Engagement rate calculations

**Phase 4 (Week 6)**: AI Analysis & Export
- AI-powered quality scoring
- Volume/quality recommendations
- Google Sheets export
- Batch processing
- Result caching

## Usage

### Using the Web App (Coming Soon)

1. Navigate to http://localhost:3000
2. Enter an e-commerce URL (e.g., `https://example-store.com`)
3. Select analysis depth (quick/standard/comprehensive)
4. Click "Analyze"
5. View real-time progress as the system:
   - Detects the e-commerce platform
   - Identifies geographic operations
   - Extracts social media links
   - Analyzes product catalog
   - Scores quality metrics
6. Review the comprehensive report
7. Export to Google Sheets (optional)

### Using the API Directly

#### Create an Enrichment Job

```bash
curl -X POST "http://localhost:8000/api/v1/enrichment/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example-store.com",
    "depth": "standard",
    "include_social": true,
    "include_quality": true
  }'
```

Response:
```json
{
  "job_id": "abc-123-def",
  "status": "queued",
  "created_at": "2026-02-02T12:00:00Z"
}
```

#### Check Job Status

```bash
curl "http://localhost:8000/api/v1/enrichment/jobs/abc-123-def"
```

#### Health Check

```bash
curl "http://localhost:8000/health"
```

### WAT Framework Usage

### Creating a Workflow

1. Create a new markdown file in `workflows/`
2. Define:
   - **Objective**: What needs to be accomplished
   - **Required Inputs**: What data/parameters are needed
   - **Tools**: Which scripts from `tools/` to use
   - **Expected Outputs**: What the workflow produces
   - **Edge Cases**: How to handle failures and special situations

Example workflow structure:
```markdown
# Workflow: [Name]

## Objective
[Clear description of what this workflow accomplishes]

## Required Inputs
- Input 1: [description]
- Input 2: [description]

## Tools Required
- `tools/script_name.py`: [what it does]

## Steps
1. [Step 1]
2. [Step 2]
...

## Expected Outputs
[What gets produced]

## Edge Cases
- [Case 1]: [How to handle]
- [Case 2]: [How to handle]
```

### Creating a Tool

1. Create a Python script in `tools/`
2. Make it focused on a single, deterministic task
3. Use environment variables from `.env` for credentials
4. Handle errors gracefully with clear messages

Example tool structure:
```python
#!/usr/bin/env python3
import os
from dotenv import load_dotenv

load_dotenv()

def main():
    # Tool implementation
    pass

if __name__ == "__main__":
    main()
```

## Self-Improvement Loop

When errors occur:
1. Identify what broke
2. Fix the tool
3. Verify the fix works
4. Update the workflow with lessons learned
5. Continue with a more robust system

## Best Practices

- **Workflows**: Keep them updated as you learn better approaches
- **Tools**: Make them single-purpose and deterministic
- **Credentials**: Always store in `.env`, never hardcode
- **Outputs**: Deliver to cloud services (Google Sheets, Slides, etc.)
- **Intermediates**: Store in `.tmp/` - these are disposable

## Why This Approach Works

When AI attempts to handle every step directly:
- 5 steps at 90% accuracy each = 59% overall success rate
- Error compounds with each additional step

With WAT framework:
- Deterministic tools handle execution (100% consistency)
- AI focuses on orchestration and decision-making (where it excels)
- Result: Reliable, repeatable outcomes

## Contributing

When adding new workflows or tools:
1. Follow existing naming conventions
2. Document thoroughly
3. Test with edge cases
4. Update this README if needed

## License

[Your license here]
