import json
import os
import re

import requests

# --- CONFIGURATION ---
BASE_URL = os.environ.get(
    "CPQ_BASE_URL", "https://tataconsultancyservices-partner1.cpq.cloud.sap"
)
API_ENDPOINT = f"{BASE_URL}/api/products/v1/categories"

ACCESS_TOKEN = os.environ.get("CPQ_ACCESS_TOKEN", "")

INPUT_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "agco_complete_data.json"
)
USER_PREFIX = os.environ.get("USER_PREFIX", "CS")


# --- HELPERS ---
def get_headers():
    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def make_sys_id(text):
    if not text:
        return f"{USER_PREFIX}_UNKNOWN"
    clean = re.sub(r"[^a-zA-Z0-9]", "_", str(text).strip())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return f"{USER_PREFIX}_{clean}".upper()


# --- 1. FETCH WITH PAGINATION ---
def fetch_all_categories(headers):
    print("📥 Fetching ALL Category IDs (Pagination Enabled)...")
    all_records = []
    skip = 0
    top = 1000  # Max allowed

    while True:
        print(f"   Requesting records {skip} to {skip + top}...", end=" ")
        try:
            params = {"$skip": skip, "$top": top}
            resp = requests.get(API_ENDPOINT, headers=headers, params=params)

            if resp.status_code == 200:
                data = resp.json()
                page = data.get("pagedRecords", [])
                all_records.extend(page)
                print(f"Got {len(page)}")

                if len(page) < top:
                    break  # Reached end
                skip += top
            else:
                print(f"❌ Failed: {resp.status_code}")
                break
        except Exception as e:
            print(f"❌ Error: {e}")
            break

    # Build Map
    id_map = {}
    for r in all_records:
        sys_id = r.get("systemId")
        num_id = r.get("id")
        if sys_id and num_id:
            id_map[sys_id] = num_id

    print(f"✅ Total Categories Mapped: {len(id_map)}")
    return id_map


# --- 2. MAIN LOGIC ---
def link_categories():
    # 1. READ JSON
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        print("❌ JSON not found")
        return

    headers = get_headers()

    # 2. GET MAP
    id_map = fetch_all_categories(headers)

    # 3. LINKING LOOP
    print("\n⚡ Starting FULL UPDATE Linking...")

    root_sys_id = f"{USER_PREFIX}_MASSEY_FERGUSON"
    success_count = 0

    for item in data:
        title = item.get("title")
        parent_name = item.get("parent")

        child_sys_id = make_sys_id(title)

        if parent_name in ["ROOT", "Home"]:
            parent_sys_id = root_sys_id
        else:
            parent_sys_id = make_sys_id(parent_name)

        child_num_id = id_map.get(child_sys_id)
        parent_num_id = id_map.get(parent_sys_id)

        # Validation
        if not child_num_id:
            continue
        if not parent_num_id:
            # Only warn if it's NOT the root itself (Root has no parent)
            if child_sys_id != root_sys_id:
                print(f"⚠️ Skip {title}: Parent {parent_sys_id} not found.")
            continue

        # --- THE FIX: GET -> MODIFY -> PUT ---
        try:
            # A. GET Current Data
            url = f"{API_ENDPOINT}/{child_num_id}"
            get_resp = requests.get(url, headers=headers)

            if get_resp.status_code != 200:
                print(f"❌ Failed to GET {title}: {get_resp.status_code}")
                continue

            current_data = get_resp.json()

            # Check if update is actually needed
            if current_data.get("parentCategory") == parent_num_id:
                # Already linked, skip to save time
                continue

            # B. MODIFY Payload
            current_data["parentCategory"] = parent_num_id

            # Remove Read-Only fields that cause 400 errors
            # (CreatedBy, ModifiedBy, Dates often cause issues if sent back)
            for key in [
                "createdDate",
                "modifiedDate",
                "createdBy",
                "modifiedBy",
                "permissions",
            ]:
                current_data.pop(key, None)

            # C. PUT Update
            print(f"Linking {title} -> {parent_name}...", end=" ")
            put_resp = requests.put(url, headers=headers, json=current_data)

            if put_resp.status_code in [200, 204]:
                print("✅")
                success_count += 1
            else:
                print(f"❌ {put_resp.status_code} - {put_resp.text}")

        except Exception as e:
            print(f"❌ Error: {e}")

    print(f"\n--- DONE: Updated {success_count} Categories ---")


if __name__ == "__main__":
    link_categories()
