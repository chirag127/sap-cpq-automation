import pandas as pd
import json
import re
import os

# --- CONFIGURATION ---
INPUT_JSON_FILE = 'agco_complete_data.json'
OUTPUT_EXCEL_FILE = 'SAP_CPQ_Product_Import_Clean.xlsx'

# User Settings
USER_PREFIX = "CS"
USER_FULL_NAME = "Chirag Singhal"

# --- HELPER FUNCTIONS ---
def make_sys_id(text):
    if not text: return f"{USER_PREFIX}_UNKNOWN"
    clean = re.sub(r'[^a-zA-Z0-9]', '_', str(text).strip())
    clean = re.sub(r'_+', '_', clean).strip('_')
    return f"{USER_PREFIX}_{clean}".upper()[:50]

def make_name(text):
    if not text: return f"Unknown - {USER_FULL_NAME}"
    return f"{str(text).strip()} - {USER_FULL_NAME}"

# --- MAIN LOGIC ---
def process_data():
    print(f"📂 Reading {INPUT_JSON_FILE}...")

    try:
        with open(INPUT_JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ ERROR: Could not find {INPUT_JSON_FILE}.")
        return

    # 1. REQUIRED COLUMNS ONLY
    # These headers are standard for SAP CPQ Product Bulk Import
    required_columns = [
        "Product System ID",   # Mandatory key
        "Product Name",        # Mandatory name
        "Part Number",         # Highly recommended
        "Categories",          # Mandatory (Plural)
        "Product Type",        # Mandatory (Configurable vs Simple)
        "Display Type",        # Mandatory (UI behavior)
        "Active",              # Mandatory (Status)
        "Base Price",          # Mandatory for pricing
        "Description",         # Optional but good
        "Unit Of Measure"      # Often required
    ]

    rows = []

    for item in data:
        title = item.get('title', 'Unknown')
        parent_name = item.get('parent', 'ROOT')
        depth = item.get('depth', 0)
        is_leaf = item.get('isLeaf', False)
        description = item.get('description', '')

        sys_id = make_sys_id(title)

        # Determine Category Code
        if parent_name in ["ROOT", "Home"]:
            cat_code = make_sys_id("Massey Ferguson")
        else:
            cat_code = make_sys_id(parent_name)

        # Logic: Treat as Product if leaf or deep enough
        if is_leaf or depth >= 3:

            # 2. CREATE ROW
            row = {
                "Product System ID": sys_id,
                "Product Name": make_name(title),
                "Part Number": sys_id,
                "Categories": cat_code,

                # FIX 1: Use 'Configurable' for Type
                "Product Type": "Configurable",

                # FIX 2: Use 'Configurable Product' for Display (Solves Invalid UI Type)
                "Display Type": "Configurable Product",

                "Active": "TRUE",
                "Base Price": "50000",
                "Description": description[:255] if description else title,
                "Unit Of Measure": "PC"
            }
            rows.append(row)

    # 3. WRITE TO EXCEL
    if rows:
        df = pd.DataFrame(rows)
        # Enforce column order
        df = df[required_columns]

        print(f"💾 Writing to {OUTPUT_EXCEL_FILE}...")
        df.to_excel(OUTPUT_EXCEL_FILE, index=False)
        print(f"✅ Success! Generated {OUTPUT_EXCEL_FILE} with {len(df)} products.")
        print("   -> Upload this file to Setup > Product Catalog > Bulk Import.")
    else:
        print("⚠️ No products found in JSON data.")

if __name__ == "__main__":
    process_data()