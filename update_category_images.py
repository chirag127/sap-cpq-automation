
import requests
import json
import time
from googlesearch import search
import sys

# --- CONFIGURATION ---
# --- CONFIGURATION ---
CPQ_BASE_URL = "https://tataconsultancyservices-partner1.cpq.cloud.sap"
CPQ_TOKEN_URL = f"{CPQ_BASE_URL}/basic/api/token"
CPQ_CAT_API = f"{CPQ_BASE_URL}/api/products/v1/categories"

# CPQ Credentials (for generating fresh token)
CPQ_USERNAME = "REDACTED_CPQ_USERNAME<=="  # Username only
CPQ_DOMAIN = "TATACONSULTANCYSERVICESLIMITED_PARTNER1"
CPQ_PASSWORD = "REDACTED_CPQ_PASSWORD<=="  # Paste the long string from Setup > Users

# Google Search Configuration
SEARCH_SUFFIX = "Massey Ferguson official white background"

def get_cpq_token():
    """Generates a fresh Bearer Token from SAP CPQ"""
    print("🔑 Authenticating with SAP CPQ...")
    payload = {
        'grant_type': 'password',
        'username': CPQ_USERNAME,
        'password': CPQ_PASSWORD,
        'domain': CPQ_DOMAIN
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    try:
        response = requests.post(CPQ_TOKEN_URL, data=payload, headers=headers)
        response.raise_for_status()
        return response.json()['access_token']
    except Exception as e:
        print(f"❌ Auth Failed: {e}")
        sys.exit(1)

def find_image_url(query):
    """
    Searches Google for an image URL matching the query.
    Falls back to a placeholder if no direct image link is found.
    """
    clean_query = query.replace("Chirag Singhal - ", "").strip()
    search_query = f"{clean_query} {SEARCH_SUFFIX}"
    print(f"   🔍 Searching for: '{clean_query}'...", end=" ")

    # OPTION 1: Try Google Search
    try:
        results = search(search_query, num_results=5, advanced=True)
        for result in results:
            if result.url.lower().endswith(('.jpg', '.png', '.jpeg')):
                print("✅ Found URL")
                return result.url
    except:
        pass

    # OPTION 2: Fallback Placeholder
    print("⚠️ Using Placeholder")
    return f"https://placehold.co/600x400/A6192E/FFFFFF/png?text={clean_query.replace(' ', '+')}"

def update_categories():
    token = get_cpq_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    # 1. GET ALL CATEGORIES
    print("📥 Fetching existing categories...")
    try:
        # Fetch categories (Filtering in Python to be safe against OData version diffs)
        response = requests.get(CPQ_CAT_API, headers=headers)
        response.raise_for_status()

        data = response.json()

        # Handle different API response structures (List vs Dict wrapper)
        categories = []
        if isinstance(data, list):
            categories = data
        elif isinstance(data, dict):
            categories = data.get('Items') or data.get('Value') or data.get('PagedList') or []

        # Filter for your specific categories
        my_cats = [c for c in categories if str(c.get('SystemId', '')).startswith('CS_')]
        print(f"   Found {len(my_cats)} 'CS' categories to update.")

    except Exception as e:
        print(f"❌ Failed to get categories: {e}")
        return

    # 2. LOOP AND PATCH
    success_count = 0
    for cat in my_cats:
        cat_id = cat.get('Id')
        sys_id = cat.get('SystemId')
        name = cat.get('Name')

        if not cat_id:
            continue

        # Search for image
        image_url = find_image_url(name)

        # Prepare Patch Payload
        payload = {
            "Id": cat_id,
            "ImageUrl": image_url
        }

        try:
            # PATCH/PUT request to update
            patch_url = f"{CPQ_CAT_API}({cat_id})"
            resp = requests.put(patch_url, headers=headers, json=payload)

            if resp.status_code in [200, 204]:
                print(f"      💾 Updated {sys_id}")
                success_count += 1
            else:
                print(f"      ⚠️ Failed ({resp.status_code}): {resp.text}")

        except Exception as e:
            print(f"      ❌ Error updating {sys_id}: {e}")

        time.sleep(0.5) # Throttle requests

    print(f"\n✅ Finished. Updated {success_count} categories.")

if __name__ == "__main__":
    update_categories()