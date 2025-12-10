import requests
import json
import re
import sys

# --- CONFIGURATION ---
BASE_URL = "https://tataconsultancyservices-partner1.cpq.cloud.sap"
API_ENDPOINT = f"{BASE_URL}/api/products/v1/categories"

# PASTE YOUR *NEW* ACCESS TOKEN HERE
ACCESS_TOKEN = "REDACTED_JWT_TOKEN<=="

INPUT_FILE = 'agco_complete_data.json'
USER_PREFIX = "CS"

# --- HELPERS ---
def get_headers():
    return {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }

def make_sys_id(text):
    if not text: return f"{USER_PREFIX}_UNKNOWN"
    clean = re.sub(r'[^a-zA-Z0-9]', '_', str(text).strip())
    clean = re.sub(r'_+', '_', clean).strip('_')
    return f"{USER_PREFIX}_{clean}".upper()

# --- MAIN LOGIC ---
def link_categories():
    print("--- SAP CPQ CATEGORY LINKER ---")

    # 1. READ JSON DATA
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("❌ Error: JSON file not found."); return

    # 2. FETCH EXISTING IDS (The Map)
    # We must know the Numeric ID (e.g. 2310) for every System ID (e.g. CS_MASSEY_FERGUSON)
    print("📥 Fetching current Category IDs from CPQ...")
    headers = get_headers()

    id_map = {} # { "CS_TRACTORS": 2311, ... }

    try:
        # Fetch plenty of records to ensure we get them all
        resp = requests.get(API_ENDPOINT, headers=headers, params={"$top": 2000})
        if resp.status_code == 200:
            records = resp.json().get('pagedRecords', [])
            print(f"   Found {len(records)} existing categories.")

            for r in records:
                sys_id = r.get('systemId')
                num_id = r.get('id')
                if sys_id and num_id:
                    id_map[sys_id] = num_id
        else:
            print(f"❌ Failed to fetch: {resp.status_code} - {resp.text}")
            return
    except Exception as e:
        print(f"❌ Network Error: {e}"); return

    # 3. FAST LINKING (PUT)
    print("\n⚡ Starting Fast Linking...")

    # Pre-calculate Root ID
    root_sys_id = f"{USER_PREFIX}_MASSEY_FERGUSON"
    root_num_id = id_map.get(root_sys_id)

    if not root_num_id:
        print(f"❌ CRITICAL: Root Category {root_sys_id} not found in CPQ. Run creation script first.")
        return

    success_count = 0

    for item in data:
        title = item.get('title')
        parent_name = item.get('parent')

        # Calculate System IDs
        child_sys_id = make_sys_id(title)

        if parent_name in ["ROOT", "Home"]:
            parent_sys_id = root_sys_id
        else:
            parent_sys_id = make_sys_id(parent_name)

        # Lookup Numeric IDs
        child_num_id = id_map.get(child_sys_id)
        parent_num_id = id_map.get(parent_sys_id)

        # Only proceed if both exist
        if child_num_id and parent_num_id:
            # Payload just needs ID and ParentCategory
            payload = {
                "id": child_num_id,
                "parentCategory": parent_num_id
            }

            try:
                url = f"{API_ENDPOINT}/{child_num_id}"
                resp = requests.put(url, headers=headers, json=payload)

                if resp.status_code in [200, 204]:
                    print(f"✅ Linked: {title} -> {parent_name}")
                    success_count += 1
                elif resp.status_code == 401:
                    print(f"❌ Auth Failed (401). Token Expired?")
                    break # Stop if token dies
                else:
                    print(f"⚠️ Failed {title}: {resp.status_code}")
            except Exception as e:
                print(f"❌ Error {title}: {e}")
        else:
            if not child_num_id:
                # Silent skip or log if strictly needed.
                # Usually means the category wasn't created in Phase 1
                pass

    print(f"\n--- DONE: Linked {success_count} Categories ---")

if __name__ == "__main__":
    link_categories()