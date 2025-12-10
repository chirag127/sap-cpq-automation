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

# --- HELPER: SYSTEM ID GENERATOR ---
def make_sys_id(text):
    """Matches the logic used in Category Creation"""
    if not text or text.upper() in ["ROOT", "HOME"]: return ROOT_CAT_ID
    clean = re.sub(r'[^a-zA-Z0-9]', '_', str(text).strip())
    clean = re.sub(r'_+', '_', clean).strip('_')
    return f"CS_{clean}".upper()

# --- 2. AUTHENTICATION ---
def get_cpq_headers():
    url = f"{CPQ_BASE_URL}/basic/api/token"
    payload = {
        'grant_type': 'password',
        'username': CPQ_USERNAME,
        'password': CPQ_PASSWORD,
        'domain': CPQ_DOMAIN
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    try:
        resp = requests.post(url, data=payload, headers=headers)
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

# --- 3. AUTO-DETECT ENDPOINTS ---
def find_endpoints(headers):
    print("🔎 Validating API Endpoints...")
    patterns = ["/api/product/v1", "/api/products/v1"]

    prod_url = None
    attr_url = None

    for p in patterns:
        if not prod_url:
            u = f"{CPQ_BASE_URL}{p}/products"
            if requests.get(u, headers=headers, params={"$top":1}).status_code in [200, 401]:
                prod_url = u
        if not attr_url:
            u = f"{CPQ_BASE_URL}{p}/attributes"
            if requests.get(u, headers=headers, params={"$top":1}).status_code in [200, 401]:
                attr_url = u

    if not prod_url: prod_url = f"{CPQ_BASE_URL}/api/product/v1/products"
    if not attr_url: attr_url = f"{CPQ_BASE_URL}/api/product/v1/attributes"

    print(f"   ✅ Products: {prod_url}")
    print(f"   ✅ Attributes: {attr_url}")
    return prod_url, attr_url

# --- 4. INTELLIGENCE ENGINE ---
def generate_payload(product_name, parent_name, description):
    print(f"   🧠 Designing '{product_name}'...")

    # Generate IDs
    prod_sys_id = make_sys_id(product_name)
    cat_sys_id = make_sys_id(parent_name)

    # Safety: If sys_id equals root ID (unlikely for product but possible), append _PROD
    if prod_sys_id == cat_sys_id: prod_sys_id += "_PROD"

    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""
    Act as SAP CPQ Architect.
    Product: "{product_name}"
    Parent Category ID: "{cat_sys_id}"
    Desc: "{description}"

    Task: Create JSON for SAP CPQ Product Creation.

    CRITICAL RULES:
    1. "SystemId": "{prod_sys_id}"
    2. "CategorySystemId": "{cat_sys_id}"
    3. "PartNumber": "{prod_sys_id}"  <-- REQUIRED
    4. "Name": "Chirag Singhal - {product_name}"
    5. "ProductType": "Configurable"
    6. "DisplayType": "Configuration"
    7. "Active": true
    8. "BasePrice": (Integer)
    9. Attributes: Create 3 detailed technical attributes (e.g. Engine Power, Transmission Type, Hydraulics).

    Output JSON ONLY. No text.
    {{
        "SystemId": "...",
        "CategorySystemId": "...",
        "PartNumber": "...",
        "Name": "...",
        "ProductType": "...",
        "DisplayType": "...",
        "Active": true,
        "BasePrice": 0,
        "Description": "...",
        "Attributes": [
            {{
                "SystemId": "CS_ATTR_...",
                "Name": "...",
                "DisplayType": "DropDown",
                "Values": [
                    {{"ValueCode": "A", "Display": "Option A", "Price": 0}},
                    {{"ValueCode": "B", "Display": "Option B", "Price": 1000}}
                ]
            }}
        ]
    }}
    """

    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        raise ValueError("No JSON")
    except Exception as e:
        print(f"   ⚠️ AI Error: {e}. Using Fallback.")
        return {
            "SystemId": prod_sys_id,
            "CategorySystemId": cat_sys_id,
            "PartNumber": prod_sys_id,
            "Name": f"Chirag Singhal - {product_name}",
            "ProductType": "Configurable",
            "DisplayType": "Configuration",
            "Active": True,
            "BasePrice": 50000,
            "Description": description[:250],
            "Attributes": []
        }

# --- 5. UPLOADER ---
def upload_product(data, headers, prod_api, attr_api):
    sys_id = data['SystemId']

    # 1. Create Attributes
    for attr in data.get('Attributes', []):
        try:
            requests.post(attr_api, headers=headers, json={
                "SystemId": attr['SystemId'],
                "Name": attr['Name'],
                "DisplayType": "DropDown",
                "Active": True,
                "Values": attr['Values']
            })
        except: pass

    # 2. Upsert Product
    print(f"   🚀 Upserting {sys_id}...", end=" ")

    # Try Update
    check = requests.get(f"{prod_api}({sys_id})", headers=headers)

    if check.status_code == 200:
        # Update existing
        resp = requests.put(f"{prod_api}({sys_id})", headers=headers, json=data)
        action = "Updated"
    else:
        # Create new
        resp = requests.post(prod_api, headers=headers, json=data)
        action = "Created"

    if resp.status_code in [200, 201]:
        print(f"✅ {action}")

        # 3. Link Attributes
        for attr in data.get('Attributes', []):
            try:
                requests.post(f"{prod_api}({sys_id})/attributes", headers=headers, json={"SystemId": attr['SystemId']})
            except: pass
    else:
        # Print FULL detailed error
        print(f"❌ Failed ({resp.status_code})")
        print(f"      Response: {resp.text}")

# --- MAIN ---
if __name__ == "__main__":
    print(f"📂 Reading {INPUT_JSON_FILE}...")
    try:
        with open(INPUT_JSON_FILE, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except:
        print("❌ File not found."); sys.exit()

    # Filter
    products = [i for i in raw_data if i.get('isLeaf') or i.get('depth', 0) >= 3]
    print(f"🎯 Found {len(products)} products.")

    headers = get_cpq_headers()
    PROD_API, ATTR_API = find_endpoints(headers)

    for i, prod in enumerate(products):
        print(f"\n[{i+1}/{len(products)}] {prod.get('title')}")

        if i > 0 and i % 10 == 0: headers = get_cpq_headers()

        payload = generate_payload(
            prod.get('title'),
            prod.get('parent', 'Root'),
            prod.get('description', '')
        )

        upload_product(payload, headers, PROD_API, ATTR_API)
        time.sleep(1)