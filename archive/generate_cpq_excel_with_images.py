import pandas as pd
import json
import re
import os

# --- CONFIGURATION ---
INPUT_JSON_FILE = 'agco_complete_data.json'
OUTPUT_EXCEL_FILE = 'CPQ_Upload_With_Images.xlsx'

# Naming Convention
USER_PREFIX = "CS"
USER_FULL_NAME = "Chirag Singhal"

# --- HELPER FUNCTIONS ---
def make_sys_id(text):
    """Generates a System ID: 'Tractors' -> 'CS_TRACTORS'"""
    if not text: return f"{USER_PREFIX}_UNKNOWN"
    # Clean string: Keep only alphanumeric, replace spaces with _
    clean = re.sub(r'[^a-zA-Z0-9]', '_', str(text).strip())
    # Remove duplicate underscores
    clean = re.sub(r'_+', '_', clean).strip('_')
    return f"{USER_PREFIX}_{clean}".upper()

def make_name(text):
    """Generates Display Name"""
    if not text: return f"Unknown - {USER_FULL_NAME}"
    return f"{str(text).strip()} - {USER_FULL_NAME}"

# --- MAIN LOGIC ---
def process_data():
    print(f"📂 Reading {INPUT_JSON_FILE}...")

    try:
        with open(INPUT_JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ ERROR: Could not find {INPUT_JSON_FILE}. Make sure it is in the same folder.")
        return

    products = []

    print(f"   Processing {len(data)} items...")

    # Iterate Data
    for item in data:
        title = item.get('title', 'Unknown')
        parent_name = item.get('parent', 'ROOT')
        depth = item.get('depth', 0)
        is_leaf = item.get('isLeaf', False)
        description = item.get('description', '')
        image_url = item.get('image', '') # EXTRACT IMAGE URL

        current_id = make_sys_id(title)

        # Determine Parent ID (Category Code)
        if parent_name in ["ROOT", "Home"]:
            parent_id = make_sys_id("Massey Ferguson")
        else:
            parent_id = make_sys_id(parent_name)

        # LOGIC: Treat as Product if it's a leaf node OR deep in the tree (Depth 3+)
        # Adjust 'depth' logic if your JSON structure is different
        is_product = is_leaf or depth >= 3

        if is_product:
            # --- CREATE PRODUCT ROW ---
            products.append({
                "Product Identifier": current_id, # Key for Import
                "System ID": current_id,
                "Product Name": make_name(title),
                "Category Code": parent_id,
                "Part Number": current_id,
                "Product Type": "Configurable",
                "Display Type": "Configuration",
                "Active": "TRUE",
                "Base Price": "50000", # Placeholder Price
                "Description": description[:255] if description else "",
                "Image File": image_url, # CPQ Import expects the URL here
                # Placeholder Attributes
                "Engine": "Standard Engine",
                "Transmission": "Standard Transmission"
            })

    # --- OUTPUT GENERATION ---
    if products:
        df = pd.DataFrame(products)

        # Reorder columns for a clean Excel template
        cols = [
            "Product Identifier", "System ID", "Product Name", "Category Code",
            "Part Number", "Product Type", "Display Type", "Active",
            "Base Price", "Image File", "Description", "Engine", "Transmission"
        ]

        # Ensure all columns exist
        for c in cols:
            if c not in df.columns: df[c] = ""

        df = df[cols]

        print(f"💾 Writing to {OUTPUT_EXCEL_FILE}...")
        df.to_excel(OUTPUT_EXCEL_FILE, index=False)
        print(f"✅ Success! Generated {OUTPUT_EXCEL_FILE} with {len(df)} products.")
        print("   -> You can now upload this file to SAP CPQ (Setup > Product Catalog > Bulk Import)")
    else:
        print("⚠️ No products found in JSON data. Check the depth/isLeaf logic.")

if __name__ == "__main__":
    process_data()