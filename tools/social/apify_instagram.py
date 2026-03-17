"""
SearchAPI Instagram Profile Integration

Purpose: Get Instagram metrics using SearchAPI's instagram_profile engine
Inputs: Instagram username or URL
Outputs: Follower count, posts, engagement metrics
Dependencies: requests, os, datetime

API Endpoint: https://www.searchapi.io/api/v1/search?engine=instagram_profile
Method: GET
"""

import os
import re
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

load_dotenv()


def extract_instagram_username(url_or_username: str) -> Optional[str]:
    """
    Extract Instagram username from URL or return username if already provided.

    Args:
        url_or_username: Instagram URL or username

    Returns:
        Username string or None if invalid
    """
    # If it's already just a username (no slashes, no protocol)
    if '/' not in url_or_username and '://' not in url_or_username:
        return url_or_username.strip('@')

    # Extract from URL patterns
    patterns = [
        r'instagram\.com/([^/?]+)',
        r'instagram\.com/([^/?]+)/',
        r'@([a-zA-Z0-9._]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_username)
        if match:
            username = match.group(1)
            # Remove trailing slash or query params
            username = username.split('?')[0].rstrip('/')
            return username

    return None


def get_instagram_metrics(
    username_or_url: str,
    include_posts: bool = True,
    posts_limit: int = 20
) -> Dict[str, Any]:
    """
    Get Instagram profile metrics using SearchAPI.

    Args:
        username_or_url: Instagram username or profile URL
        include_posts: Whether to use posts for engagement calculation (default: True)
        posts_limit: Not used directly (SearchAPI returns ~12 posts), kept for API compat

    Returns:
        Dict with:
            - success: bool
            - data: dict with metrics (followers, posts_last_30d, engagement_rate, etc.)
            - error: str or None
    """
    try:
        # Extract username
        username = extract_instagram_username(username_or_url)
        if not username:
            return {
                'success': False,
                'data': {},
                'error': f'Invalid Instagram username or URL: {username_or_url}'
            }

        # Get API key from environment
        api_key = os.getenv('SEARCHAPI_API_KEY')
        if not api_key:
            return {
                'success': False,
                'data': {},
                'error': 'SEARCHAPI_API_KEY not found in environment variables'
            }

        # Call SearchAPI instagram_profile engine
        response = requests.get(
            'https://www.searchapi.io/api/v1/search',
            params={
                'engine': 'instagram_profile',
                'username': username,
                'api_key': api_key,
            },
            timeout=30,
        )

        if response.status_code != 200:
            return {
                'success': False,
                'data': {},
                'error': f'SearchAPI error (HTTP {response.status_code}): {response.text[:300]}'
            }

        data = response.json()

        # Check for error in response
        if data.get('error'):
            return {
                'success': False,
                'data': {},
                'error': f"SearchAPI: {data['error']}"
            }

        profile = data.get('profile', {})
        if not profile:
            return {
                'success': False,
                'data': {},
                'error': f'No profile data returned for username: {username}'
            }

        # Extract profile metrics
        followers = profile.get('followers', 0)
        following = profile.get('following', 0)
        posts_count = profile.get('posts', 0)
        full_name = profile.get('name', '')
        biography = profile.get('bio', '')
        profile_pic = profile.get('avatar_hd') or profile.get('avatar', '')
        is_verified = profile.get('is_verified', False)
        is_private = False  # SearchAPI only returns public profiles

        # Calculate engagement metrics from posts
        engagement_rate = 0.0
        posts_last_30_days = 0
        total_engagement = 0

        posts_data = data.get('posts', [])

        if include_posts and posts_data and isinstance(posts_data, list):
            cutoff_date = datetime.now() - timedelta(days=30)

            for post in posts_data:
                iso_date = post.get('iso_date')
                if iso_date:
                    try:
                        post_date = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
                        if post_date.replace(tzinfo=None) > cutoff_date:
                            posts_last_30_days += 1
                            likes = post.get('likes', 0)
                            comments = post.get('comments', 0)
                            total_engagement += (likes + comments)
                    except (ValueError, TypeError):
                        pass

            # Calculate average engagement rate
            if posts_last_30_days > 0 and followers > 0:
                avg_engagement_per_post = total_engagement / posts_last_30_days
                engagement_rate = (avg_engagement_per_post / followers) * 100

        return {
            'success': True,
            'data': {
                'username': username,
                'url': f'https://instagram.com/{username}',
                'followers': followers,
                'following': following,
                'posts_count': posts_count,
                'posts_last_30d': posts_last_30_days,
                'engagement_rate': round(engagement_rate, 2),
                'full_name': full_name,
                'biography': biography,
                'profile_pic': profile_pic,
                'is_verified': is_verified,
                'is_private': is_private,
                'scraped_at': datetime.utcnow().isoformat()
            },
            'error': None
        }

    except requests.exceptions.Timeout:
        return {
            'success': False,
            'data': {},
            'error': 'SearchAPI request timeout (>30s)'
        }

    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'data': {},
            'error': f'SearchAPI request failed: {str(e)}'
        }

    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Instagram scraping error: {str(e)}'
        }


