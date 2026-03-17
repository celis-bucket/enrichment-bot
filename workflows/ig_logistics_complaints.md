# Instagram Logistics Complaints Analysis

## Objective
Analyze a company's Instagram comments to detect logistics complaints
(delivery delays, damaged packages, wrong items, return difficulties)
and produce a weighted risk score (0-100).

## Required Inputs
- **company_url**: Company website URL (e.g., `https://www.armatura.com.co`)

## Entry Point (CLI)
```bash
python tools/logistics/analyze_ig_complaints.py "https://www.example.com"
```

## Tools Used (in order)

| Step | Tool | Purpose |
|------|------|---------|
| 1 | `tools/social/extract_social_links.py` | Scrape website HTML + extract IG URL (Serper fallback) |
| 2 | `tools/social/apify_instagram.py` → `get_instagram_posts()` | Get last 12 posts with shortcodes via Apify |
| 3 | `tools/social/apify_instagram_comments.py` → `get_comments_for_posts()` | Scrape up to 50 comments per post via Apify |
| 4 | *(in-memory)* | Filter out brand's own replies |
| 5 | `tools/logistics/analyze_ig_complaints.py` → Claude API | Classify complaints by category + severity |
| 6 | `tools/logistics/analyze_ig_complaints.py` → deterministic scoring | Weighted risk score (recency × severity) |

## Output
JSON to console with:
- `risk_score` (0-100)
- `risk_level` (none / low / medium / high / critical)
- `summary` (Spanish, 2-3 sentences from Claude)
- `top_flagged_comments` (up to 10, sorted by weighted score)
- `category_breakdown` (counts per complaint type)
- `recency_trend` (worsening / stable / improving)

## Scope & Constraints
- **Single company only** (no batch support)
- **Spanish comments only**
- **No caching** (always fresh scrape)
- **Comments on company's own posts only** (not mentions/tags)
- **Last 12 posts**, up to 50 comments each (max ~600 comments)
- **Not part of enrichment pipeline** (standalone tool)

## Complaint Categories

| Category | Examples |
|----------|----------|
| DELAY | "lleva semanas", "no ha llegado", "tarda mucho" |
| NON_DELIVERY | "nunca llegó", "pedido perdido" |
| DAMAGED | "llegó roto", "caja dañada" |
| WRONG_ITEM | "me llegó otro", "producto equivocado" |
| RETURN_REFUND | "no me devuelven", "reembolso" |
| POOR_SERVICE | "no responden sobre mi pedido", "pésimo servicio de envío" |

## Risk Score Computation
- **Severity weights**: high=3.0, medium=2.0, low=1.0
- **Recency weights**: exponential decay `exp(-0.1 × (post_rank - 1))` where rank 1=newest
- **Score**: sigmoid-scaled ratio of weighted complaints to total comments
- **Risk levels**: 0=none, 1-25=low, 26-50=medium, 51-75=high, 76-100=critical

## Edge Cases (returns `status: "not_available"`)
- No Instagram found (HTML + Serper)
- Private Instagram account
- No posts on account
- Zero comments across all posts
- Website unreachable
- Apify timeout

## Cost Estimate Per Analysis
- **Apify Instagram profile**: ~$0.01 (1 run, details mode)
- **Apify comment scraper**: ~$0.10-0.50 (apidojo actor, $0.50/1K comments)
- **Claude API**: ~$0.05-0.25 (single call, depends on comment volume)
- **Total**: ~$0.15-0.75

## Environment Variables Required
- `APIFY_API_TOKEN` — for Instagram scraping (profile + comments)
- `ANTHROPIC_API_KEY` — for Claude classification
- `SERPER_API_KEY` — only if Instagram not found in HTML (fallback)

## Apify Actor Choice
Uses `apidojo/instagram-comments-scraper` instead of the official `apify/instagram-comment-scraper`.
Reason: The official actor was extremely slow (20+ min for 1 post, never completed in testing).
The apidojo actor returns 200 comments across 5 posts in ~10 seconds and costs 4.6x less.

## Known Limitations
- Instagram public API (via Apify) returns max ~50 comments per post
- Very new accounts with few comments produce low-confidence scores
- Non-Spanish comments are ignored by Claude (not flagged)
- The comment scraper may not capture all threaded replies
- Cost is dominated by Claude for high-comment accounts (~$0.20 for 374 comments)
