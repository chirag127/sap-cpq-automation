import requests
import json
import time
import sys
import os
import csv

# --- 1. CONFIGURATION (Hardcoded for Assignment) ---
CPQ_BASE_URL = "https://tataconsultancyservices-partner1.cpq.cloud.sap"
TOKEN_URL = f"{CPQ_BASE_URL}/basic/api/token"

# CORRECT REST API ENDPOINTS (v1)
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

# PRICING DATA (To be written to CSV)
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

# ATTRIBUTE DEFINITIONS
ATTRIBUTES = [
    {
        "name": f"Size_{EMP_ID}",
        "type": "UserSelection",
        "values": ["Small", "Medium", "Large"]
    },
    {
        "name": f"Crust Type_{EMP_ID}",
        "type": "UserSelection",
        "values": ["Thin Crust", "Deep Dish"]
    },
    {
        "name": f"Specialty_{EMP_ID}",
        "type": "UserSelection",
        "values": ["Custom Pizza", "Meat Lovers", "The Works"]
    },
    {
        "name": f"Toppings_{EMP_ID}",
        "type": "UserSelection",
        "values": ["Sausage", "Pepperoni", "Green Peppers", "Onion", "Mushrooms", "Anchovy"]
    },
    {
        "name": f"Include Desserts_{EMP_ID}",
        "type": "Boolean",
        "values": []
    },
    # Container Attributes
    {
        "name": f"Number of Desserts_{EMP_ID}",
        "type": "Integer",
        "values": []
    },
    {
        "name": f"Dessert Type_{EMP_ID}",
        "type": "UserSelection",
        "values": ["Ice Cream Cone", "Hot Fudge Sundae", "Milkshake", "Yogurt Parfait", "Chai Tea Latte"]
    },
    {
        "name": f"Dessert Size_{EMP_ID}",
        "type": "UserSelection",
        "values": ["Small", "Medium", "Large"]
    }
]

