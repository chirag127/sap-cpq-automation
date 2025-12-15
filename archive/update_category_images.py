import requests
import json
import time
from googlesearch import search
import sys

# --- CONFIGURATION ---
# --- CONFIGURATION ---
CPQ_BASE_URL = "https://tataconsultancyservices-partner1.cpq.cloud.sap"
TOKEN_URL = f"{CPQ_BASE_URL}/basic/api/token"
CAT_API = f"{CPQ_BASE_URL}/api/products/v1/categories"

# CPQ Credentials (for generating fresh token)
CPQ_USERNAME = "REDACTED_CPQ_USERNAME<=="  # Username only
CPQ_DOMAIN = "TATACONSULTANCYSERVICESLIMITED_PARTNER1"
CPQ_PASSWORD = "REDACTED_CPQ_PASSWORD<=="  # Paste the long string from Setup > Users

# --- 1. GET TOKEN ---
def get_token():
    print("🔑 Authenticating...")
    payload = {
        'grant_type': 'password',
        'username': CPQ_USERNAME,
        'password': CPQ_PASSWORD,
        'domain': CPQ_DOMAIN
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    try:
        resp = requests.post(TOKEN_URL, data=payload, headers=headers)
        if resp.status_code != 200:
            print(f"❌ Auth Failed ({resp.status_code}): {resp.text}")
            sys.exit(1)
        return resp.json()['access_token']
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        sys.exit(1)

# --- 2. FIND IMAGE ---
def get_image_url(product_name):
    # Clean the name for better search results
    query = product_name.replace("Chirag Singhal - ", "").strip()
    search_term = f"Massey Ferguson {query} official product photo white background"
    print(f"   🔍 Searching: '{query}'...", end=" ")

    try:
        # Search Google for a valid image URL
        for result in search(search_term, num_results=5, advanced=True):
            url = result.url.lower()
            if url.endswith(('.jpg', '.png', '.jpeg', '.webp')):
                print("✅ Found")
                return result.url
    except:
        pass

    # Fallback to a nice generated placeholder if Google fails
    print("⚠️ Placeholder")
    safe_text = query.replace(" ", "+")
    return f"https://placehold.co/800x600/EFEFEF/A6192E/png?text={safe_text}"

# --- 3. MAIN UPDATE LOOP ---
def run_update():
    token = get_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    print("📥 Fetching ALL categories (Local Filtering)...")
    try:
        # Fetch all categories without server-side filtering to avoid errors
        resp = requests.get(CAT_API, headers=headers)
        if resp.status_code != 200:
            print(f"❌ API Error: {resp.text}")
            return

        # Handle different response formats
        data = resp.json()
        all_cats = data if isinstance(data, list) else data.get('Items', []) or data.get('Value', [])

        print(f"   Total Categories in System: {len(all_cats)}")

        # DEBUG: Print keys of the first item to check field names
        if all_cats:
            print(f"   🔎 Debug Keys: {list(all_cats[0].keys())}")

    except Exception as e:
        print(f"❌ Failed to fetch: {e}")
        return

    # Filter locally for 'CS_'
    my_cats = [c for c in all_cats if str(c.get('SystemId', '')).startswith('CS_') or str(c.get('CategoryCode', '')).startswith('CS_')]

    print(f"   🎯 Found {len(my_cats)} categories to update.\n")

    success = 0
    for cat in my_cats:
        cat_id = cat.get('Id')
        sys_id = cat.get('SystemId') or cat.get('CategoryCode')
        name = cat.get('Name')

        # Get new image
        new_image = get_image_url(name)

        # SAFETY: We start with the existing object so we don't erase data
        # We only update the ImageUrl field
        cat['ImageUrl'] = new_image

        # Remove read-only fields that might cause errors on update
        for field in ['DateCreated', 'DateModified', 'CreatedBy', 'ModifiedBy']:
            cat.pop(field, None)

        try:
            # Send the update
            update_url = f"{CAT_API}({cat_id})"
            update_resp = requests.put(update_url, headers=headers, json=cat)

            if update_resp.status_code in [200, 204]:
                print(f"      💾 Saved: {sys_id}")
                success += 1
            else:
                print(f"      ❌ Failed ({update_resp.status_code}): {update_resp.text}")
        except Exception as e:
            print(f"      ❌ Network Error: {e}")

        time.sleep(0.5) # Be polite

    print(f"\n✅ Job Complete. Updated {success} categories.")

if __name__ == "__main__":
    run_update()