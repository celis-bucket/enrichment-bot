"""
Apify Instagram Scraper Integration

Purpose: Get Instagram metrics using Apify's Instagram scraper
Inputs: Instagram username or URL
Outputs: Follower count, posts, engagement metrics
Dependencies: requests, os, datetime

API Endpoint: https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items
Method: POST
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
    Get Instagram profile metrics using Apify API.

    Args:
        username_or_url: Instagram username or profile URL
        include_posts: Whether to fetch recent posts (default: True)
        posts_limit: Number of recent posts to fetch (default: 20)

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

        # Get API credentials from environment
        api_token = os.getenv('APIFY_API_TOKEN')
        if not api_token:
            return {
                'success': False,
                'data': {},
                'error': 'APIFY_API_TOKEN not found in environment variables'
            }

        # Get endpoint URL (allow override via env)
        endpoint = os.getenv(
            'APIFY_INSTAGRAM_ENDPOINT',
            'https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items'
        )

        # Build full URL with token
        url = f"{endpoint}?token={api_token}"

        # Build Instagram profile URL
        instagram_url = f"https://www.instagram.com/{username}/"

        # Prepare request payload using directUrls approach
        payload = {
            "directUrls": [instagram_url],
            "resultsType": "details",
            "searchLimit": 1
        }

        # Make API request
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=120  # Apify can take time to scrape
        )

        # Check response status (200 OK or 201 Created are both valid)
        if response.status_code not in [200, 201]:
            return {
                'success': False,
                'data': {},
                'error': f'Apify API error (HTTP {response.status_code}): {response.text}'
            }

        # Parse response
        data = response.json()

        # Check for error in response body (Apify may return 201 with error)
        if isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            if isinstance(first_item, dict) and first_item.get('error'):
                return {
                    'success': False,
                    'data': {},
                    'error': f"Apify error: {first_item.get('error')} - {first_item.get('errorDescription', '')}"
                }

        # Apify returns array of results
        if not data or len(data) == 0:
            return {
                'success': False,
                'data': {},
                'error': f'No data returned for username: {username}'
            }

        # Get first result (profile data)
        profile = data[0] if isinstance(data, list) else data

        # Extract metrics - handle both old and new field names
        followers = profile.get('followersCount') or profile.get('followers', 0)
        following = profile.get('followsCount') or profile.get('following', 0)
        posts_count = profile.get('postsCount') or profile.get('posts', 0)

        # Profile info
        full_name = profile.get('fullName') or profile.get('full_name', '')
        biography = profile.get('biography') or profile.get('bio', '')
        profile_pic = profile.get('profilePicUrl') or profile.get('profile_pic_url', '')
        is_verified = profile.get('verified', False)
        is_private = profile.get('private') or profile.get('isPrivate', False)

        # Calculate engagement metrics from recent posts
        engagement_rate = 0.0
        posts_last_30_days = 0
        total_engagement = 0

        # Check for posts in different possible field names
        posts_data = profile.get('latestPosts') or profile.get('posts') or profile.get('recentPosts') or []

        if include_posts and posts_data and isinstance(posts_data, list):
            cutoff_date = datetime.now() - timedelta(days=30)

            for post in posts_data:
                # Get post timestamp (try multiple field names)
                timestamp = post.get('timestamp') or post.get('taken_at') or post.get('takenAt')
                if timestamp:
                    try:
                        if isinstance(timestamp, str):
                            post_date = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        else:
                            # Unix timestamp
                            post_date = datetime.fromtimestamp(timestamp)

                        if post_date.replace(tzinfo=None) > cutoff_date:
                            posts_last_30_days += 1

                            # Calculate engagement for this post
                            likes = post.get('likesCount') or post.get('likes', 0)
                            comments = post.get('commentsCount') or post.get('comments', 0)
                            total_engagement += (likes + comments)
                    except:
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
            'error': 'Apify API request timeout (>60s)'
        }

    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'data': {},
            'error': f'Apify API request failed: {str(e)}'
        }

    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Instagram scraping error: {str(e)}'
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
        # Test with provided username
        username = sys.argv[1]
    else:
        # Default test username
        username = 'instagram'  # Instagram's official account

    print("Apify Instagram Scraper Test")
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