def get_instagram_posts(
    username_or_url: str,
    limit: int = 12,
) -> Dict[str, Any]:
    """
    Get recent posts from an Instagram profile via SearchAPI.

    Args:
        username_or_url: Instagram username or profile URL
        limit: Maximum number of posts to return (default: 12)

    Returns:
        Dict with:
            - success: bool
            - data: dict with username, is_private, followers, and posts list
            - error: str or None
    """
    try:
        username = extract_instagram_username(username_or_url)
        if not username:
            return {
                'success': False,
                'data': {},
                'error': f'Invalid Instagram username or URL: {username_or_url}'
            }

        api_key = os.getenv('SEARCHAPI_API_KEY')
        if not api_key:
            return {
                'success': False,
                'data': {},
                'error': 'SEARCHAPI_API_KEY not found in environment variables'
            }

        response = requests.get(
            'https://www.searchapi.io/api/v1/search',
            params={
                'engine': 'instagram_profile',
                'username': username,
                'api_key': api_key,
            },
            timeout=30,
        )

        if response.status_code != 200:
            return {
                'success': False,
                'data': {},
                'error': f'SearchAPI error (HTTP {response.status_code}): {response.text[:300]}'
            }

        data = response.json()

        if data.get('error'):
            return {
                'success': False,
                'data': {},
                'error': f"SearchAPI: {data['error']}"
            }

        profile = data.get('profile', {})
        followers = profile.get('followers', 0)

        raw_posts = data.get('posts', [])
        posts = []
        for post in raw_posts[:limit]:
            post_id = post.get('id', '')
            permalink = post.get('permalink', '')
            if not post_id:
                continue
            posts.append({
                'shortCode': post_id,
                'url': permalink or f'https://www.instagram.com/p/{post_id}/',
                'timestamp': post.get('iso_date', ''),
                'likesCount': post.get('likes', 0),
                'commentsCount': post.get('comments', 0),
                'caption': (post.get('caption') or '')[:200],
            })

        return {
            'success': True,
            'data': {
                'username': username,
                'is_private': False,
                'followers': followers,
                'posts': posts,
            },
            'error': None
        }

    except requests.exceptions.Timeout:
        return {
            'success': False,
            'data': {},
            'error': 'SearchAPI request timeout (>30s)'
        }

    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'data': {},
            'error': f'SearchAPI request failed: {str(e)}'
        }

    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Instagram posts scraping error: {str(e)}'
        }


def get_multiple_instagram_profiles(
    usernames: list[str],
    include_posts: bool = True
) -> Dict[str, Any]:
    """
    Get metrics for multiple Instagram profiles.

    Args:
        usernames: List of Instagram usernames or URLs
        include_posts: Whether to fetch recent posts

    Returns:
        Dict with:
            - success: bool
            - data: list of profile results
            - error: str or None
    """
    results = []
    errors = []

    for username in usernames:
        result = get_instagram_metrics(username, include_posts=include_posts)
        results.append({
            'username': username,
            'result': result
        })

        if not result['success']:
            errors.append(f"{username}: {result['error']}")

    return {
        'success': len(errors) == 0,
        'data': results,
        'error': '; '.join(errors) if errors else None,
        'stats': {
            'total': len(usernames),
            'successful': len(usernames) - len(errors),
            'failed': len(errors)
        }
    }


if __name__ == '__main__':
    # Test cases
    import sys

    if len(sys.argv) > 1:
        username = sys.argv[1]
    else:
        username = 'nike'

    print("SearchAPI Instagram Profile Test")
    print("=" * 60)
    print(f"Testing with: {username}\n")

    result = get_instagram_metrics(username, include_posts=True)

    print(f"Success: {result['success']}")
    if result['success']:
        data = result['data']
        print(f"\nProfile: @{data['username']}")
        print(f"Full Name: {data['full_name']}")
        print(f"Followers: {data['followers']:,}")
        print(f"Following: {data['following']:,}")
        print(f"Total Posts: {data['posts_count']:,}")
        print(f"Posts (last 30 days): {data['posts_last_30d']}")
        print(f"Engagement Rate: {data['engagement_rate']}%")
        print(f"Verified: {data['is_verified']}")
        print(f"Private: {data['is_private']}")
        print(f"\nBio: {data['biography'][:100]}..." if len(data['biography']) > 100 else f"\nBio: {data['biography']}")
    else:
        print(f"Error: {result['error']}")

    print("\n" + "=" * 60)
    print("Test complete!")
