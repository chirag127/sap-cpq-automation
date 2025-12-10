import requests
import json
import time
import sys

# --- CONFIGURATION ---
BASE_URL = "https://tataconsultancyservices-partner1.cpq.cloud.sap"
API_ENDPOINT = f"{BASE_URL}/api/products/v1/categories"

# PASTE YOUR ACCESS TOKEN HERE
ACCESS_TOKEN = "REDACTED_JWT_TOKEN<=="

# Filtering String (Case Insensitive)
TARGET_NAME = "chirag"

def delete_categories():
    print(f"--- SAP CPQ DELETER ---")

    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }

    # 1. FETCH ALL CATEGORIES
    print("📥 Fetching categories...")
    try:
        response = requests.get(API_ENDPOINT, headers=headers, params={"$top": 1000})

        if response.status_code != 200:
            print(f"❌ Error fetching: {response.status_code} - {response.text}")
            return

        data = response.json()

        # Use 'pagedRecords' as identified in your previous steps
        all_cats = data.get('pagedRecords', [])
        print(f"   Total Categories found: {len(all_cats)}")

    except Exception as e:
        print(f"❌ Network Error: {e}")
        return

    # 2. FILTER TARGETS
    targets = []
    print(f"\n🔍 Filtering for '{TARGET_NAME}'...")

    for cat in all_cats:
        name = str(cat.get('name', ''))
        sys_id = str(cat.get('systemId', ''))

        if TARGET_NAME.lower() in name.lower() or TARGET_NAME.lower() in sys_id.lower():
            targets.append(cat)

    if not targets:
        print(f"✅ No categories found matching '{TARGET_NAME}'.")
        return

    print(f"⚠️ Found {len(targets)} categories to DELETE.")

    # 3. DELETE LOOP
    success = 0
    fail = 0

    # Reverse order helps delete children before parents
    for i, cat in enumerate(reversed(targets)):
        cat_id = cat.get('id')
        name = cat.get('name')

        print(f"[{i+1}/{len(targets)}] Deleting '{name}' (ID: {cat_id})...", end=" ")

        try:
            # FIX: Use SLASH separator, NOT parentheses
            # Correct: /api/products/v1/categories/123
            del_url = f"{API_ENDPOINT}/{cat_id}"

            resp = requests.delete(del_url, headers=headers)

            if resp.status_code in [200, 204]:
                print("✅ Deleted")
                success += 1
            else:
                print(f"❌ Failed ({resp.status_code})")
                try: print(f"      {resp.json()['message']}")
                except: pass
                fail += 1
        except Exception as e:
            print(f"❌ Error: {e}")
            fail += 1

        time.sleep(0.5)

    print(f"\n--- DONE ---")
    print(f"Deleted: {success}")
    print(f"Failed: {fail}")

if __name__ == "__main__":
    delete_categories()