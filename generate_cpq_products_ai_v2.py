import requests
import json
import time
from googlesearch import search
from google import genai
from google.genai import types
import sys
import re

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

# --- 2. AUTHENTICATION MANAGER ---
def get_cpq_headers():
    """Generates a fresh Bearer Token"""
    # print("🔑 Authenticating with SAP CPQ...")
    payload = {
        'grant_type': 'password',
        'username': CPQ_USERNAME,
        'password': CPQ_PASSWORD,
        'domain': CPQ_DOMAIN
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    try:
        response = requests.post(CPQ_TOKEN_URL, data=payload, headers=headers)
        if response.status_code != 200:
            print(f"❌ Auth Failed: {response.text}")
            sys.exit(1)

        token = response.json()['access_token']
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        sys.exit(1)

# --- 3. DATA MINER (Google Search) ---
def fetch_real_world_specs(product_name):
    """Searches the web for real specs to feed the AI"""
    print(f"   🔍 Searching specs for: '{product_name}'...")
    query = f"Massey Ferguson {product_name} technical specifications engine transmission price"

    context_text = ""
    try:
        # Get top 3 search snippets
        results = search(query, num_results=3, advanced=True)
        for res in results:
            context_text += f"- {res.title}: {res.description}\n"
    except:
        context_text = "Standard agricultural tractor specifications."

    return context_text

# --- 4. INTELLIGENCE ENGINE (Gemini 2.5) ---
def generate_cpq_payload(product_name, raw_context):
    print(f"   🧠 Reasoning with {GEMINI_MODEL}...")

    # Initialize the NEW client
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""
    You are a Solution Architect for SAP CPQ.
    Task: Create a JSON payload to create a Configurable Product.

    Product: "{product_name}"
    Real World Context: {raw_context}

    Requirements:
    1. SystemId MUST be "CS_{product_name.replace(' ', '_').replace('.', '_').upper()}"
    2. Name MUST be "Chirag Singhal - {product_name}"
    3. Extract realistic Attributes (Engine, Transmission) from context.
    4. BasePrice should be a realistic integer (in USD).

    Output Format: JSON ONLY. Do not use Markdown code blocks.
    {{
        "SystemId": "...",
        "Name": "...",
        "DisplayType": "Configuration",
        "ProductType": "Configurable",
        "Active": true,
        "BasePrice": 0000,
        "Description": "...",
        "Attributes": [
            {{
                "SystemId": "CS_ATTR_...",
                "Name": "...",
                "DisplayType": "DropDown",
                "Values": [
                    {{"ValueCode": "...", "Display": "...", "Price": 0}}
                ]
            }}
        ]
    }}
    """

    try:
        # Using the new SDK method signature
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        # Clean response (remove ```json if present)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)

    except Exception as e:
        print(f"   ❌ AI Generation Error: {e}")
        return None

# --- 5. CPQ LOADER ---
def push_to_sap_cpq(product_json):
    headers = get_cpq_headers()
    sys_id = product_json['SystemId']

    # A. Create Attributes First
    print(f"   ⚙️ Syncing Attributes...")
    for attr in product_json.get('Attributes', []):
        attr_payload = {
            "SystemId": attr['SystemId'],
            "Name": attr['Name'],
            "DisplayType": attr['DisplayType'],
            "Active": True,
            "Values": attr['Values']
        }
        # Create Attribute (Ignore error if exists)
        requests.post(CPQ_ATTR_API, headers=headers, json=attr_payload)

    # B. Create/Update Product
    print(f"   🚀 Upserting Product: {sys_id}...")

    # Check if exists
    check_req = requests.get(f"{CPQ_PRODUCT_API}({sys_id})", headers=headers)

    if check_req.status_code == 200:
        # Update (PUT)
        requests.put(f"{CPQ_PRODUCT_API}({sys_id})", headers=headers, json=product_json)
        print("      ✅ Updated successfully.")
    else:
        # Create (POST)
        resp = requests.post(CPQ_PRODUCT_API, headers=headers, json=product_json)
        if resp.status_code in [200, 201]:
            print("      ✅ Created successfully.")
        else:
            print(f"      ❌ Failed: {resp.text}")

    # C. Assign Attributes to Product
    # (Simplified logic: In production, you link them via a separate endpoint)
    link_url = f"{CPQ_PRODUCT_API}({sys_id})/attributes"
    for attr in product_json.get('Attributes', []):
        link_payload = {"SystemId": attr['SystemId']}
        requests.post(link_url, headers=headers, json=link_payload)

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # List of products to generate
    products = [
        "MF 4708 M",
        "MF 5711 M",
        "MF 8S.265",
        "MF IDEAL 8"
    ]

    print("🤖 STARTING AI CPQ GENERATOR (GEMINI 2.5)")

    for prod in products:
        print(f"\n🔹 Processing: {prod}")

        # 1. Search
        context = fetch_real_world_specs(prod)

        # 2. AI Generate
        data = generate_cpq_payload(prod, context)

        if data:
            # 3. Push to SAP
            push_to_sap_cpq(data)

        time.sleep(2) # Polite delay