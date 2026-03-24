"""
Apollo.io Enrichment Tool

Purpose: Enrich company info and find decision-maker contacts via Apollo.io API
Inputs: Domain name
Outputs: Company info, decision-maker contacts with emails
Dependencies: requests, python-dotenv

API Endpoints:
  - POST https://api.apollo.io/api/v1/organizations/enrich
  - POST https://api.apollo.io/api/v1/mixed_people/api_search  (people search, free)
  - POST https://api.apollo.io/api/v1/people/match              (enrichment, 1 credit each)

Note: Returns stub data when APOLLO_API_KEY is not set (success=True, source='stub').
"""

import os
import sys
from typing import Dict, Any, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

APOLLO_BASE_URL = "https://api.apollo.io/api/v1"
DEFAULT_TITLES = [
    # English
    "CEO", "COO", "CTO", "CFO",
    "Head of Logistics", "Head of Operations",
    "VP of Operations", "Director of Supply Chain",
    "Head of E-commerce", "Founder", "Co-Founder", "Owner",
    # Spanish
    "Director General", "Director de Operaciones",
    "Director de Logística", "Director Comercial",
    "Gerente General", "Gerente de Operaciones",
    "Gerente de Logística", "Gerente Comercial",
    "Jefe de Logística", "Jefe de Operaciones",
    "Fundador", "Fundadora",
]


def _get_api_key() -> Optional[str]:
    """Get Apollo API key from environment."""
    return os.getenv('APOLLO_API_KEY')


def _empty_company_data(source: str = 'stub') -> dict:
    """Return empty company data structure."""
    return {
        'company_name': '',
        'industry': '',
        'employee_count': None,
        'employee_range': '',
        'linkedin_url': '',
        'founded_year': None,
        'description': '',
        'logo_url': '',
        'phone': '',
        'city': '',
        'country': '',
        'technologies': [],
        'source': source
    }


def enrich_company(domain: str) -> Dict[str, Any]:
    """
    Enrich company information from Apollo.io.

    Args:
        domain: Company website domain (e.g., 'armatura.com.co')

    Returns:
        Dict with:
            - success: bool
            - data: dict with company_name, industry, employee_count, etc.
            - error: str or None
    """
    api_key = _get_api_key()

    if not api_key:
        return {
            'success': True,
            'data': _empty_company_data('stub'),
            'error': None
        }

    try:
        response = requests.post(
            f"{APOLLO_BASE_URL}/organizations/enrich",
            headers={"Content-Type": "application/json", "X-Api-Key": api_key},
            json={"domain": domain},
            timeout=30
        )

        if response.status_code == 401:
            return {
                'success': False,
                'data': {},
                'error': 'Invalid APOLLO_API_KEY'
            }

        if response.status_code == 429:
            return {
                'success': False,
                'data': {},
                'error': 'Apollo API rate limit reached'
            }

        if response.status_code >= 400:
            return {
                'success': False,
                'data': {},
                'error': f'Apollo API error (HTTP {response.status_code}): {response.text[:200]}'
            }

        data = response.json()
        org = data.get('organization', {})

        if not org:
            return {
                'success': True,
                'data': _empty_company_data('apollo'),
                'error': None
            }

        return {
            'success': True,
            'data': {
                'company_name': org.get('name', ''),
                'industry': org.get('industry', ''),
                'employee_count': org.get('estimated_num_employees'),
                'employee_range': org.get('employee_range', ''),
                'linkedin_url': org.get('linkedin_url', ''),
                'founded_year': org.get('founded_year'),
                'description': org.get('short_description', ''),
                'logo_url': org.get('logo_url', ''),
                'phone': org.get('phone', ''),
                'city': org.get('city', ''),
                'country': org.get('country', ''),
                'technologies': org.get('technology_names', []),
                'source': 'apollo'
            },
            'error': None
        }

    except requests.exceptions.Timeout:
        return {
            'success': False,
            'data': {},
            'error': 'Apollo API request timed out (>30s)'
        }
    except requests.exceptions.ConnectionError as e:
        return {
            'success': False,
            'data': {},
            'error': f'Apollo API connection error: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Apollo enrichment error: {str(e)}'
        }


MAX_ENRICH_PER_DOMAIN = 5  # Limit enrichment calls to control credit usage


def _enrich_person(person_id: str, api_key: str) -> Optional[Dict[str, Any]]:
    """
    Enrich a single person via Apollo /people/match to get email & phone.
    Costs 1 credit per call.

    Returns enriched person dict or None on failure.
    """
    try:
        response = requests.post(
            f"{APOLLO_BASE_URL}/people/match",
            headers={"Content-Type": "application/json", "X-Api-Key": api_key},
            json={"id": person_id, "reveal_personal_emails": False},
            timeout=30
        )
        if response.status_code != 200:
            return None
        data = response.json()
        return data.get('person')
    except Exception:
        return None


