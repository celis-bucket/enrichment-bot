"""
Instagram Scoring Functions

Purpose: Compute IG Size Score and IG Health Score from Instagram metrics.
Inputs: followers (int), posts_last_30d (int), engagement_rate (float)
Outputs: Score 0-100 (int)
Dependencies: None (stdlib math only)

Extracted from backend/api/main.py lines 166-209.
"""

import math


def calculate_ig_size_score(followers: int, posts_last_30d: int, engagement_rate: float) -> int:
    """
    IG Size Score (0-100): structural scale proxy.
    70% followers (log scale), 20% posting activity, 10% engagement presence.
    """
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
