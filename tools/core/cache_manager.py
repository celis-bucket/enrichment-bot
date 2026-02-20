"""
Cache Manager Tool

Purpose: JSON file-based cache with 7-day TTL for enrichment results
Inputs: Domain, tool name, data to cache
Outputs: Cached data or cache miss
Dependencies: json, os, time

Cache files stored at: .tmp/cache/{domain}/{tool_name}.json
"""

import os
import sys
import json
import time
import shutil
from typing import Dict, Any, Optional
from pathlib import Path

# Cache configuration
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '.tmp', 'cache')
DEFAULT_TTL = 7 * 24 * 60 * 60  # 7 days in seconds
CACHE_VERSION = "1.0"


def _sanitize_domain(domain: str) -> str:
    """
    Clean domain for use as directory name.
    Strips www., lowercases, replaces unsafe filesystem characters.
    """
    domain = domain.strip().lower()
    if domain.startswith('www.'):
        domain = domain[4:]
    # Replace characters that are unsafe in file paths
    for char in [':', '/', '\\', '?', '*', '"', '<', '>', '|']:
        domain = domain.replace(char, '_')
    return domain


def _get_cache_path(domain: str, tool_name: str) -> str:
    """Get the file path for a cache entry."""
    safe_domain = _sanitize_domain(domain)
    safe_tool = tool_name.strip().replace('/', '_').replace('\\', '_')
    return os.path.join(CACHE_DIR, safe_domain, f"{safe_tool}.json")


def cache_get(domain: str, tool_name: str) -> Dict[str, Any]:
    """
    Retrieve cached data for a domain/tool combination.

    Args:
        domain: Website domain (e.g., 'armatura.com.co')
        tool_name: Tool identifier (e.g., 'detect_geography')

    Returns:
        Dict with:
            - success: True if cache hit, False if miss or expired
            - data: cached data dict (empty if miss)
            - error: str or None
    """
    try:
        cache_path = _get_cache_path(domain, tool_name)

        if not os.path.exists(cache_path):
            return {
                'success': False,
                'data': {},
                'error': None  # Cache miss is not an error
            }

        with open(cache_path, 'r', encoding='utf-8') as f:
            cache_entry = json.load(f)

        metadata = cache_entry.get('metadata', {})
        expires_at = metadata.get('expires_at', 0)

        # Check if expired
        if time.time() > expires_at:
            return {
                'success': False,
                'data': {},
                'error': None  # Expired cache miss is not an error
            }

        return {
            'success': True,
            'data': cache_entry.get('data', {}),
            'error': None
        }

    except (json.JSONDecodeError, KeyError):
        # Corrupted cache file — delete it silently
        try:
            os.remove(_get_cache_path(domain, tool_name))
        except OSError:
            pass
        return {
            'success': False,
            'data': {},
            'error': None
        }
    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Cache read error: {str(e)}'
        }


def cache_set(domain: str, tool_name: str, data: dict, ttl: int = DEFAULT_TTL) -> Dict[str, Any]:
    """
    Store data in cache for a domain/tool combination.

    Args:
        domain: Website domain
        tool_name: Tool identifier
        data: Data dict to cache
        ttl: Time-to-live in seconds (default: 7 days)

    Returns:
        Dict with:
            - success: bool
            - data: {cache_path, expires_at}
            - error: str or None
    """
    try:
        cache_path = _get_cache_path(domain, tool_name)
        cache_dir = os.path.dirname(cache_path)
        os.makedirs(cache_dir, exist_ok=True)

        now = time.time()
        expires_at = now + ttl

        cache_entry = {
            'metadata': {
                'domain': _sanitize_domain(domain),
                'tool_name': tool_name,
                'cached_at': now,
                'cached_at_iso': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now)),
                'ttl': ttl,
                'expires_at': expires_at,
                'cache_version': CACHE_VERSION
            },
            'data': data
        }

        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_entry, f, indent=2, ensure_ascii=False, default=str)

        return {
            'success': True,
            'data': {
                'cache_path': cache_path,
                'expires_at': expires_at
            },
            'error': None
        }

    except (TypeError, ValueError) as e:
        return {
            'success': False,
            'data': {},
            'error': f'Data serialization error: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Cache write error: {str(e)}'
        }


def is_cached(domain: str, tool_name: str) -> bool:
    """Check if valid (non-expired) cache entry exists."""
    result = cache_get(domain, tool_name)
    return result['success']


