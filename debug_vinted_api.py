#!/usr/bin/env python3
"""Debug script to test Vinted API calls directly."""

import requests
import json
import logging
from urllib.parse import urljoin

# Set up logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

def test_vinted_api():
    """Test different Vinted API endpoints and parameters."""
    
    base_url = "https://www.vinted.at"
    
    # Headers that mimic a real browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.vinted.at/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }
    
    session = requests.Session()
    session.headers.update(headers)
    
    # First, visit the main page to get cookies
    print("1. Testing main page access...")
    try:
        main_response = session.get(base_url, timeout=10)
        print(f"Main page status: {main_response.status_code}")
        print(f"Cookies received: {len(session.cookies)}")
        for cookie in session.cookies:
            print(f"  - {cookie.name}: {cookie.value[:20]}...")
    except Exception as e:
        print(f"Main page error: {e}")
        return
    
    # Test different API endpoints
    api_endpoints = [
        "/api/v2/catalog/items",
        "/api/catalog/items", 
        "/catalog/items",
        "/items"
    ]
    
    search_params = {
        "search_text": "nike",
        "page": 1,
        "per_page": 12
    }
    
    for endpoint in api_endpoints:
        print(f"\n2. Testing endpoint: {endpoint}")
        api_url = urljoin(base_url, endpoint)
        
        try:
            response = session.get(api_url, params=search_params, timeout=15)
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            print(f"Response size: {len(response.content)} bytes")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"JSON keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                    
                    if isinstance(data, dict) and 'items' in data:
                        items = data['items']
                        print(f"Items found: {len(items)}")
                        if items:
                            first_item = items[0]
                            print(f"First item keys: {list(first_item.keys())}")
                            print(f"First item title: {first_item.get('title', 'No title')}")
                            print(f"First item ID: {first_item.get('id', 'No ID')}")
                            return True  # Success!
                    else:
                        print(f"Response structure: {str(data)[:200]}...")
                        
                except json.JSONDecodeError:
                    print("Response is not valid JSON")
                    print(f"Response text: {response.text[:200]}...")
            else:
                print(f"Error response: {response.text[:200]}...")
                
        except Exception as e:
            print(f"Request error: {e}")
    
    # Try with different parameters
    print(f"\n3. Testing with different parameters...")
    alt_params = [
        {"q": "nike", "page": 1, "per_page": 12},
        {"search": "nike", "page": 1, "limit": 12},
        {"query": "nike", "page": 1, "size": 12},
        {"search_text": "nike", "order": "newest_first"},
    ]
    
    for params in alt_params:
        print(f"\nTrying params: {params}")
        try:
            response = session.get(f"{base_url}/api/v2/catalog/items", params=params, timeout=10)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, dict) and 'items' in data and data['items']:
                        print(f"SUCCESS! Found {len(data['items'])} items")
                        return True
                except:
                    pass
        except Exception as e:
            print(f"Error: {e}")
    
    return False

if __name__ == "__main__":
    success = test_vinted_api()
    if not success:
        print("\n❌ All API tests failed - Vinted might be blocking requests or API has changed")
    else:
        print("\n✅ Found working API endpoint!")