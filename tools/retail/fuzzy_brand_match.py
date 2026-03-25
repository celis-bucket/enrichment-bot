"""
Fuzzy Brand Name Matching Tool

Purpose: Match a brand name against retail_store_brands using cascading strategies
Inputs: brand_name, domain, ig_username, apollo_name, list of DB brand rows
Outputs: List of matched brands with match_type and confidence
Dependencies: rapidfuzz (pip install rapidfuzz), tools/retail/store_registry

Cascade stages:
  1. Exact match on normalized name
  2. Exact match on candidate variants (domain, IG, Apollo, stripped suffixes)
  3. Token containment (subset match, only for 2+ word names)
  4. Fuzzy via rapidfuzz token_set_ratio (only for names with len >= 5)
"""

import re
import os
import sys
from typing import List, Dict, Optional, Set

_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from retail.store_registry import normalize_name


# Legal and geographic suffixes to strip
LEGAL_SUFFIXES = {
    "sa", "sas", "srl", "ltda", "cia", "inc", "llc", "corp", "company",
    "colombia", "mexico", "co", "mx", "latam", "chile", "peru", "cl", "pe",
    "oficial", "official", "store", "tienda", "shop", "brand",
}


def generate_candidate_names(
    brand_name: str,
    domain: Optional[str] = None,
    ig_username: Optional[str] = None,
    apollo_name: Optional[str] = None,
) -> List[str]:
    """
    Generate all plausible normalized name variants from available inputs.

    Returns deduplicated list ordered by expected quality (best first).
    """
    candidates: List[str] = []

    # Primary: LLM-extracted brand name
    if brand_name:
        norm = normalize_name(brand_name)
        if norm:
            candidates.append(norm)
        # Also try stripping legal/geo suffixes
        stripped = _strip_suffixes(norm)
        if stripped and stripped != norm:
            candidates.append(stripped)

    # From domain: extract the second-level domain
    if domain:
        sld = domain.split(".")[0]
        if sld and sld != "www":
            norm_sld = normalize_name(sld)
            if norm_sld:
                candidates.append(norm_sld)

    # Instagram username (often close to brand name)
    if ig_username:
        clean_ig = ig_username.lower().strip()
        # Remove common prefixes/suffixes: _co, _col, _mx, .co, oficial, etc.
        clean_ig = re.sub(
            r'[._](co|col|mx|mex|oficial|brand|store|tienda|shop)$',
            '', clean_ig,
        )
        clean_ig = re.sub(
            r'^(tienda|brand|store|shop)[._]',
            '', clean_ig,
        )
        norm_ig = normalize_name(clean_ig)
        if norm_ig:
            candidates.append(norm_ig)

    # Apollo org name
    if apollo_name:
        norm_ap = normalize_name(apollo_name)
        if norm_ap:
            candidates.append(norm_ap)
        stripped_ap = _strip_suffixes(norm_ap)
        if stripped_ap and stripped_ap != norm_ap:
            candidates.append(stripped_ap)

    # Deduplicate preserving order
    seen: Set[str] = set()
    unique: List[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def _strip_suffixes(normalized: str) -> str:
    """Remove legal and geographic suffixes from a normalized name."""
    if not normalized:
        return normalized
    tokens = normalized.split()
    while len(tokens) > 1 and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def fuzzy_match_brand(
    candidates: List[str],
    db_brands: List[Dict],
    min_fuzzy_len: int = 5,
    fuzzy_threshold: int = 85,
) -> List[Dict]:
    """
    Cascade match candidates against DB brands.

    Args:
        candidates: Normalized name variants to search for (best first)
        db_brands: Rows from retail_store_brands with at least
                   brand_name_normalized, brand_name, and store info
        min_fuzzy_len: Minimum normalized name length for fuzzy matching
        fuzzy_threshold: rapidfuzz token_set_ratio threshold (0-100)

    Returns:
        List of match dicts with store_name, store_country, brand_name,
        match_type, match_score
    """
    if not candidates or not db_brands:
        return []

    # Build exact lookup index: normalized -> list of rows
    exact_index: Dict[str, List[Dict]] = {}
    for row in db_brands:
        bn = row.get("brand_name_normalized", "")
        if bn:
            exact_index.setdefault(bn, []).append(row)

    # === STAGE 1+2: Exact match for each candidate ===
    for candidate in candidates:
        if candidate in exact_index:
            return _format_matches(exact_index[candidate], "exact", 100)

    # === STAGE 3a: Token containment (only for multi-word names) ===
    for candidate in candidates:
        c_tokens = set(candidate.split())
        if len(c_tokens) < 2:
            continue
        for db_norm, rows in exact_index.items():
            db_tokens = set(db_norm.split())
            if len(db_tokens) < 2:
                continue
            if c_tokens.issubset(db_tokens) or db_tokens.issubset(c_tokens):
                return _format_matches(rows, "token_containment", 90)

    # === STAGE 3b: Substring containment (single-token names) ===
    # Handles domain-as-name cases like "youaresavvy" containing "savvy"
    # Only when the DB brand is at least 4 chars (avoid matching "a" inside everything)
    for candidate in candidates:
        if len(candidate) < min_fuzzy_len:
            continue
        for db_norm, rows in exact_index.items():
            if len(db_norm) < 4:
                continue
            # DB brand contained in candidate (e.g., "savvy" in "youaresavvy")
            if db_norm in candidate and len(db_norm) / len(candidate) >= 0.4:
                return _format_matches(rows, "substring", 90)
            # Candidate contained in DB brand (e.g., "boost" in "beauty boost")
            if candidate in db_norm and len(candidate) / len(db_norm) >= 0.4:
                return _format_matches(rows, "substring", 90)

    # === STAGE 4: Fuzzy (rapidfuzz) ===
    # Only for candidates long enough to avoid false positives
    long_candidates = [c for c in candidates if len(c) >= min_fuzzy_len]
    if not long_candidates:
        return []

    try:
        from rapidfuzz import fuzz, process
    except ImportError:
        return []  # Graceful degradation

    all_db_normalized = list(exact_index.keys())
    if not all_db_normalized:
        return []

    best_match_key = None
    best_score = 0

    # Try multiple scorers: token_set_ratio handles word reordering,
    # WRatio handles concatenated names (e.g., "olecapilar" vs "ole capilar")
    scorers = [fuzz.token_set_ratio, fuzz.WRatio]

    for scorer in scorers:
        for candidate in long_candidates:
            result = process.extractOne(
                candidate,
                all_db_normalized,
                scorer=scorer,
                score_cutoff=fuzzy_threshold,
            )
            if result and result[1] > best_score:
                best_match_key = result[0]
                best_score = result[1]

    if best_match_key and best_match_key in exact_index:
        results = _format_matches(
            exact_index[best_match_key], "fuzzy", round(best_score),
        )
        # Supplementary: also check if individual tokens of the matched name
        # exist as standalone brands in other stores. Example: matched
        # "ole capilar" in Farmatodo → also find "ole" in Pasteur.
        matched_stores = {r["store_name"] for r in results}
        for token in best_match_key.split():
            if len(token) < 3:
                continue
            if token in exact_index and token != best_match_key:
                for row in exact_index[token]:
                    store = row.get("retail_department_stores", {}).get("name", "")
                    if store not in matched_stores:
                        results.extend(
                            _format_matches([row], "fuzzy_token", round(best_score))
                        )
                        matched_stores.add(store)
        return results

    return []


def _format_matches(
    rows: List[Dict], match_type: str, match_score: int,
) -> List[Dict]:
    """Format DB rows into standardized match results."""
    results = []
    for row in rows:
        store_info = row.get("retail_department_stores", {})
        results.append({
            "store_name": store_info.get("name", ""),
            "store_country": store_info.get("country", ""),
            "brand_name": row.get("brand_name", ""),
            "detected_at": row.get("detected_at", ""),
            "match_type": match_type,
            "match_score": match_score,
        })
    return results
