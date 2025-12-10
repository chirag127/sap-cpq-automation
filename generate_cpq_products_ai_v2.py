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


# --- 2. AUTHENTICATION MANAGER ---
def get_cpq_headers():
    payload = {
        'grant_type': 'password',
        'username': CPQ_USERNAME,
        'password': CPQ_PASSWORD,
        'domain': CPQ_DOMAIN
    }
    try:
        resp = requests.post(CPQ_TOKEN_URL, data=payload)
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

# --- 3. INTELLIGENCE ENGINE (Gemini 2.5) ---
def generate_cpq_data(product_name, description, image_url):
    print(f"   🧠 Analyzing '{product_name}' with {GEMINI_MODEL}...")

    client = genai.Client(api_key=GEMINI_API_KEY)

    clean_id = re.sub(r'[^a-zA-Z0-9]', '_', product_name).upper()
    sys_id = f"CS_MF_{clean_id}"[:30] # Truncate if too long

    prompt = f"""
    You are an SAP CPQ Expert. Create a JSON payload for the product: "{product_name}".
    Description from website: "{description}"

    TASKS:
    1. Infer realistic technical attributes (Engine, Transmission, HP, Hydraulics) based on the model name.
    2. Estimate a Base Price (USD).
    3. Output valid JSON matching the SAP CPQ structure below.

    JSON Structure:
    {{
        "SystemId": "{sys_id}",
        "Name": "Chirag Singhal - {product_name}",
        "DisplayType": "Configuration",
        "ProductType": "Configurable",
        "Active": true,
        "BasePrice": 0,
        "Description": "{description}",
        "ImageUrl": "{image_url}",
        "Attributes": [
            {{
                "SystemId": "CS_ATTR_TRANS_{clean_id}",
                "Name": "Transmission",
                "DisplayType": "DropDown",
                "Values": [
                    {{"ValueCode": "STD", "Display": "Standard", "Price": 0}},
                    {{"ValueCode": "OPT", "Display": "Premium", "Price": 1500}}
                ]
            }},
            {{
                "SystemId": "CS_ATTR_HP_{clean_id}",
                "Name": "Horsepower",
                "DisplayType": "ReadOnly",
                "Values": [
                    {{"ValueCode": "BASE", "Display": "Standard HP", "Price": 0}}
                ]
            }}
        ]
    }}
    """

    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        print(f"   ❌ AI Generation Error: {e}")
        return None

# --- 4. CPQ LOADER ---
def push_to_cpq(data, headers):
    sys_id = data['SystemId']

    # 1. Attributes
    for attr in data.get('Attributes', []):
        try:
            # Create Attribute Definition
            requests.post(CPQ_ATTR_API, headers=headers, json={
                "SystemId": attr['SystemId'],
                "Name": attr['Name'],
                "DisplayType": attr['DisplayType'],
                "Active": True,
                "Values": attr['Values']
            })
        except: pass

    # 2. Product Upsert
    print(f"   🚀 Upserting Product: {sys_id}...")

    # Check existence
    check = requests.get(f"{CPQ_PRODUCT_API}({sys_id})", headers=headers)

    if check.status_code == 200:
        # Update
        resp = requests.put(f"{CPQ_PRODUCT_API}({sys_id})", headers=headers, json=data)
        action = "Updated"
    else:
        # Create
        resp = requests.post(CPQ_PRODUCT_API, headers=headers, json=data)
        action = "Created"

    if resp.status_code in [200, 201]:
        print(f"      ✅ {action} Successfully")

        # 3. Assign Attributes
        link_url = f"{CPQ_PRODUCT_API}({sys_id})/attributes"
        for attr in data.get('Attributes', []):
            requests.post(link_url, headers=headers, json={"SystemId": attr['SystemId']})
    else:
        print(f"      ❌ Failed: {resp.text}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    print(f"📂 Reading {INPUT_JSON_FILE}...")
    try:
        with open(INPUT_JSON_FILE, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        print("❌ JSON file not found. Run the scraper first.")
        sys.exit()

    # Filter: Only Products (Leaf Nodes) or Depth >= 3
    products_to_process = [
        item for item in raw_data
        if item.get('isLeaf') is True or item.get('depth', 0) >= 3
    ]

    print(f"🎯 Found {len(products_to_process)} products to generate.")

    # Get initial token
    headers = get_cpq_headers()

    for i, prod in enumerate(products_to_process):
        print(f"\n🔹 [{i+1}/{len(products_to_process)}] Processing: {prod.get('title')}")

        # Refresh token every 10 items to be safe
        if i > 0 and i % 10 == 0:
            print("🔄 Refreshing Token...")
            headers = get_cpq_headers()

        # Generate Data
        cpq_payload = generate_cpq_data(
            prod.get('title'),
            prod.get('description', ''),
            prod.get('image', '')
        )

        if cpq_payload:
            # Upload
            push_to_cpq(cpq_payload, headers)

        time.sleep(1) # Prevent API rate limits

    print("\n✅ JOB COMPLETE.")