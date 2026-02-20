"""
Input Reader Tool

Purpose: Read and clean a list of URLs/brand names from a text file
Inputs: File path to a plain text file
Outputs: Cleaned, deduplicated list of entries
Dependencies: tools/core/url_normalizer.py, tools/core/resolve_brand_url.py
"""

import os
import sys
from typing import Dict, Any

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.url_normalizer import normalize_url, extract_domain
from core.resolve_brand_url import _looks_like_url


def _classify_entry(text: str) -> dict:
    """
    Classify a single entry as URL or brand name.

    Returns:
        dict with 'raw', 'cleaned', 'type' ('url'|'brand_name'), 'domain'
    """
    cleaned = text.strip()

    if _looks_like_url(cleaned):
        # It's a URL — normalize to extract domain
        norm_result = normalize_url(cleaned)
        domain = None
        if norm_result['success']:
            domain = extract_domain(norm_result['data']['url'])
        return {
            'raw': text,
            'cleaned': cleaned,
            'type': 'url',
            'domain': domain
        }
    else:
        return {
            'raw': text,
            'cleaned': cleaned,
            'type': 'brand_name',
            'domain': None
        }


def read_input_list(file_path: str) -> Dict[str, Any]:
    """
    Read a text file of URLs/brand names and return cleaned entries.

    Each line should be a URL or brand name.
    Lines starting with # are comments.
    Empty lines are skipped.
    Duplicate domains are removed (first occurrence wins).

    Args:
        file_path: Path to text file

    Returns:
        Dict with:
            - success: bool
            - data: dict with entries[], total_lines, valid_entries,
                     duplicates_removed, comments_skipped
            - error: str or None
    """
    try:
        if not os.path.exists(file_path):
            return {
                'success': False,
                'data': {},
                'error': f'File not found: {file_path}'
            }

        # Read file with encoding fallback
        content = None
        for encoding in ['utf-8', 'latin-1']:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            return {
                'success': False,
                'data': {},
                'error': f'Unable to read file (encoding error): {file_path}'
            }

        lines = content.splitlines()
        total_lines = len(lines)
        comments_skipped = 0
        duplicates_removed = 0
        entries = []
        seen_domains = set()

        for line in lines:
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Skip comments
            if stripped.startswith('#'):
                comments_skipped += 1
                continue

            entry = _classify_entry(stripped)

            # Deduplicate URLs by domain (first occurrence wins)
            if entry['type'] == 'url' and entry['domain']:
                domain_key = entry['domain'].lower()
                if domain_key in seen_domains:
                    duplicates_removed += 1
                    continue
                seen_domains.add(domain_key)

            entries.append(entry)

        return {
            'success': True,
            'data': {
                'entries': entries,
                'total_lines': total_lines,
                'valid_entries': len(entries),
                'duplicates_removed': duplicates_removed,
                'comments_skipped': comments_skipped
            },
            'error': None
        }

    except PermissionError:
        return {
            'success': False,
            'data': {},
            'error': f'Permission denied: {file_path}'
        }
    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Input reader error: {str(e)}'
        }


if __name__ == '__main__':
    file_path = sys.argv[1] if len(sys.argv) > 1 else 'urls.txt'

    print("Input Reader")
    print("=" * 60)
    print(f"File: {file_path}")

    result = read_input_list(file_path)
    print(f"\nSuccess: {result['success']}")

    if result['success']:
        data = result['data']
        print(f"  Total lines: {data['total_lines']}")
        print(f"  Valid entries: {data['valid_entries']}")
        print(f"  Duplicates removed: {data['duplicates_removed']}")
        print(f"  Comments skipped: {data['comments_skipped']}")
        print(f"\n  Entries:")
        for entry in data['entries'][:10]:
            print(f"    [{entry['type']}] {entry['cleaned']} (domain: {entry['domain']})")
        if len(data['entries']) > 10:
            print(f"    ... and {len(data['entries']) - 10} more")
    else:
        print(f"  Error: {result['error']}")
