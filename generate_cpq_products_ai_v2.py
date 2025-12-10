import json
import time
import requests
from google import genai
import sys
import re
import os

# --- 1. CONFIGURATION ---
# SAP CPQ Settings
CPQ_BASE_URL = "https://tataconsultancyservices-partner1.cpq.cloud.sap"
CPQ_TOKEN_URL = f"{CPQ_BASE_URL}/basic/api/token"
# CONFIRMED: Plural 'products' is the correct v1 endpoint for this tenant
CPQ_PRODUCT_API = f"{CPQ_BASE_URL}/api/products/v1/products"
CPQ_ATTR_API = f"{CPQ_BASE_URL}/api/products/v1/attributes"
# CPQ Credentials (for generating fresh token)
CPQ_USERNAME = "REDACTED_CPQ_USERNAME<=="  # Username only
CPQ_DOMAIN = "TATACONSULTANCYSERVICESLIMITED_PARTNER1"
CPQ_PASSWORD = "REDACTED_CPQ_PASSWORD<=="  # Paste the long string from Setup > Users


# Google Gemini Settings
# Using the NEW SDK and Model 2.5
GEMINI_API_KEY = "AIzaSyBRgzwZ86bV4-n5OomJDN0RQ64nMylJZB8"
GEMINI_MODEL = "gemini-2.5-flash-lite-preview-09-2025"

# --- 1. CONFIGURATION ---
INPUT_JSON_FILE = 'agco_complete_data.json' # Your scraped data file

# Root Category ID (Must match what you uploaded earlier)
ROOT_CAT_ID = "CS_MASSEY_FERGUSON"

# --- 2. HELPERS ---
def make_sys_id(text):
    """Generates exact System ID to match Categories"""
    if not text or text.upper() in ["ROOT", "HOME"]: return "CS_MASSEY_FERGUSON"
    clean = re.sub(r'[^a-zA-Z0-9]', '_', str(text).strip())
    clean = re.sub(r'_+', '_', clean).strip('_')
    return f"CS_{clean}".upper()[:50] # CPQ limit 50 chars usually

def get_headers():
    url = f"{CPQ_BASE_URL}/basic/api/token"
    payload = {
        'grant_type': 'password',
        'username': CPQ_USERNAME,
        'password': CPQ_PASSWORD,
        'domain': CPQ_DOMAIN
    }
    try:
        resp = requests.post(url, data=payload)
        if resp.status_code != 200:
            print(f"❌ Auth Failed: {resp.text}")
            sys.exit(1)
        return {
            'Authorization': f"Bearer {resp.json()['access_token']}",
            'Content-Type': 'application/json'
        }
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        sys.exit(1)

# --- 3. INTELLIGENCE ENGINE (DATA ONLY) ---
def analyze_product_with_ai(product_name, description):
    print(f"   🧠 Analyzing '{product_name}'...", end=" ")

    client = genai.Client(api_key=GEMINI_API_KEY)

    # We ask AI for DATA, not CPQ JSON structure. Safer.
    prompt = f"""
    Product: "{product_name}"
    Description: "{description}"

    Extract/Estimate the following technical data.
    1. Base Price (Integer USD, e.g. 45000)
    2. Three technical attributes specific to this machine type (e.g. Engine Power, Transmission, Hydraulics).
       For each attribute, provide 2-3 realistic options (Value Code, Display Name, Price Adder).

    Output PURE JSON:
    {{
        "price": 55000,
        "attributes": [
            {{
                "name": "Transmission",
                "values": [
                    {{"code": "STD", "display": "Standard 12x12", "price": 0}},
                    {{"code": "PRO", "display": "Dyna-4", "price": 2500}}
                ]
            }}
        ]
    }}
    """

    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            print("✅ Done")
            return json.loads(json_match.group(0))
        raise ValueError("No JSON")
    except Exception as e:
        print(f"⚠️ AI Error. Using Default.")
        return {
            "price": 50000,
            "attributes": [
                {"name": "Configuration", "values": [{"code": "STD", "display": "Standard", "price": 0}]}
            ]
        }

