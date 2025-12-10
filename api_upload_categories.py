import pandas as pd
import requests
import json
from requests.auth import HTTPBasicAuth
import sys

# --- CONFIGURATION (UPDATE THESE) ---
BASE_URL = "https://tataconsultancyservices-partner1.cpq.cloud.sap"
USERNAME = "REDACTED_CPQ_USERNAME<=="
PASSWORD = "REDACTED_CPQ_PASSWORD<=="
DOMAIN = "tataconsultancyservices-partner1"

INPUT_FILE = '1_Upload_Categories_Chirag.xlsx'

# --- API SETUP ---
# Try the standard v1 endpoint first
API_ENDPOINT = f"{BASE_URL}/api/product/v1/categories"

def upload_categories():
    # FIX: Declare global at the start of the function
    global API_ENDPOINT

    print(f"--- SAP CPQ UPLOADER ---")
    print(f"Target: {API_ENDPOINT}")

    # 1. READ FILE
    try:
        df = pd.read_excel(INPUT_FILE)
    except FileNotFoundError:
        print("❌ Error: Excel file not found.")
        return

    # 2. AUTHENTICATION
    # Construct username as per CPQ Basic Auth standard: user#tenant
    auth_user = f"{USERNAME}#{DOMAIN}"
    print(f"Authenticating as: {auth_user}")

    session = requests.Session()
    session.auth = HTTPBasicAuth(auth_user, PASSWORD)
    session.headers.update({
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    })

    # 3. TEST CONNECTION
    # We try to get categories to verify auth before looping
    try:
        test_resp = session.get(API_ENDPOINT, params={"$top": 1})

        if test_resp.status_code == 404:
            print("❌ Error 404: API Endpoint not found.")
            print("Trying alternate endpoint '/api/products/v1/categories'...")

            # Switch to plural 'products' endpoint
            API_ENDPOINT = f"{BASE_URL}/api/products/v1/categories"
            test_resp = session.get(API_ENDPOINT, params={"$top": 1})

        if test_resp.status_code == 401:
            print("❌ Error 401: Unauthorized. Check Password or enable API in User Setup.")
            return
        elif test_resp.status_code not in [200, 201]:
            print(f"⚠️ Connection Warning: {test_resp.status_code} - {test_resp.text}")
        else:
            print("✅ Connection Successful!")

    except Exception as e:
        print(f"❌ Network Error: {e}")
        return

    # 4. SORT DATA (Parents First)
    df['Parent Category Code'] = df['Parent Category Code'].fillna('')
    # Simple sort: Empty parents (Roots) first
    df['SortKey'] = df['Parent Category Code'].apply(lambda x: 0 if x == '' else 1)
    df = df.sort_values('SortKey').drop('SortKey', axis=1)

    print(f"Starting upload for {len(df)} categories...")

    # 5. UPLOAD LOOP
    success = 0
    fail = 0

    for index, row in df.iterrows():
        sys_id = str(row['Category Code']).strip()
        name = str(row['Name']).strip()
        desc = str(row['Description']).strip() if pd.notna(row['Description']) else ""
        parent_id = str(row['Parent Category Code']).strip()

        # Construct Payload based on CPQ API Model
        payload = {
            "SystemId": sys_id,
            "Name": name,
            "Description": desc,
            "Active": True,
            "DisplayType": "Category",
            "VisibleToEveryone": True
        }

        if parent_id:
            payload["ParentCategorySystemId"] = parent_id

        print(f"[{index+1}] Creating {sys_id}...", end=" ")

        try:
            # POST request to create
            response = session.post(API_ENDPOINT, json=payload)

            if response.status_code in [200, 201]:
                print("✅ Created")
                success += 1
            elif response.status_code == 409:
                print("⚠️ Exists (Skipping)")
                success += 1
            else:
                # Extract error message
                try:
                    err = response.json().get('Message', response.text)
                except:
                    err = response.text[:100]
                print(f"❌ Failed: {err}")
                fail += 1

        except Exception as e:
            print(f"❌ Error: {e}")
            fail += 1

    print("\n--- SUMMARY ---")
    print(f"Success: {success}")
    print(f"Failed: {fail}")

if __name__ == "__main__":
    upload_categories()