def find_decision_makers(
    domain: str,
    titles: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Find decision-maker contacts at a company via Apollo.io.

    Two-step process:
      1. Search people with /mixed_people/api_search (free, no credits)
      2. Enrich top results with /people/match to get emails (1 credit each)

    Args:
        domain: Company website domain
        titles: List of job titles to search for (default: DEFAULT_TITLES)

    Returns:
        Dict with:
            - success: bool
            - data: dict with contacts list, total_found, source
            - error: str or None
    """
    api_key = _get_api_key()

    if not api_key:
        return {
            'success': True,
            'data': {
                'contacts': [],
                'total_found': 0,
                'domain': domain,
                'source': 'stub'
            },
            'error': None
        }

    search_titles = titles or DEFAULT_TITLES

    try:
        # --- Step 1: Search (free, no credits) ---
        response = requests.post(
            f"{APOLLO_BASE_URL}/mixed_people/api_search",
            headers={"Content-Type": "application/json", "X-Api-Key": api_key},
            json={
                "q_organization_domains": domain,
                "person_titles": search_titles,
                "page": 1,
                "per_page": 10
            },
            timeout=30
        )

        if response.status_code == 401:
            return {
                'success': False,
                'data': {},
                'error': 'Invalid APOLLO_API_KEY'
            }

        if response.status_code == 429:
            return {
                'success': False,
                'data': {},
                'error': 'Apollo API rate limit reached'
            }

        if response.status_code == 403:
            return {
                'success': True,
                'data': {
                    'contacts': [],
                    'total_found': 0,
                    'domain': domain,
                    'source': 'apollo'
                },
                'error': 'People search requires a paid Apollo plan'
            }

        if response.status_code >= 400:
            return {
                'success': False,
                'data': {},
                'error': f'Apollo API error (HTTP {response.status_code}): {response.text[:200]}'
            }

        data = response.json()
        people = data.get('people', [])

        if not people:
            # Retry with seniority filter (language-agnostic, free)
            try:
                retry_response = requests.post(
                    f"{APOLLO_BASE_URL}/mixed_people/api_search",
                    headers={"Content-Type": "application/json", "X-Api-Key": api_key},
                    json={
                        "q_organization_domains": domain,
                        "person_seniorities": ["owner", "founder", "c_suite", "vp", "director"],
                        "page": 1,
                        "per_page": 10
                    },
                    timeout=30
                )
                if retry_response.status_code == 200:
                    people = retry_response.json().get('people', [])
            except Exception:
                pass  # keep people as empty list

        if not people:
            return {
                'success': True,
                'data': {
                    'contacts': [],
                    'total_found': 0,
                    'domain': domain,
                    'source': 'apollo'
                },
                'error': None
            }

        # --- Step 2: Enrich top candidates to get emails (1 credit each) ---
        contacts = []
        enriched_count = 0

        for person in people:
            person_id = person.get('id')
            name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
            title = person.get('title', '')
            linkedin = person.get('linkedin_url')

            # Try enrichment if we haven't hit the limit
            email = None
            phone = None
            confidence = 0.0

            if person_id and enriched_count < MAX_ENRICH_PER_DOMAIN:
                enriched = _enrich_person(person_id, api_key)
                if enriched:
                    enriched_count += 1
                    email = enriched.get('email')
                    confidence = (enriched.get('email_confidence', 0) or 0) / 100
                    # Phone can be in phone_numbers array or direct field
                    phone_numbers = enriched.get('phone_numbers') or []
                    if phone_numbers:
                        phone = phone_numbers[0].get('sanitized_number') or phone_numbers[0].get('raw_number')
                    elif enriched.get('phone_number'):
                        phone = enriched.get('phone_number')
                    # Use enriched name/linkedin if better
                    if enriched.get('name'):
                        name = enriched['name']
                    if enriched.get('linkedin_url'):
                        linkedin = enriched['linkedin_url']

            contacts.append({
                'name': name,
                'title': title,
                'email': email,
                'linkedin_url': linkedin,
                'confidence': confidence,
                'phone': phone
            })

        return {
            'success': True,
            'data': {
                'contacts': contacts,
                'total_found': len(contacts),
                'domain': domain,
                'source': 'apollo'
            },
            'error': None
        }

    except requests.exceptions.Timeout:
        return {
            'success': False,
            'data': {},
            'error': 'Apollo API request timed out (>30s)'
        }
    except requests.exceptions.ConnectionError as e:
        return {
            'success': False,
            'data': {},
            'error': f'Apollo API connection error: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Apollo people search error: {str(e)}'
        }


def _get_fallback_domains(domain: str) -> List[str]:
    """
    Generate alternate domains to try in Apollo when the primary domain returns nothing.

    Examples:
        platanomelon.mx      → [platanomelon.com]
        gaiadesign.com.mx    → [gaiadesign.com]
        onehalf.com.co       → [onehalf.com]
        armatura.com.co      → [armatura.com]
        example.com          → []  (already .com, no fallback)
    """
    compound_tlds = ['.com.mx', '.com.co', '.com.ar', '.com.br', '.com.pe', '.com.ec']
    country_tlds = ['.mx', '.co', '.ar', '.cl', '.pe', '.ec', '.br']

    for ctld in compound_tlds:
        if domain.endswith(ctld):
            base = domain[:-len(ctld)]
            return [f"{base}.com"]

    for ctld in country_tlds:
        if domain.endswith(ctld):
            base = domain[:-len(ctld)]
            return [f"{base}.com"]

    return []


def _has_apollo_data(company_result: dict, contacts_result: dict) -> bool:
    """Check if Apollo returned any meaningful data."""
    company_data = company_result.get('data', {})
    has_company = (
        company_data.get('source') == 'apollo'
        and (company_data.get('company_name') or company_data.get('linkedin_url'))
    )
    contacts = contacts_result.get('data', {}).get('contacts', [])
    has_contacts = len(contacts) > 0
    return has_company or has_contacts


def apollo_enrich(domain: str) -> Dict[str, Any]:
    """
    Combined company enrichment + decision-maker search.
    If the primary domain returns nothing, tries fallback domains
    (e.g. platanomelon.mx → platanomelon.com).

    Args:
        domain: Company website domain

    Returns:
        Dict with:
            - success: bool
            - data: dict with company info, contacts, domain, source, apollo_domain
            - error: str or None
    """
    try:
        company_result = enrich_company(domain)
        contacts_result = find_decision_makers(domain)
        used_domain = domain

        # If primary domain returned nothing, try fallback domains
        if not _has_apollo_data(company_result, contacts_result):
            fallbacks = _get_fallback_domains(domain)
            for fallback_domain in fallbacks:
                fb_company = enrich_company(fallback_domain)
                fb_company_data = fb_company.get('data', {})
                # Check if this fallback has company data
                if fb_company_data.get('source') == 'apollo' and (
                    fb_company_data.get('company_name') or fb_company_data.get('linkedin_url')
                ):
                    company_result = fb_company
                    contacts_result = find_decision_makers(fallback_domain)
                    used_domain = fallback_domain
                    break

        # Determine overall source
        company_source = company_result.get('data', {}).get('source', 'unknown')
        contacts_source = contacts_result.get('data', {}).get('source', 'unknown')
        source = 'apollo' if 'apollo' in (company_source, contacts_source) else 'stub'

        company_data = company_result.get('data', _empty_company_data(source))
        contacts_data = contacts_result.get('data', {}).get('contacts', [])

        # Collect errors
        errors = []
        if not company_result['success']:
            errors.append(f"Company: {company_result['error']}")
        if not contacts_result['success']:
            errors.append(f"Contacts: {contacts_result['error']}")

        return {
            'success': True,
            'data': {
                'company': company_data,
                'contacts': contacts_data,
                'domain': domain,
                'apollo_domain': used_domain,
                'source': source
            },
            'error': '; '.join(errors) if errors else None
        }

    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Apollo enrichment error: {str(e)}'
        }


if __name__ == '__main__':
    test_domain = sys.argv[1] if len(sys.argv) > 1 else 'example.com'

    print("Apollo.io Enrichment")
    print("=" * 60)
    print(f"Domain: {test_domain}")

    result = apollo_enrich(test_domain)
    print(f"\nSuccess: {result['success']}")

    if result['success']:
        data = result['data']
        print(f"  Source: {data.get('source')}")

        company = data.get('company', {})
        if company.get('company_name'):
            print(f"\n  Company: {company['company_name']}")
            print(f"  Industry: {company.get('industry', 'N/A')}")
            print(f"  Employees: {company.get('employee_range', 'N/A')}")
            print(f"  Country: {company.get('country', 'N/A')}")
            print(f"  LinkedIn: {company.get('linkedin_url', 'N/A')}")
        else:
            print(f"\n  Company: No data {'(stub mode - set APOLLO_API_KEY)' if data['source'] == 'stub' else ''}")

        contacts = data.get('contacts', [])
        print(f"\n  Contacts found: {len(contacts)}")
        for c in contacts[:5]:
            print(f"    - {c['name']} ({c['title']}): {c.get('email', 'N/A')}")

        if result.get('error'):
            print(f"\n  Warnings: {result['error']}")
    else:
        print(f"  Error: {result['error']}")
