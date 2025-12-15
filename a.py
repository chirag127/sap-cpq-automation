import pandas as pd
import json
import re
import os

# --- CONFIGURATION ---
# Ensure this file name matches your local JSON file
INPUT_JSON_FILE = 'agco_complete_data.json'
OUTPUT_EXCEL_FILE = 'CPQ_Import_Final.xlsx'

# Root Category System ID (Must exist in CPQ before importing products)
# Based on your previous scripts, this is likely "CS_MASSEY_FERGUSON"
ROOT_CATEGORY_ID = "CS_MASSEY_FERGUSON"

# User Settings for Naming Conventions
USER_PREFIX = "CS"
USER_FULL_NAME = "Chirag Singhal"

# --- HELPER FUNCTIONS ---
def make_sys_id(text):
    """Generates a clean System ID (e.g., 'Tractors' -> 'CS_TRACTORS')"""
    if not text: return f"{USER_PREFIX}_UNKNOWN"
    # Remove non-alphanumeric characters, replace with underscore
    clean = re.sub(r'[^a-zA-Z0-9]', '_', str(text).strip())
    # Remove duplicate underscores
    clean = re.sub(r'_+', '_', clean).strip('_')
    # Limit length to 50 chars to fit CPQ limits
    return f"{USER_PREFIX}_{clean}".upper()[:50]

def make_name(text):
    """Generates a consistent Product Name (e.g., 'Tractors - Chirag Singhal')"""
    if not text: return f"Unknown - {USER_FULL_NAME}"
    return f"{str(text).strip()} - {USER_FULL_NAME}"

# --- MAIN LOGIC ---
def process_data():
    print(f"📂 Reading {INPUT_JSON_FILE}...")

    # 1. Load JSON Data
    try:
        with open(INPUT_JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: File '{INPUT_JSON_FILE}' not found. Please check the filename.")
        return
    except json.JSONDecodeError:
        print(f"❌ Error: Failed to decode JSON. Please check the file format.")
        return

    rows = []

    print(f"   Processing {len(data)} items...")

    # 2. Iterate Through Data
    for item in data:
        title = item.get('title', 'Unknown')
        parent_name = item.get('parent', 'ROOT')
        depth = item.get('depth', 0)
        is_leaf = item.get('isLeaf', False)
        description = item.get('description', '')
        image_url = item.get('image', '')

        # Generate System IDs
        sys_id = make_sys_id(title)

        # Determine Category System ID (The Key Fix)
        # If parent is ROOT or Home, map to your top-level category ID
        if parent_name in ["ROOT", "Home"]:
            cat_sys_id = ROOT_CATEGORY_ID
        else:
            cat_sys_id = make_sys_id(parent_name)

        # Logic: Treat as Product if it's a leaf node OR deep in the hierarchy (Depth >= 3)
        if is_leaf or depth >= 3:

            # 3. Create Data Row
            row = {
                "Product System ID": sys_id,
                "Product Name": make_name(title),
                "Part Number": sys_id,

                # Use System ID for Category (Safer than path string)
                "Category System ID": cat_sys_id,
                # Include Name too just in case (optional for mapping)
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

    # 4. Generate Excel
    if rows:
        df = pd.DataFrame(rows)

        # Define Columns (Order matters for readability, though CPQ maps by name)
        cols = [
            "Product System ID",
            "Product Name",
            "Category System ID",
            "Categories",
            "Part Number",
            "Product Type",
            "Display Type",
            "Active",
            "Price",
            "Description",
            "Unit Of Measure",
            "Image File"
        ]

        # Ensure only valid columns are written
        df = df[cols]

        print(f"💾 Writing to {OUTPUT_EXCEL_FILE}...")
        df.to_excel(OUTPUT_EXCEL_FILE, index=False)
        print(f"✅ Success! Generated {OUTPUT_EXCEL_FILE} with {len(df)} products.")
        print("\n--- NEXT STEPS ---")
        print("1. Log in to SAP CPQ.")
        print("2. Go to Setup > Product Catalog > Bulk Import.")
        print("3. Upload this Excel file.")
        print("4. IMPORTANT: Map 'Category System ID' to the CPQ field 'Parent Category System ID'.")
    else:
        print("⚠️ No products found matching criteria (isLeaf=True or depth>=3).")

if __name__ == "__main__":
    process_data()