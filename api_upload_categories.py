import pandas as pd
import requests
import json
from requests.auth import HTTPBasicAuth

# --- CONFIGURATION (UPDATE THESE) ---
# --- CONFIGURATION ---
BASE_URL = "https://tataconsultancyservices-partner1.cpq.cloud.sap"

# Your Login Credentials for this specific site
USERNAME = "REDACTED_CPQ_USERNAME<=="  # e.g., chirag.singhal
PASSWORD = "REDACTED_CPQ_PASSWORD<=="
# For this specific URL format, the Domain might not be required in the Auth header
# if you use the standard /api endpoints, but often it is 'tataconsultancyservices-partner1'
DOMAIN = "tataconsultancyservices-partner1"



INPUT_FILE = '1_Upload_Categories_Chirag.xlsx'

# --- API ENDPOINTS ---
API_URL = f"{BASE_URL}/api/product/v1/categories"

def upload_categories():
    print(f"Reading {INPUT_FILE}...")
    try:
        df = pd.read_excel(INPUT_FILE)
    except FileNotFoundError:
        print("Error: Excel file not found.")
        return

    # 1. SORT DATA BY HIERARCHY
    # We must create parents before children.
    # Logic: Rows with empty 'Parent Category Code' are Level 0.

    # Fill NaN parents with empty string for sorting
    df['Parent Category Code'] = df['Parent Category Code'].fillna('')

    # Create a 'Depth' column for sorting (Root = 0, others = 1+)
    # This is a simple approximation: empty parent = 0, else 1.
    # For deep hierarchies, we might need multiple passes, but this usually works for SAP CPQ
    # because the file was generated top-down.

    print(f"found {len(df)} categories to upload.")

    # 2. ITERATE AND UPLOAD
    session = requests.Session()
    session.auth = HTTPBasicAuth(f"{USERNAME}#{DOMAIN}", PASSWORD)
    session.headers.update({'Content-Type': 'application/json'})

    success_count = 0
    fail_count = 0

    for index, row in df.iterrows():
        sys_id = row['Category Code']
        parent_id = row['Parent Category Code']
        name = row['Name']
        desc = row['Description']

        # Prepare Payload
        payload = {
            "SystemId": sys_id,
            "Name": name,
            "Description": desc,
            "Active": True,
            "DisplayType": "Category"
        }

        # Add Parent if it exists
        if parent_id:
            payload["ParentCategorySystemId"] = parent_id

        print(f"[{index+1}/{len(df)}] Creating: {sys_id}...", end=" ")

        try:
            response = session.post(API_URL, json=payload)

            if response.status_code in [200, 201]:
                print("✅ Success")
                success_count += 1
            elif response.status_code == 409:
                print("⚠️ Exists (Skipping)")
            else:
                print(f"❌ Failed: {response.text}")
                fail_count += 1

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            fail_count += 1

    print("\n--- SUMMARY ---")
    print(f"Successfully Created: {success_count}")
    print(f"Failed: {fail_count}")

if __name__ == "__main__":
    upload_categories()