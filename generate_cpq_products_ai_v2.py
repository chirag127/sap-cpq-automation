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

# --- 3. INTELLIGENCE ENGINE ---
def generate_cpq_data(product_name, description, image_url):
    print(f"   🧠 Analyzing '{product_name}'...")

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        clean_id = re.sub(r'[^a-zA-Z0-9]', '_', product_name).upper()
        sys_id = f"CS_MF_{clean_id}"[:30]

        prompt = f"""
        Act as a CPQ Data Architect.
        Product: "{product_name}"
        Description: "{description}"

        Task: Create a valid JSON object for this product.

        Requirements:
        1. SystemId: "{sys_id}"
        2. Name: "Chirag Singhal - {product_name}"
        3. BasePrice: Estimate a realistic integer (e.g. 45000).
        4. Attributes: Create 2 specific attributes based on the machine type (e.g. Transmission, Flow Rate, Horsepower).

        Output JSON ONLY. No markdown. No chatter.
        Structure:
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
                    "SystemId": "CS_ATTR_{clean_id}_1",
                    "Name": "Example Attribute",
                    "DisplayType": "DropDown",
                    "Values": [
                        {{"ValueCode": "A", "Display": "Option A", "Price": 0}}
                    ]
                }}
            ]
        }}
        """

        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)

        # --- ROBUST JSON EXTRACTION ---
        raw_text = response.text
        # Find the first '{' and the last '}'
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)

        if json_match:
            clean_json = json_match.group(0)
            return json.loads(clean_json)
        else:
            raise ValueError(f"No JSON found in response: {raw_text[:50]}...")

    except Exception as e:
        print(f"   ⚠️ AI Failed: {e}")
        print("   ⚠️ Generating FALLBACK data instead.")

        # Fallback Data so script continues
        return {
            "SystemId": sys_id,
            "Name": f"Chirag Singhal - {product_name}",
            "DisplayType": "Configuration",
            "ProductType": "Configurable",
            "Active": True,
            "BasePrice": 50000,
            "Description": description,
            "Attributes": [
                {
                    "SystemId": f"CS_ATTR_STD_{clean_id}",
                    "Name": "Standard Configuration",
                    "DisplayType": "DropDown",
                    "Values": [{"ValueCode": "STD", "Display": "Standard", "Price": 0}]
                }
            ]
        }

# --- 4. CPQ LOADER ---
def push_to_cpq(data, headers):
    sys_id = data['SystemId']

    # 1. Attributes
    for attr in data.get('Attributes', []):
        try:
            requests.post(CPQ_ATTR_API, headers=headers, json={
                "SystemId": attr['SystemId'],
                "Name": attr['Name'],
                "DisplayType": attr['DisplayType'],
                "Active": True,
                "Values": attr['Values']
            })
        except: pass

    # 2. Product
    print(f"   🚀 Upserting: {sys_id}...", end=" ")

    check = requests.get(f"{CPQ_PRODUCT_API}({sys_id})", headers=headers)

    if check.status_code == 200:
        resp = requests.put(f"{CPQ_PRODUCT_API}({sys_id})", headers=headers, json=data)
        print("✅ Updated")
    else:
        resp = requests.post(CPQ_PRODUCT_API, headers=headers, json=data)
        if resp.status_code in [200, 201]:
            print("✅ Created")
        else:
            print(f"❌ Failed ({resp.status_code}): {resp.text[:100]}")

    # 3. Link
    link_url = f"{CPQ_PRODUCT_API}({sys_id})/attributes"
    for attr in data.get('Attributes', []):
        try:
            requests.post(link_url, headers=headers, json={"SystemId": attr['SystemId']})
        except: pass

# --- MAIN ---
if __name__ == "__main__":
    print(f"📂 Reading {INPUT_JSON_FILE}...")
    try:
        with open(INPUT_JSON_FILE, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        print("❌ JSON file not found.")
        sys.exit()

    # Filter for Products (Leaf Nodes or Depth 3+)
    products_to_process = [
        item for item in raw_data
        if item.get('isLeaf') is True or item.get('depth', 0) >= 3
    ]

    print(f"🎯 Processing {len(products_to_process)} products...")

    headers = get_cpq_headers()

    for i, prod in enumerate(products_to_process):
        print(f"\n[{i+1}/{len(products_to_process)}] {prod.get('title')}")

        # Refresh token periodically
        if i > 0 and i % 10 == 0: headers = get_cpq_headers()

        data = generate_cpq_data(
            prod.get('title'),
            prod.get('description', ''),
            prod.get('image', '')
        )

        if data:
            push_to_cpq(data, headers)

        time.sleep(1) # Prevent rate limiting