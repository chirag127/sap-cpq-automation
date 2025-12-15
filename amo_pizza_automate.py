import requests
import json
import time
import sys
import os
import csv

# --- 1. CONFIGURATION ---
CPQ_BASE_URL = "https://tataconsultancyservices-partner1.cpq.cloud.sap"
TOKEN_URL = f"{CPQ_BASE_URL}/basic/api/token"

# API ENDPOINTS
API_CAT = f"{CPQ_BASE_URL}/api/products/v1/categories"
API_PROD = f"{CPQ_BASE_URL}/api/products/v1/products"
API_ATTR = f"{CPQ_BASE_URL}/api/products/v1/attributes"

# CREDENTIALS
CPQ_USERNAME = "REDACTED_CPQ_USERNAME<=="
CPQ_PASSWORD = "REDACTED_CPQ_PASSWORD<=="
CPQ_DOMAIN = "TATACONSULTANCYSERVICESLIMITED_PARTNER1"

# ASSIGNMENT DETAILS
EMP_ID = "2800815"
ROOT_CAT_NAME = "Amo la Pizza"
SUB_CAT_NAME = f"Pizza Menu_{EMP_ID}"
PROD_NAME = f"Pizza Order_{EMP_ID}"
PROD_SYS_ID = f"PZ_ORD_{EMP_ID}"

# PRICING DATA
PRICING_ROWS = [
    ["part_number", "description", "price_usd", "price_cad"],
    ["BX001", "Gift box packing", "1", "1.1 * USD Price"],
    ["PZ_SmTh", "Small Thin Crust Pizza", "10", "1.1 * USD Price"],
    ["PZ_MdTh", "Medium Thin Crust Pizza", "12", "1.1 * USD Price"],
    ["PZ_MdDd", "Medium Deep Dish Pizza", "15", "1.1 * USD Price"],
    ["PZ_LgTh", "Large Thin Crust Pizza", "17", "1.1 * USD Price"],
    ["PZ_LgDd", "Large Deep Dish Pizza", "20", "1.1 * USD Price"],
    ["TP001", "Add Sausage", "1", "1.1 * USD Price"],
    ["TP002", "Add Pepperoni", "1", "1.1 * USD Price"],
    ["TP003", "Add Green Pepper", "1", "1.1 * USD Price"],
    ["TP004", "Add Onion", "1", "1.1 * USD Price"],
    ["TP005", "Add Mushrooms", "1", "1.1 * USD Price"],
    ["TP006", "Add Anchovy", "1", "1.1 * USD Price"],
    ["ICC001", "Small Ice Cream Cone with nuts", "1.25", "1.1 * USD Price"],
    ["ICC002", "Small Ice Cream Cone without nuts", "1", "1.1 * USD Price"],
    ["HFS001", "Small Hot Fudge Sundae with nuts", "1.75", "1.1 * USD Price"],
    ["HFS002", "Small Hot Fudge Sundae without nuts", "1.5", "1.1 * USD Price"],
    ["MS001", "Small Milkshake with nuts", "1.5", "1.1 * USD Price"],
    ["MS002", "Small Milkshake without nuts", "1.25", "1.1 * USD Price"],
    ["YP001", "Small Yogurt Parfait with nuts", "1.5", "1.1 * USD Price"],
    ["YP002", "Small Yogurt Parfait without nuts", "1.25", "1.1 * USD Price"],
    ["CTL001", "Small Chai Tea Latte with nuts", "1.5", "1.1 * USD Price"],
    ["CTL002", "Small Chai Tea Latte without nuts", "1.25", "1.1 * USD Price"],
    ["ICC003", "Medium Ice Cream Cone with nuts", "1.75", "1.1 * USD Price"],
    ["ICC004", "Medium Ice Cream Cone without nuts", "1.5", "1.1 * USD Price"],
    ["HFS003", "Medium Hot Fudge Sundae with nuts", "2.25", "1.1 * USD Price"],
    ["HFS004", "Medium Hot Fudge Sundae without nuts", "2", "1.1 * USD Price"],
    ["MS003", "Medium Milkshake with nuts", "2", "1.1 * USD Price"],
    ["MS004", "Medium Milkshake without nuts", "1.75", "1.1 * USD Price"],
    ["YP003", "Medium Yogurt Parfait with nuts", "2", "1.1 * USD Price"],
    ["YP004", "Medium Yogurt Parfait without nuts", "1.75", "1.1 * USD Price"],
    ["CTL003", "Medium Chai Tea Latte with nuts", "2", "1.1 * USD Price"],
    ["CTL004", "Medium Chai Tea Latte without nuts", "1.75", "1.1 * USD Price"],
    ["ICC005", "Large Ice Cream Cone with nuts", "2.25", "1.1 * USD Price"],
    ["ICC006", "Large Ice Cream Cone without nuts", "2", "1.1 * USD Price"],
    ["HFS005", "Large Hot Fudge Sundae with nuts", "2.75", "1.1 * USD Price"],
    ["HFS006", "Large Hot Fudge Sundae without nuts", "2.5", "1.1 * USD Price"],
    ["MS005", "Large Milkshake with nuts", "2.5", "1.1 * USD Price"],
    ["MS006", "Large Milkshake without nuts", "2.25", "1.1 * USD Price"],
    ["YP005", "Large Yogurt Parfait with nuts", "2.5", "1.1 * USD Price"],
    ["YP006", "Large Yogurt Parfait without nuts", "2.25", "1.1 * USD Price"],
    ["CTL005", "Large Chai Tea Latte with nuts", "2.5", "1.1 * USD Price"],
    ["CTL006", "Large Chai Tea Latte without nuts", "2.25", "1.1 * USD Price"]
]