def cache_clear(domain: Optional[str] = None) -> Dict[str, Any]:
    """
    Clear cache entries.

    Args:
        domain: If provided, clear only this domain. If None, clear entire cache.

    Returns:
        Dict with:
            - success: bool
            - data: {entries_cleared: int}
            - error: str or None
    """
    try:
        entries_cleared = 0

        if domain:
            # Clear specific domain
            domain_dir = os.path.join(CACHE_DIR, _sanitize_domain(domain))
            if os.path.exists(domain_dir):
                for f in os.listdir(domain_dir):
                    if f.endswith('.json'):
                        os.remove(os.path.join(domain_dir, f))
                        entries_cleared += 1
                # Remove empty directory
                try:
                    os.rmdir(domain_dir)
                except OSError:
                    pass
        else:
            # Clear entire cache
            if os.path.exists(CACHE_DIR):
                for domain_dir in os.listdir(CACHE_DIR):
                    domain_path = os.path.join(CACHE_DIR, domain_dir)
                    if os.path.isdir(domain_path):
                        for f in os.listdir(domain_path):
                            if f.endswith('.json'):
                                entries_cleared += 1
                        shutil.rmtree(domain_path)

        return {
            'success': True,
            'data': {'entries_cleared': entries_cleared},
            'error': None
        }

    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Cache clear error: {str(e)}'
        }


def get_cache_stats() -> Dict[str, Any]:
    """
    Return cache statistics.

    Returns:
        Dict with:
            - success: bool
            - data: {total_entries, total_size_bytes, expired_entries, domains}
            - error: str or None
    """
    try:
        total_entries = 0
        expired_entries = 0
        total_size = 0
        domains = []

        if not os.path.exists(CACHE_DIR):
            return {
                'success': True,
                'data': {
                    'total_entries': 0,
                    'total_size_bytes': 0,
                    'expired_entries': 0,
                    'domains': []
                },
                'error': None
            }

        now = time.time()

        for domain_dir in os.listdir(CACHE_DIR):
            domain_path = os.path.join(CACHE_DIR, domain_dir)
            if not os.path.isdir(domain_path):
                continue

            domain_count = 0
            for f in os.listdir(domain_path):
                if not f.endswith('.json'):
                    continue

                file_path = os.path.join(domain_path, f)
                total_entries += 1
                domain_count += 1
                total_size += os.path.getsize(file_path)

                try:
                    with open(file_path, 'r', encoding='utf-8') as fh:
                        entry = json.load(fh)
                    if now > entry.get('metadata', {}).get('expires_at', 0):
                        expired_entries += 1
                except (json.JSONDecodeError, KeyError):
                    expired_entries += 1

            if domain_count > 0:
                domains.append(domain_dir)

        return {
            'success': True,
            'data': {
                'total_entries': total_entries,
                'total_size_bytes': total_size,
                'expired_entries': expired_entries,
                'domains': domains
            },
            'error': None
        }

    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Cache stats error: {str(e)}'
        }


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'stats'

    print("Cache Manager")
    print("=" * 60)

    if action == 'stats':
        result = get_cache_stats()
        print(f"\nSuccess: {result['success']}")
        if result['success']:
            data = result['data']
            print(f"  Total entries: {data['total_entries']}")
            print(f"  Total size: {data['total_size_bytes']} bytes")
            print(f"  Expired: {data['expired_entries']}")
            print(f"  Domains: {', '.join(data['domains']) or 'None'}")
        else:
            print(f"  Error: {result['error']}")

    elif action == 'clear':
        domain = sys.argv[2] if len(sys.argv) > 2 else None
        result = cache_clear(domain)
        print(f"\nClearing: {'domain ' + domain if domain else 'all cache'}")
        print(f"Success: {result['success']}")
        if result['success']:
            print(f"  Entries cleared: {result['data']['entries_cleared']}")
        else:
            print(f"  Error: {result['error']}")

    elif action == 'test':
        print("\nRunning cache test cycle...")

        # Set
        set_result = cache_set('test.example.com', 'test_tool', {'key': 'value', 'number': 42})
        print(f"\n  SET: success={set_result['success']}")

        # Check
        check = is_cached('test.example.com', 'test_tool')
        print(f"  IS_CACHED: {check}")

        # Get
        get_result = cache_get('test.example.com', 'test_tool')
        print(f"  GET: success={get_result['success']}, data={get_result['data']}")

        # Clear
        clear_result = cache_clear('test.example.com')
        print(f"  CLEAR: entries_cleared={clear_result['data'].get('entries_cleared', 0)}")

        # Verify cleared
        check_after = is_cached('test.example.com', 'test_tool')
        print(f"  IS_CACHED after clear: {check_after}")

        print("\n  Test complete.")
    else:
        print(f"\nUnknown action: {action}")
        print("Usage: python cache_manager.py [stats|clear|test] [domain]")
