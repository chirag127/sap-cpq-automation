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

# --- 3. AUTO-DETECT API URL (THE FIX) ---
def find_correct_endpoints(headers):
    print("🔎 Detecting correct API Endpoints...")

    # Possible patterns for SAP CPQ
    patterns = [
        "/api/product/v1",   # Standard Singular
        "/api/products/v1",  # Plural (Newer tenants)
        "/api/v1"            # Short
    ]

    prod_url = None
    attr_url = None

    # Test for Products Endpoint
    for p in patterns:
        test_url = f"{CPQ_BASE_URL}{p}/products"
        try:
            # Request 1 item to check if endpoint exists
            r = requests.get(test_url, headers=headers, params={"$top": 1})
            if r.status_code in [200, 401]: # 200=OK, 401=Auth bad but URL good
                print(f"   ✅ Products API found at: {test_url}")
                prod_url = test_url
                break
        except: pass

    # Test for Attributes Endpoint
    for p in patterns:
        test_url = f"{CPQ_BASE_URL}{p}/attributes"
        try:
            r = requests.get(test_url, headers=headers, params={"$top": 1})
            if r.status_code in [200, 401]:
                print(f"   ✅ Attributes API found at: {test_url}")
                attr_url = test_url
                break
        except: pass

    if not prod_url or not attr_url:
        print("❌ Could not auto-detect API URLs. Check your Tenant URL.")
        # Fallback to mixed if detection fails
        if not prod_url: prod_url = f"{CPQ_BASE_URL}/api/product/v1/products"
        if not attr_url: attr_url = f"{CPQ_BASE_URL}/api/product/v1/attributes"

    return prod_url, attr_url

# --- 4. INTELLIGENCE ENGINE ---
def generate_cpq_data(product_name, description, image_url):
    print(f"   🧠 Analyzing '{product_name}'...")

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        # Cleaner System ID generation
        clean_name = re.sub(r'[^a-zA-Z0-9]', '_', product_name).upper()
        # Remove duplicate MF prefix if present
        if clean_name.startswith("MF_"): clean_name = clean_name[3:]
        sys_id = f"CS_MF_{clean_name}"[:30] # Limit length

        prompt = f"""
        Act as SAP CPQ Architect.
        Product: "{product_name}"
        Description: "{description}"

        Create JSON for SAP CPQ Product Import.
        1. SystemId: "{sys_id}"
        2. Name: "Chirag Singhal - {product_name}"
        3. BasePrice: Numeric integer (e.g. 55000)
        4. Attributes: Define 2 technical attributes (e.g. Transmission, Hydraulics).

        Output JSON ONLY.
        {{
            "SystemId": "{sys_id}",
            "Name": "Chirag Singhal - {product_name}",
            "DisplayType": "Configuration",
            "ProductType": "Configurable",
            "Active": true,
            "BasePrice": 50000,
            "Description": "{description[:100]}...",
            "Attributes": [
                {{
                    "SystemId": "CS_ATTR_TRANS_{clean_name[:5]}",
                    "Name": "Transmission",
                    "DisplayType": "DropDown",
                    "Values": [
                        {{"ValueCode": "STD", "Display": "Standard", "Price": 0}},
                        {{"ValueCode": "PRO", "Display": "Pro Spec", "Price": 2500}}
                    ]
                }}
            ]
        }}
        """

        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)

        # Extract JSON
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        else:
            raise ValueError("No JSON found")

    except Exception as e:
        print(f"   ⚠️ AI Error: {e}. Using Fallback.")
        return {
            "SystemId": sys_id,
            "Name": f"Chirag Singhal - {product_name}",
            "DisplayType": "Configuration",
            "ProductType": "Configurable",
            "Active": True,
            "BasePrice": 50000,
            "Description": description[:200],
            "Attributes": []
        }

# --- 5. CPQ LOADER ---
def push_to_cpq(data, headers, prod_api, attr_api):
    sys_id = data['SystemId']

    # 1. Attributes
    for attr in data.get('Attributes', []):
        try:
            requests.post(attr_api, headers=headers, json={
                "SystemId": attr['SystemId'],
                "Name": attr['Name'],
                "DisplayType": attr['DisplayType'],
                "Active": True,
                "Values": attr['Values']
            })
        except: pass

    # 2. Product
    print(f"   🚀 Upserting: {sys_id}...", end=" ")

    # Try Update first
    check_url = f"{prod_api}({sys_id})"
    check = requests.get(check_url, headers=headers)

    if check.status_code == 200:
        resp = requests.put(check_url, headers=headers, json=data)
        action = "Updated"
    else:
        resp = requests.post(prod_api, headers=headers, json=data)
        action = "Created"

    if resp.status_code in [200, 201]:
        print(f"✅ {action}")

        # 3. Link Attributes
        link_url = f"{prod_api}({sys_id})/attributes"
        for attr in data.get('Attributes', []):
            try:
                requests.post(link_url, headers=headers, json={"SystemId": attr['SystemId']})
            except: pass
    else:
        print(f"❌ Failed ({resp.status_code}): {resp.text[:100]}")

# --- MAIN ---
if __name__ == "__main__":
    print(f"📂 Reading {INPUT_JSON_FILE}...")
    try:
        with open(INPUT_JSON_FILE, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        print("❌ File not found.")
        sys.exit()

    # Filter for products
    products = [i for i in raw_data if i.get('isLeaf') or i.get('depth', 0) >= 3]
    print(f"🎯 Found {len(products)} products.")

    # Auth & Setup
    headers = get_cpq_headers()
    PROD_API, ATTR_API = find_correct_endpoints(headers)

    for i, prod in enumerate(products):
        print(f"\n[{i+1}/{len(products)}] {prod.get('title')}")

        # Periodic Token Refresh
        if i > 0 and i % 10 == 0: headers = get_cpq_headers()

        data = generate_cpq_data(
            prod.get('title'),
            prod.get('description', ''),
            prod.get('image', '')
        )

        push_to_cpq(data, headers, PROD_API, ATTR_API)
        time.sleep(1)