# --- 4. CPQ LOADER (STRICT SCHEMA) ---
def process_product(prod_raw, headers, prod_api, attr_api):
    # Prepare IDs
    prod_name = prod_raw.get('title')
    sys_id = make_sys_id(prod_name)
    cat_sys_id = make_sys_id(prod_raw.get('parent', 'Root'))

    # Get AI Data
    ai_data = analyze_product_with_ai(prod_name, prod_raw.get('description', ''))

    # --- STEP A: CREATE ATTRIBUTES ---
    created_attr_ids = []
    print(f"   ⚙️ Attributes...", end=" ")

    for attr in ai_data['attributes']:
        attr_sys_id = f"CS_ATTR_{make_sys_id(attr['name'])[3:]}_{sys_id[6:10]}" # Unique ID

        attr_payload = {
            "SystemId": attr_sys_id,
            "Name": attr['name'],
            "DisplayType": "DropDown", # Standard
            "Active": True,
            "Values": [
                {
                    "ValueCode": v['code'],
                    "Display": v['display'],
                    "Price": v['price']
                } for v in attr['values']
            ]
        }

        # Fire & Forget Attribute Creation
        try:
            requests.post(attr_api, headers=headers, json=attr_payload)
            created_attr_ids.append(attr_sys_id)
        except: pass
    print(f"Synced {len(created_attr_ids)}.")

    # --- STEP B: CREATE PRODUCT (CLEAN PAYLOAD) ---
    print(f"   🚀 Upserting Product...", end=" ")

    product_payload = {
        "SystemId": sys_id,
        "CategorySystemId": cat_sys_id,
        "PartNumber": sys_id,
        "Name": f"Chirag Singhal - {prod_name}",
        "ProductType": "Configurable",
        "DisplayType": "Configuration",
        "Active": True,
        "BasePrice": ai_data['price'],
        "Description": prod_raw.get('description', '')[:255]
    }

    # Check existence
    check = requests.get(f"{prod_api}({sys_id})", headers=headers)

    if check.status_code == 200:
        # Update
        resp = requests.put(f"{prod_api}({sys_id})", headers=headers, json=product_payload)
        action = "Updated"
    else:
        # Create
        resp = requests.post(prod_api, headers=headers, json=product_payload)
        action = "Created"

    if resp.status_code in [200, 201]:
        print(f"✅ {action}")

        # --- STEP C: LINK ATTRIBUTES ---
        # Only link if product exists
        for attr_id in created_attr_ids:
            link_payload = {
                "SystemId": attr_id,
                "Required": False,
                "DisplayAs": "DropDown",
                "Rank": 10
            }
            try:
                requests.post(f"{prod_api}({sys_id})/attributes", headers=headers, json=link_payload)
            except: pass
    else:
        print(f"❌ Failed ({resp.status_code})")
        print(f"      Err: {resp.text[:300]}") # Show detailed error

# --- MAIN ---
if __name__ == "__main__":
    print(f"📂 Reading {INPUT_JSON_FILE}...")
    try:
        with open(INPUT_JSON_FILE, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except:
        print("❌ File not found."); sys.exit()

    products = [i for i in raw_data if i.get('isLeaf') or i.get('depth', 0) >= 3]
    print(f"🎯 Found {len(products)} products.")

    headers = get_headers()
    # Hardcoded known endpoints for your tenant
    PROD_API = f"{CPQ_BASE_URL}/api/product/v1/products"
    ATTR_API = f"{CPQ_BASE_URL}/api/product/v1/attributes"

    for i, prod in enumerate(products):
        print(f"\n[{i+1}/{len(products)}] {prod.get('title')}")
        if i > 0 and i % 10 == 0: headers = get_headers()

        process_product(prod, headers, PROD_API, ATTR_API)
        time.sleep(1)