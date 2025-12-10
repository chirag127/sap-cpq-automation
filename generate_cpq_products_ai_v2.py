
import json
import time
import requests
from google import genai
from google.genai import types # <--- CRITICAL IMPORT
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
GEMINI_API_KEY = "AIzaSyBS5im3Kp10MrGHBs5pQ5-UdsHw3nqZ0GI"
GEMINI_MODEL = "gemini-2.5-flash-lite-preview-09-2025"

# --- 1. CONFIGURATION ---
INPUT_JSON_FILE = 'agco_complete_data.json' # Your scraped data file

# Root Category ID (Must match what you uploaded earlier)
ROOT_CAT_ID = "CS_MASSEY_FERGUSON"
# --- 2. AUTHENTICATION ---
def get_cpq_headers():
    url = f"{CPQ_BASE_URL}/basic/api/token"
    payload = {'grant_type':'password', 'username':CPQ_USERNAME, 'password':CPQ_PASSWORD, 'domain':CPQ_DOMAIN}
    try:
        resp = requests.post(url, data=payload)
        if resp.status_code != 200:
            print(f"❌ Auth Failed: {resp.text}")
            sys.exit(1)
        return {'Authorization': f"Bearer {resp.json()['access_token']}", 'Content-Type': 'application/json'}
    except Exception as e:
        print(f"❌ Connection Error: {e}"); sys.exit(1)

# --- 3. HELPER: ID GENERATOR ---
def make_sys_id(text):
    if not text or text.upper() in ["ROOT", "HOME"]: return "CS_MASSEY_FERGUSON"
    clean = re.sub(r'[^a-zA-Z0-9]', '_', str(text).strip())
    clean = re.sub(r'_+', '_', clean).strip('_')
    return f"CS_{clean}".upper()[:50]

# --- 4. DIAGNOSTIC: FIND VALID PAYLOAD ---
def detect_valid_structure(headers, prod_api):
    print("🔬 DIAGNOSTIC: Attempting to fetch an existing product...")
    try:
        # Try to get ANY product to see its structure
        resp = requests.get(prod_api, headers=headers, params={"$top": 1})
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('Items', []) or data.get('Value', [])
            if items:
                print("   ✅ Found existing product! Analyzing structure...")
                sample = items[0]
                # Check how ProductType is formatted
                pt = sample.get('BasicInfo', {}).get('ProductType')
                dt = sample.get('BasicInfo', {}).get('DisplayType')
                print(f"   ℹ️ System expects: ProductType={pt}, DisplayType={dt}")
                return pt, dt
    except: pass

    print("   ⚠️ No existing products found. Using 'Minimal' Strategy.")
    return None, None

# --- 5. INTELLIGENCE ENGINE ---
def analyze_product(product_name, description):
    print(f"   🧠 Analyzing '{product_name}'...", end=" ")
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""
        Product: {product_name}
        Desc: {description}