import requests
import json
import time
import re
import sys

# --- CONFIGURATION ---
BASE_URL = "https://tataconsultancyservices-partner1.cpq.cloud.sap"
API_ENDPOINT = f"{BASE_URL}/api/product/v1/categories"

# PASTE YOUR ACCESS TOKEN HERE
ACCESS_TOKEN = "REDACTED_JWT_TOKEN<=="

INPUT_FILE = 'agco_complete_data.json'

# NAMING CONVENTION
USER_PREFIX = "CS"
USER_NAME_SUFFIX = "Chirag Singhal"

# --- HELPER FUNCTIONS ---
def get_headers():
    return {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

def make_sys_id(text):
    """Generates unique SystemId: 'Tractors' -> 'CS_TRACTORS'"""
    if not text: return f"{USER_PREFIX}_UNKNOWN"
    clean = re.sub(r'[^a-zA-Z0-9]', '_', str(text).strip())
    clean = re.sub(r'_+', '_', clean).strip('_')
    return f"{USER_PREFIX}_{clean}".upper()

def make_display_name(text):
    """Generates Name: 'Tractors - Chirag Singhal'"""
    return f"{str(text).strip()} - {USER_NAME_SUFFIX}"

# --- MAIN LOGIC ---
def create_categories():
    print("--- SAP CPQ HIERARCHICAL CATEGORY CREATOR ---")

    # 1. LOAD DATA
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {INPUT_FILE} not found.")
        return

    # 2. ORGANIZE BY DEPTH (Root -> Level 1 -> Level 2)
    # This ensures we create parents before children
    levels = {}
    for item in data:
        depth = item.get('depth', 0)
        if depth not in levels:
            levels[depth] = []
        levels[depth].append(item)

    # 3. CREATE ROOT PARENT (Massey Ferguson)
    # We need a top-level folder to hold everything so it doesn't get lost
    root_sys_id = f"{USER_PREFIX}_MASSEY_FERGUSON"
    root_name = f"Massey Ferguson - {USER_NAME_SUFFIX}"

    print(f"Creating Root Category: {root_sys_id}...")
    root_payload = {
        "SystemId": root_sys_id,
        "Name": root_name,
        "Active": True,
        "DisplayType": "Category"
    }

    # Check/Create Root
    headers = get_headers()
    resp = requests.post(API_ENDPOINT, headers=headers, json=root_payload)
    if resp.status_code in [200, 201, 409]:
        print("✅ Root Ready.")
    else:
        print(f"❌ Failed to create Root: {resp.text}")
        return

    # 4. ITERATE LEVELS
    # Dictionary to map 'Title' -> 'SystemId' for parent lookups
    # Initialize with our manual Root
    id_map = { "ROOT": root_sys_id, "Home": root_sys_id }

    # Get sorted depth keys (0, 1, 2, 3...)
    sorted_depths = sorted(levels.keys())

    for depth in sorted_depths:
        print(f"\n--- Processing Level {depth} ---")
        items = levels[depth]

        for item in items:
            title = item.get('title')
            parent_title = item.get('parent')
            desc = item.get('description', '')

            # Generate IDs
            sys_id = make_sys_id(title)
            name = make_display_name(title)

            # Find Parent System ID
            # We look up the parent's title in our map to get its System ID
            parent_sys_id = id_map.get(parent_title)

            if not parent_sys_id:
                print(f"⚠️ Warning: Parent '{parent_title}' not found for '{title}'. Skipping.")
                continue

            # Store mapping for future children
            id_map[title] = sys_id

            # Prepare Payload
            payload = {
                "systemId": sys_id,
                "parentCategory": parent_sys_id, # Crucial Link
                "name": name,
                "description": desc[:255] if desc else "",
                "active": True,
                "displayType": "Category"
            }

            print(f"Creating: {sys_id} (Parent: {parent_sys_id})...", end=" ")

            try:
                # API Call
                response = requests.post(API_ENDPOINT, headers=headers, json=payload)

                if response.status_code in [200, 201]:
                    print("✅ Created")
                elif response.status_code == 409:
                    print("✅ Exists (Skipping)")
                else:
                    # Try to extract error message
                    try: err_msg = response.json()['message']
                    except: err_msg = response.text[:50]
                    print(f"❌ Failed: {err_msg}")

            except Exception as e:
                print(f"❌ Network Error: {e}")

            # Rate Limiting
            time.sleep(0.5)

    print("\n--- JOB COMPLETE ---")

if __name__ == "__main__":
    create_categories()