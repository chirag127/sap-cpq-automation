import requests
import json
import time
from googlesearch import search

# --- CONFIGURATION ---
CPQ_BASE_URL = "https://tataconsultancyservices-partner1.cpq.cloud.sap"
CPQ_TOKEN_URL = f"{CPQ_BASE_URL}/basic/api/token"
CPQ_CAT_API = f"{CPQ_BASE_URL}/api/products/v1/categories"

# CPQ Credentials (for generating fresh token)
CPQ_USERNAME = "REDACTED_CPQ_USERNAME<=="  # Username only
CPQ_DOMAIN = "TATACONSULTANCYSERVICESLIMITED_PARTNER1"
CPQ_PASSWORD = "REDACTED_CPQ_PASSWORD<=="  # Paste the long string from Setup > Users

# Google Search Configuration
SEARCH_SUFFIX = "Massey Ferguson official white background" # Helps find clean product images

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
        exit()

def find_image_url(query):
    """
    Searches Google for an image URL matching the query.
    Note: Real production apps use the Google Custom Search JSON API.
    This is a simplified scraper approach.
    """
    search_query = f"{query} {SEARCH_SUFFIX}"
    print(f"   🔍 Searching for: '{search_query}'...")

    # We use a trick: search for direct image links or official site pages
    # Since we can't scrape Google Images directly easily without an API Key,
    # we will use a placeholder logic here.
    # To make this WORK FOR REAL, you should put a real image URL or use a hardcoded map.

    # OPTION A: Use a placeholder service that generates images based on text (Reliable)
    # return f"https://dummyimage.com/600x400/A6192E/fff&text={query.replace(' ', '+')}"

    # OPTION B: Attempt to find a real URL (Unreliable without API Key)
    try:
        results = search(search_query, num_results=5, advanced=True)
        for result in results:
            # Simple heuristic: try to find a jpg/png
            if result.url.endswith('.jpg') or result.url.endswith('.png'):
                return result.url
    except:
        pass

    # Fallback to a clean placeholder if search fails
    return f"https://placehold.co/600x400/A6192E/FFFFFF/png?text={query.replace(' ', '+')}"

def update_categories():
    token = get_cpq_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    # 1. GET ALL CATEGORIES
    print("📥 Fetching existing categories...")
    try:
        # Filter for only YOUR categories to avoid touching system ones
        # We assume they start with "CS_" based on your previous steps
        response = requests.get(f"{CPQ_CAT_API}?$filter=startswith(SystemId,'CS_')", headers=headers)
        categories = response.json()

        if 'Value' in categories: categories = categories['Value'] # Handle OData wrapper

        print(f"   Found {len(categories)} categories to update.")

    except Exception as e:
        print(f"❌ Failed to get categories: {e}")
        return

    # 2. LOOP AND PATCH
    for cat in categories:
        cat_id = cat['Id']
        sys_id = cat['SystemId']
        name = cat['Name'].replace("Chirag Singhal - ", "") # Clean name for search

        # Search for image
        image_url = find_image_url(name)

        # Prepare Patch Payload
        # We assume the field is 'ImageUrl' or similar standard CPQ field
        payload = {
            "Id": cat_id,
            "ImageUrl": image_url
        }

        print(f"   🖼️ Patching {sys_id} with image...")

        try:
            # PATCH request to update specific fields
            patch_url = f"{CPQ_CAT_API}({cat_id})"
            resp = requests.put(patch_url, headers=headers, json=payload) # CPQ often uses PUT for updates

            if resp.status_code in [200, 204]:
                print(f"   ✅ Success: {sys_id}")
            else:
                print(f"   ⚠️ Failed ({resp.status_code}): {resp.text}")

        except Exception as e:
            print(f"   ❌ Error updating {sys_id}: {e}")

        time.sleep(1) # Be polite to the API

if __name__ == "__main__":
    update_categories()