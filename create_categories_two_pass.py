import requests
import json
import time
import re
import sys

# --- CONFIGURATION ---
BASE_URL = "https://tataconsultancyservices-partner1.cpq.cloud.sap"
API_ENDPOINT = f"{BASE_URL}/api/products/v1/categories"

# PASTE ACCESS TOKEN HERE
ACCESS_TOKEN = "REDACTED_JWT_TOKEN<=="

INPUT_FILE = 'agco_complete_data.json'
USER_PREFIX = "CS"
USER_NAME_SUFFIX = "Chirag Singhal"

# --- HELPERS ---
def get_headers():
    return {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

def make_sys_id(text):
    if not text: return f"{USER_PREFIX}_UNKNOWN"
    clean = re.sub(r'[^a-zA-Z0-9]', '_', str(text).strip())
    clean = re.sub(r'_+', '_', clean).strip('_')
    return f"{USER_PREFIX}_{clean}".upper()

def make_display_name(text):
    return f"{str(text).strip()} - {USER_NAME_SUFFIX}"

# --- MAIN LOGIC ---
def process_categories():
    print("--- SAP CPQ 2-PHASE CATEGORY CREATOR ---")

    # 1. READ DATA
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("❌ JSON file not found."); return

    headers = get_headers()

    # MEMORY: Maps Title -> Real CPQ Integer ID
    id_map = {}

    # --- PHASE 1: CREATE (POST) ---
    print("\n🔹 PHASE 1: Creating Categories & Tracking IDs...")

    # Add Root Manually First
    root_sys_id = f"{USER_PREFIX}_MASSEY_FERGUSON"
    root_payload = {
        "systemId": root_sys_id,
        "name": f"Massey Ferguson - {USER_NAME_SUFFIX}",
        "active": True,
        "visibleToEveryone": True,
        "displayType": "Category"
    }

    print(f"Creating Root: {root_sys_id}...", end=" ")
    try:
        resp = requests.post(API_ENDPOINT, headers=headers, json=root_payload)
        if resp.status_code in [200, 201]:
            new_id = resp.json()['id'] # Capture the auto-generated ID
            id_map["ROOT"] = new_id
            id_map["Home"] = new_id
            print(f"✅ Created (ID: {new_id})")
        else:
            print(f"❌ Failed: {resp.text}")
            # If exists, we must find its ID or script fails.
            # In a real script we would search for it here.
            return
    except Exception as e:
        print(f"❌ Error: {e}"); return

    # Create All Others
    for item in data:
        title = item.get('title')
        sys_id = make_sys_id(title)

        payload = {
            "systemId": sys_id,
            "name": make_display_name(title),
            "description": item.get('description', '')[:255],
            "active": True,
            "visibleToEveryone": True
        }

        print(f"Creating: {sys_id}...", end=" ")
        try:
            resp = requests.post(API_ENDPOINT, headers=headers, json=payload)
            if resp.status_code in [200, 201]:
                new_id = resp.json()['id'] # <--- CRITICAL STEP: SAVE ID
                id_map[title] = new_id
                print(f"✅ ID: {new_id}")
            else:
                print(f"⚠️ Failed ({resp.status_code})")
        except:
            print("❌ Error")


    print(f"\n✅ Phase 1 Complete. Tracked {len(id_map)} IDs.")

    # --- PHASE 2: LINK (PUT) ---
    print("\n🔹 PHASE 2: Linking Parents (PUT)...")

    for item in data:
        title = item.get('title')
        parent_name = item.get('parent')

        # We need the Integer ID of the Child AND the Parent
        child_id = id_map.get(title)
        parent_id = id_map.get(parent_name)

        if child_id and parent_id:
            print(f"Linking {title} ({child_id}) -> Parent ({parent_id})...", end=" ")

            update_payload = {
                "id": child_id,
                "parentCategory": parent_id # This requires the Integer ID
            }

            try:
                # PUT /api/products/v1/categories/{id}
                put_url = f"{API_ENDPOINT}/{child_id}"
                resp = requests.put(put_url, headers=headers, json=update_payload)

                if resp.status_code in [200, 204]:
                    print("✅ Linked")
                else:
                    print(f"❌ Failed: {resp.text}")
            except: print("❌ Error")

        else:
            if not child_id: print(f"⚠️ Skipping {title} (ID not found)")
            elif not parent_id: print(f"⚠️ Skipping {title} (Parent '{parent_name}' ID not found)")

    print("\n🎉 DONE.")

if __name__ == "__main__":
    process_categories()