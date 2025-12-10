import pandas as pd
import json
import re
import os

# --- CONFIGURATION ---
INPUT_JSON_FILE = 'agco_complete_data.json'
OUTPUT_EXCEL_FILE = 'CPQ_Import_Final.xlsx'
ROOT_CATEGORY_ID = "CS_MASSEY_FERGUSON" # Must match your uploaded root category System ID

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
    except:
        print("❌ File not found."); return

    rows = []

    # Iterate Data
    for item in data:
        title = item.get('title', 'Unknown')
        parent_name = item.get('parent', 'ROOT')
        depth = item.get('depth', 0)
        is_leaf = item.get('isLeaf', False)
        description = item.get('description', '')
        image_url = item.get('image', '')

        sys_id = make_sys_id(title)

        # Determine Category System ID (The Key Fix)
        if parent_name in ["ROOT", "Home"]:
            cat_sys_id = ROOT_CATEGORY_ID
        else:
            cat_sys_id = make_sys_id(parent_name)

        if is_leaf or depth >= 3:

            # CREATE ROW
            row = {
                "Product System ID": sys_id,
                "Product Name": make_name(title),
                "Part Number": sys_id,

                # Use System ID for Category (Safer than path string)
                "Category System ID": cat_sys_id,
                # Include Name too just in case
                "Categories": parent_name if parent_name != "ROOT" else "Massey Ferguson",

                "Product Type": "Configurable Product",
                "Display Type": "Configurable Product",
                "Active": "TRUE",
                "Price": "50000",
                "Description": description[:255] if description else title,
                "Unit Of Measure": "PC",
                "Image File": image_url
            }
            rows.append(row)

    # OUTPUT
    if rows:
        df = pd.DataFrame(rows)

        # Define Columns
        cols = [
            "Product System ID", "Product Name", "Category System ID", "Categories",
            "Part Number", "Product Type", "Display Type", "Active",
            "Price", "Description", "Unit Of Measure", "Image File"
        ]

        df = df[cols]

        print(f"💾 Writing to {OUTPUT_EXCEL_FILE}...")
        df.to_excel(OUTPUT_EXCEL_FILE, index=False)
        print(f"✅ Success! Generated {OUTPUT_EXCEL_FILE} with {len(df)} products.")
    else:
        print("⚠️ No products found.")

if __name__ == "__main__":
    process_data()