# --- 2. AUTHENTICATION ---
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
        resp = requests.post(TOKEN_URL, data=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.json()['access_token']
        print(f"❌ Auth Failed: {resp.text}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        sys.exit(1)

# --- 3. HELPER FUNCTIONS ---
def generate_system_id(name):
    # Create a safe System ID: CS_2800815_NAME
    clean_name = name.replace(" ", "_").replace("-", "_").upper()
    # Limit length if necessary, but keep unique
    return f"CS_{clean_name}"[:50]

def api_get(url, token, params=None):
    headers = {'Authorization': f'Bearer {token}'}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        return r
    except Exception as e:
        print(f"   ⚠️ Network Error (GET): {e}")
        return None

def api_post(url, token, payload):
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        return r
    except Exception as e:
        print(f"   ⚠️ Network Error (POST): {e}")
        return None

def find_id_by_name(url, token, name, key="Name"):
    # Searches for an item and returns its ID if found
    r = api_get(url, token)
    if r and r.status_code == 200:
        data = r.json()
        # Handle list in 'Items' or direct list
        items = data.get('Items', []) if isinstance(data, dict) else data
        for item in items:
            if item.get(key) == name:
                return item.get('Id')
    return None

# --- 4. MAIN WORKFLOW ---
def run_automation():
    token = get_token()

    print("\n--- 🍕 STARTING AMO LA PIZZA SETUP ---")

    # 1. CATEGORIES
    print("\n[1/5] Setting up Categories...")

    # Root Category
    root_id = find_id_by_name(API_CAT, token, ROOT_CAT_NAME)
    if not root_id:
        payload = {
            "SystemId": generate_system_id(ROOT_CAT_NAME),
            "Name": ROOT_CAT_NAME,
            "Active": True
        }
        r = api_post(API_CAT, token, payload)
        if r and r.status_code in [200, 201]:
            root_id = r.json()['Id']
            print(f"   ✅ Created Root Category: {ROOT_CAT_NAME}")
        else:
            print(f"   ❌ Failed Root Category: {r.text if r else 'Error'}")
            sys.exit(1)
    else:
        print(f"   ✅ Root Category Exists: {ROOT_CAT_NAME}")

    # Sub Category
    sub_id = find_id_by_name(API_CAT, token, SUB_CAT_NAME)
    if not sub_id:
        payload = {
            "SystemId": generate_system_id(SUB_CAT_NAME),
            "Name": SUB_CAT_NAME,
            "ParentId": root_id, # Linking to Parent
            "Active": True
        }
        r = api_post(API_CAT, token, payload)
        if r and r.status_code in [200, 201]:
            sub_id = r.json()['Id']
            print(f"   ✅ Created Sub Category: {SUB_CAT_NAME}")
        else:
            print(f"   ❌ Failed Sub Category: {r.text if r else 'Error'}")
    else:
        print(f"   ✅ Sub Category Exists: {SUB_CAT_NAME}")

    # 2. PRODUCT
    print("\n[2/5] Setting up Product...")
    prod_id = None
    # Check by SystemID first as it's more unique
    search_sys = api_get(f"{API_PROD}?$filter=SystemId eq '{PROD_SYS_ID}'", token)
    if search_sys and search_sys.status_code == 200 and search_sys.json().get('Items'):
         prod_id = search_sys.json()['Items'][0]['Id']
         print(f"   ✅ Product Exists: {PROD_NAME}")

    if not prod_id:
        payload = {
            "SystemId": PROD_SYS_ID,
            "Name": PROD_NAME,
            "CategoryId": sub_id,
            "ProductType": "Accessories", # Trying Accessories first, fallback to Simple if needed
            "BasePrice": 0,
            "Active": True,
            "DisplayType": "Configuration"
        }
        r = api_post(API_PROD, token, payload)
        if r and r.status_code in [200, 201]:
            prod_id = r.json()['Id']
            print(f"   ✅ Created Product: {PROD_NAME}")
        else:
            print(f"   ❌ Failed to Create Product: {r.text if r else 'Error'}")
            # Fallback for some environments that don't like 'Accessories'
            if r and "ProductType" in r.text:
                print("   ⚠️ Retrying as 'Simple' product type...")
                payload['ProductType'] = "Simple"
                r = api_post(API_PROD, token, payload)
                if r and r.status_code in [200, 201]:
                    prod_id = r.json()['Id']
                    print(f"   ✅ Created Product (Simple): {PROD_NAME}")

    # 3. ATTRIBUTES
    print("\n[3/5] Setting up Attributes & Menus...")

    for attr in ATTRIBUTES:
        attr_name = attr['name']
        attr_sys_id = generate_system_id(attr_name)
        attr_id = None

        # Check existence
        search = api_get(f"{API_ATTR}?$filter=Name eq '{attr_name}'", token)
        if search and search.status_code == 200 and search.json().get('Items'):
            attr_id = search.json()['Items'][0]['Id']
            print(f"   🔹 Found Attribute: {attr_name}")
        else:
            # Create Attribute
            payload = {
                "SystemId": attr_sys_id,
                "Name": attr_name,
                "AttributeType": attr['type'],
                "Active": True
            }
            r = api_post(API_ATTR, token, payload)
            if r and r.status_code in [200, 201]:
                attr_id = r.json()['Id']
                print(f"   ✅ Created Attribute: {attr_name}")
            else:
                print(f"   ❌ Failed Attribute {attr_name}: {r.text if r else 'Error'}")
                continue

        # Add Menu Values (For UserSelection)
        if attr['type'] == "UserSelection" and attr['values'] and attr_id:
            val_url = f"{API_ATTR}/{attr_id}/values"
            # Get existing to avoid duplicates
            existing = api_get(val_url, token).json()
            existing_codes = [x['ValueCode'] for x in existing]

            for val in attr['values']:
                if val not in existing_codes:
                    val_payload = {"ValueCode": val, "Display": val}
                    # We post values individually
                    api_post(val_url, token, val_payload)
            print(f"      Use selections synced.")

        # 4. LINK ATTRIBUTE TO PRODUCT
        # Endpoint: /api/products/v1/products/{prod_id}/attributes
        if prod_id and attr_id:
            link_url = f"{API_PROD}/{prod_id}/attributes"

            # Check if linked? (Hard to check efficiently, so we try-catch the create)
            link_payload = {
                "AttributeId": attr_id,
                "Rank": 10
            }
            # Many CPQs return 400 if already linked, which is fine
            r_link = api_post(link_url, token, link_payload)
            if r_link and r_link.status_code in [200, 201]:
                 print(f"      🔗 Linked to Product")
            elif r_link and "already assigned" in r_link.text:
                 print(f"      🔗 Already Linked")

    # 5. GENERATE CSV
    print("\n[5/5] Generating Pricing CSV...")
    filename = f"pricing_upload_{EMP_ID}.csv"
    try:
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(PRICING_ROWS)
        print(f"   📄 Successfully generated: {filename}")
        print(f"   👉 Path: {os.path.abspath(filename)}")
    except Exception as e:
        print(f"   ❌ CSV Gen Failed: {e}")

    print("\n--- 🎉 AUTOMATION DONE ---")
    print("NEXT STEPS:")
    print("1. Go to CPQ Setup > Pricing/Calculations > Custom Tables.")
    print(f"2. Create table 'Amo Pricing {EMP_ID}'.")
    print(f"3. Import the file '{filename}' generated above.")
    print("4. Manually add the Rules (Practice 8-5) in the 'Rules' tab of the product.")

if __name__ == "__main__":
    run_automation()