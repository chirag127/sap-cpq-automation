import pandas as pd
import requests
import json
from requests.auth import HTTPBasicAuth
import sys

# --- CONFIGURATION ---
BASE_URL = "https://tataconsultancyservices-partner1.cpq.cloud.sap"
# TRY 1: Use just your ID (remove @tcs.com)
USERNAME = "chirag.singhal2"
PASSWORD = "REDACTED_CPQ_PASSWORD<=="
DOMAIN = "tataconsultancyservices-partner1"

INPUT_FILE = '1_Upload_Categories_Chirag.xlsx'

# --- API SETUP ---
# We found out from your logs that 'products' (plural) is the correct path
API_ENDPOINT = f"{BASE_URL}/api/products/v1/categories"

def upload_categories():
    print(f"--- SAP CPQ UPLOADER V4 ---")

    # 1. AUTHENTICATION CONSTRUCTION
    # Construct: chirag.singhal2#tataconsultancyservices-partner1
    auth_user = f"{USERNAME}#{DOMAIN}"

    print(f"Target: {API_ENDPOINT}")
    print(f"User:   {auth_user}")

    session = requests.Session()
    session.auth = HTTPBasicAuth(auth_user, PASSWORD)
    session.headers.update({
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    })

    # 2. TEST CONNECTION
    print(f"Testing Auth...")
    try:
        test_resp = session.get(API_ENDPOINT, params={"$top": 1})

        if test_resp.status_code == 403 or test_resp.status_code == 401:
            print("❌ AUTHENTICATION FAILED.")
            print("Creating an API Password usually fixes this.")
            print("1. Log in to CPQ.")
            print("2. Click your Name (top right) > Setup > Users > Users.")
            print("3. Click on your user 'chirag.singhal2'.")
            print("4. Scroll down to 'API Password' section.")
            print("5. Click 'Generate Password', Copy it, and paste it into the script.")
            return
        elif test_resp.status_code == 200:
            print("✅ Connection Successful! Starting Upload...")
        else:
            print(f"⚠️ Warning: {test_resp.status_code} - {test_resp.text}")

    except Exception as e:
        print(f"❌ Network Error: {e}")
        return

    # 3. READ FILE
    try:
        df = pd.read_excel(INPUT_FILE)
    except FileNotFoundError:
        print("❌ Error: Excel file not found.")
        return

    # 4. SORT DATA
    df['Parent Category Code'] = df['Parent Category Code'].fillna('')
    df['SortKey'] = df['Parent Category Code'].apply(lambda x: 0 if x == '' else 1)
    df = df.sort_values('SortKey').drop('SortKey', axis=1)

    # 5. UPLOAD LOOP
    success = 0
    fail = 0

    for index, row in df.iterrows():
        sys_id = str(row['Category Code']).strip()
        name = str(row['Name']).strip()
        desc = str(row['Description']).strip() if pd.notna(row['Description']) else ""
        parent_id = str(row['Parent Category Code']).strip()

        # Payload
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
            response = session.post(API_ENDPOINT, json=payload)

            if response.status_code in [200, 201]:
                print("✅ Created")
                success += 1
            elif response.status_code == 409:
                print("⚠️ Exists")
                success += 1
            else:
                try:
                    err = response.json().get('Message', response.text)
                except:
                    err = response.text[:50]
                print(f"❌ {err}")
                fail += 1
        except Exception as e:
            print(f"❌ Error: {e}")
            fail += 1

    print("\n--- SUMMARY ---")
    print(f"Success: {success}")
    print(f"Failed: {fail}")

if __name__ == "__main__":
    upload_categories()