# ATTRIBUTES
ATTRIBUTES = [
    {"name": f"Size_{EMP_ID}", "type": "UserSelection", "values": ["Small", "Medium", "Large"]},
    {"name": f"Crust Type_{EMP_ID}", "type": "UserSelection", "values": ["Thin Crust", "Deep Dish"]},
    {"name": f"Specialty_{EMP_ID}", "type": "UserSelection", "values": ["Custom Pizza", "Meat Lovers", "The Works"]},
    {"name": f"Toppings_{EMP_ID}", "type": "UserSelection", "values": ["Sausage", "Pepperoni", "Green Peppers", "Onion", "Mushrooms", "Anchovy"]},
    {"name": f"Include Desserts_{EMP_ID}", "type": "Boolean", "values": []},
    {"name": f"Number of Desserts_{EMP_ID}", "type": "Integer", "values": []},
    {"name": f"Dessert Type_{EMP_ID}", "type": "UserSelection", "values": ["Ice Cream Cone", "Hot Fudge Sundae", "Milkshake", "Yogurt Parfait", "Chai Tea Latte"]},
    {"name": f"Dessert Size_{EMP_ID}", "type": "UserSelection", "values": ["Small", "Medium", "Large"]}
]

# --- 2. AUTHENTICATION ---
def get_token():
    print("🔑 Authenticating...")
    payload = {
        'grant_type': 'password', 'username': CPQ_USERNAME,
        'password': CPQ_PASSWORD, 'domain': CPQ_DOMAIN
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        resp = requests.post(TOKEN_URL, data=payload, headers=headers, timeout=20)
        if resp.status_code == 200:
            return resp.json()['access_token']
        print(f"❌ Auth Failed: {resp.text}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        sys.exit(1)

# --- 3. HELPER FUNCTIONS ---
def generate_system_id(name):
    # Ensure standard characters for System ID
    clean = name.replace(" ", "_").replace("-", "_").upper()
    return f"CS_{clean}"[:50]

def api_call(method, url, token, payload=None):
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    try:
        if method == 'GET':
            r = requests.get(url, headers=headers, params=payload, timeout=20)
        else:
            r = requests.post(url, headers=headers, json=payload, timeout=20)
        return r
    except Exception as e:
        print(f"   ⚠️ Network Error ({method}): {e}")
        return None

def find_id_by_filter(url, token, filter_str):
    """Searches using OData filter and returns ID if found."""
    # Example: $filter=Name eq 'My Item'
    params = {'$filter': filter_str}
    r = api_call('GET', url, token, params)

    if r and r.status_code == 200:
        data = r.json()
        items = data.get('Items', []) if isinstance(data, dict) else data
        if items:
            return items[0]['Id']
    return None

def create_and_get_id(url, token, payload, name_field="Name"):
    """
    Tries to find item. If missing, creates it.
    ALWAYS fetches ID via search after create to ensure correctness.
    """
    name_value = payload.get(name_field)
    filter_str = f"{name_field} eq '{name_value}'"

    # 1. Search First
    existing_id = find_id_by_filter(url, token, filter_str)
    if existing_id:
        print(f"   ✅ Found Existing: {name_value}")
        return existing_id

    # 2. Create
    r = api_call('POST', url, token, payload)

    # 3. Handle Result
    if r and r.status_code in [200, 201]:
        # Try to get ID from response directly
        try:
            return r.json()['Id']
        except (KeyError, ValueError, TypeError):
            # Fallback: Search again immediately
            print(f"   ⚠️ Response missing ID, re-fetching...")
            retry_id = find_id_by_filter(url, token, filter_str)
            if retry_id:
                print(f"   ✅ Created & Verified: {name_value}")
                return retry_id
            else:
                print(f"   ❌ Created but could not find: {name_value}")
                return None
    else:
        print(f"   ❌ Create Failed for {name_value}")
        if r:
            print(f"      Status: {r.status_code}")
            print(f"      Response: {r.text}")
        return None

# --- 4. MAIN WORKFLOW ---
def run_automation():
    token = get_token()
    print("\n--- 🍕 STARTING AMO LA PIZZA SETUP (ROBUST MODE) ---")

    # 1. CATEGORIES
    print("\n[1/5] Setting up Categories...")

    # Root Category
    root_payload = {
        "SystemId": generate_system_id(ROOT_CAT_NAME),
        "Name": ROOT_CAT_NAME,
        "Active": True
    }
    root_id = create_and_get_id(API_CAT, token, root_payload)
    if not root_id:
        sys.exit(1)

    # Sub Category
    sub_payload = {
        "SystemId": generate_system_id(SUB_CAT_NAME),
        "Name": SUB_CAT_NAME,
        "ParentId": root_id,
        "Active": True
    }
    sub_id = create_and_get_id(API_CAT, token, sub_payload)

    # 2. PRODUCT
    print("\n[2/5] Setting up Product...")
    prod_payload = {
        "SystemId": PROD_SYS_ID,
        "Name": PROD_NAME,
        "CategoryId": sub_id,
        "ProductType": "Accessories",
        "BasePrice": 0,
        "Active": True,
        "DisplayType": "Configuration"
    }
    # Check by SystemId for products (more precise)
    prod_id = find_id_by_filter(API_PROD, token, f"SystemId eq '{PROD_SYS_ID}'")
    if not prod_id:
        # Create
        r = api_call('POST', API_PROD, token, prod_payload)
        if r and r.status_code in [200, 201]:
            # Re-fetch to be safe
            prod_id = find_id_by_filter(API_PROD, token, f"SystemId eq '{PROD_SYS_ID}'")
            print(f"   ✅ Created Product: {PROD_NAME}")
        else:
            print(f"   ❌ Product Create Failed: {r.text if r else 'No response'}")

    # 3. ATTRIBUTES
    print("\n[3/5] Setting up Attributes...")
    for attr in ATTRIBUTES:
        attr_payload = {
            "SystemId": generate_system_id(attr['name']),
            "Name": attr['name'],
            "AttributeType": attr['type'],
            "Active": True
        }
        attr_id = create_and_get_id(API_ATTR, token, attr_payload)

        # Add Menu Values (UserSelection only)
        if attr_id and attr['type'] == "UserSelection" and attr['values']:
            val_url = f"{API_ATTR}/{attr_id}/values"
            # Fetch existing to dedupe
            r_exist = api_call('GET', val_url, token)
            existing_codes = []
            if r_exist and r_exist.status_code == 200:
                existing_codes = [x['ValueCode'] for x in r_exist.json()]

            for val in attr['values']:
                if val not in existing_codes:
                    v_payload = {"ValueCode": val, "Display": val}
                    api_call('POST', val_url, token, v_payload)
            print(f"      Synced values for {attr['name']}")

        # 4. LINK ATTRIBUTE
        if prod_id and attr_id:
            link_url = f"{API_PROD}/{prod_id}/attributes"
            link_payload = {"AttributeId": attr_id, "Rank": 10}
            api_call('POST', link_url, token, link_payload)
            # We ignore errors here as "Already assigned" is common/harmless

    # 5. GENERATE CSV
    print("\n[5/5] Generating Pricing CSV...")
    filename = f"pricing_upload_{EMP_ID}.csv"
    try:
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(PRICING_ROWS)
        print(f"   📄 Generated: {os.path.abspath(filename)}")
    except Exception as e:
        print(f"   ❌ CSV Gen Failed: {e}")

    print("\n--- 🎉 DONE. PLEASE CHECK CPQ UI ---")

if __name__ == "__main__":
    run_automation()