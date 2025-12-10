
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

# --- FUNCTIONS ---

def get_cpq_token():
    print("🔑 Authenticating...")
    payload = {
        'grant_type': 'password',
        'username': CPQ_USERNAME,
        'password': CPQ_PASSWORD,
        'domain': CPQ_DOMAIN
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    try:
        response = requests.post(CPQ_TOKEN_URL, data=payload, headers=headers)
        if response.status_code != 200:
            print(f"❌ Auth Error {response.status_code}: {response.text}")
            sys.exit(1)
        return response.json()['access_token']
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        sys.exit(1)

def find_image_url(query):
    """Finds an image URL or returns a professional placeholder"""
    clean_query = query.replace("Chirag Singhal - ", "").strip()
    search_query = f"{clean_query} tractor machine white background"

    print(f"   🔍 Query: '{clean_query}'...", end=" ")

    try:
        # Get top 3 results
        results = list(search(search_query, num_results=3, advanced=True))
        for res in results:
            url = res.url
            if any(ext in url.lower() for ext in ['.jpg', '.png', '.jpeg', '.webp']):
                print("✅ Found")
                return url
    except:
        pass

    print("⚠️ Placeholder")
    safe_text = clean_query.replace(" ", "+")
    return f"https://placehold.co/800x600/EFEFEF/A6192E/png?text={safe_text}"

def update_categories():
    token = get_cpq_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    # 1. GET CATEGORIES
    print("📥 Fetching categories...")
    try:
        response = requests.get(CPQ_CAT_API, headers=headers)
        if response.status_code != 200:
            print(f"❌ API Error {response.status_code}: {response.text}")
            return

        data = response.json()
        categories = []

        if isinstance(data, list):
            categories = data
        elif isinstance(data, dict):
            categories = data.get('Items') or data.get('Value') or data.get('PagedList') or []

    except Exception as e:
        print(f"❌ Failed to get categories: {e}")
        return

    # DEBUG: Print first item to see keys
    if categories:
        print(f"   🔎 DEBUG: First Item Keys: {list(categories[0].keys())}")
        print(f"   🔎 DEBUG: First Item Values: {categories[0]}")
    else:
        print("   ❌ No categories found in system at all.")
        return

    # 2. ROBUST FILTERING
    # We check SystemId OR CategoryCode OR Name for "CS_"
    my_cats = []
    for c in categories:
        # Get all potential ID fields
        sys_id = str(c.get('SystemId', ''))
        cat_code = str(c.get('CategoryCode', ''))

        # Check if ANY match 'CS_'
        if sys_id.startswith('CS_') or cat_code.startswith('CS_'):
            my_cats.append(c)

    print(f"   Found {len(my_cats)} matching 'CS_' categories.")

    # 3. UPDATE LOOP
    success_count = 0

    for cat in my_cats:
        cat_id = cat.get('Id')
        # Prefer SystemId, fallback to CategoryCode
        sys_id = cat.get('SystemId') or cat.get('CategoryCode')
        name = cat.get('Name')

        if not cat_id:
            continue

        img_url = find_image_url(name)

        payload = {
            "Id": cat_id,
            "ImageUrl": img_url
        }

        try:
            patch_url = f"{CPQ_CAT_API}({cat_id})"
            resp = requests.put(patch_url, headers=headers, json=payload)

            if resp.status_code in [200, 204]:
                print(f"      💾 Updated {sys_id}")
                success_count += 1
            else:
                print(f"      ❌ Failed: {resp.status_code} - {resp.text}")

        except Exception as e:
            print(f"      ❌ Error: {e}")

        time.sleep(0.5)

    print(f"\n✅ Finished. Updated {success_count} categories.")

if __name__ == "__main__":
    update_categories()