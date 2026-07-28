import os

import pandas as pd
import requests

# --- CONFIGURATION ---
BASE_URL = os.environ.get(
    "CPQ_BASE_URL", "https://tataconsultancyservices-partner1.cpq.cloud.sap"
)

ACCESS_TOKEN = os.environ.get("CPQ_ACCESS_TOKEN", "")

INPUT_FILE = "1_Upload_Categories_Chirag.xlsx"

# --- API SETUP ---
API_ENDPOINT = f"{BASE_URL}/api/products/v1/categories"


def upload_categories():
    print("--- SAP CPQ UPLOADER (TOKEN AUTH) ---")
    print(f"Target: {API_ENDPOINT}")

    # 1. SETUP HEADERS WITH TOKEN
    # This is the key change: We use 'Bearer' auth
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    session = requests.Session()
    session.headers.update(headers)

    # 2. TEST CONNECTION
    print("Testing Token Validity...")
    try:
        test_resp = session.get(API_ENDPOINT, params={"$top": 1})

        if test_resp.status_code == 401:
            print("❌ Error 401: Unauthorized.")
            print("Your Access Token has expired or is invalid.")
            print(
                "Please generate a new token from /basic/api/token and update the script."
            )
            return
        elif test_resp.status_code == 200:
            print("✅ Token is Valid! Starting Upload...")
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
    df["Parent Category Code"] = df["Parent Category Code"].fillna("")
    df["SortKey"] = df["Parent Category Code"].apply(lambda x: 0 if x == "" else 1)
    df = df.sort_values("SortKey").drop("SortKey", axis=1)

    # 5. UPLOAD LOOP
    success = 0
    fail = 0

    for index, row in df.iterrows():
        sys_id = str(row["Category Code"]).strip()
        name = str(row["Name"]).strip()
        desc = str(row["Description"]).strip() if pd.notna(row["Description"]) else ""
        parent_id = str(row["Parent Category Code"]).strip()

        payload = {
            "SystemId": sys_id,
            "Name": name,
            "Description": desc,
            "Active": True,
            "DisplayType": "Category",
            "VisibleToEveryone": True,
        }

        if parent_id:
            payload["ParentCategorySystemId"] = parent_id

        print(f"[{index + 1}] Creating {sys_id}...", end=" ")

        try:
            # We don't need 'auth=' here because headers handle it
            response = session.post(API_ENDPOINT, json=payload)

            if response.status_code in [200, 201]:
                print("✅ Created")
                success += 1
            elif response.status_code == 409:
                print("⚠️ Exists")
                success += 1
            else:
                try:
                    err = response.json().get("Message", response.text)
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
