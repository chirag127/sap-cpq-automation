import pandas as pd
import json
import re
import os

# --- CONFIGURATION ---
INPUT_JSON = 'agco_complete_data.json' # Make sure this matches your scraper output file name

# Output files
CAT_OUTPUT_FILE = '1_Upload_Categories_Chirag.xlsx'
PROD_OUTPUT_FILE = '2_Upload_Products_Chirag.xlsx'

# Naming Convention
USER_PREFIX = "CS"
USER_FULL_NAME = "Chirag Singhal"

# --- HELPER FUNCTIONS ---
def make_sys_id(text):
    """Generates a System ID like 'CHIRAG_TRACTORS'"""
    if not text: return f"{USER_PREFIX}_UNKNOWN"

    # Remove special chars and spaces
    clean = re.sub(r'[^a-zA-Z0-9]', '_', str(text).strip())
    # Remove duplicate underscores
    clean = re.sub(r'_+', '_', clean)
    clean = clean.strip('_')

    return f"{USER_PREFIX}_{clean}".upper()

def make_name(text):
    """Generates Display Name like 'Chirag Singhal - Tractors'"""
    if not text: return f"{USER_FULL_NAME} - Unknown"
    return f"{USER_FULL_NAME} - {str(text).strip()}"

# --- MAIN LOGIC ---
def process_data():
    print(f"Reading {INPUT_JSON}...")

    try:
        with open(INPUT_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Could not find {INPUT_JSON}. Run the scraper first.")
        return

    print(f"Processing {len(data)} items...")

    categories = {}
    products = []

    # 1. Initialize Root Category
    root_id = make_sys_id("Massey Ferguson")
    categories[root_id] = {
        "Category Code": root_id,
        "Parent Category Code": "",
        "Name": make_name("Massey Ferguson"),
        "Description": "Root Catalog",
        "Active": "TRUE"
    }

    # 2. Iterate Data
    for item in data:
        title = item.get('title', 'Unknown')
        parent_name = item.get('parent', 'ROOT')
        depth = item.get('depth', 0)
        is_leaf = item.get('isLeaf', False)

        # Clean Description: Use real text or empty (looks manual)
        raw_desc = item.get('description', '')
        description = raw_desc[:255] if raw_desc else ""

        current_id = make_sys_id(title)

        # Determine Parent ID
        if parent_name == "ROOT" or parent_name == "Home":
            parent_id = root_id
        else:
            parent_id = make_sys_id(parent_name)

        # Logic: Depth >= 3 or isLeaf = Product
        is_product = is_leaf or depth >= 3

        if not is_product:
            # --- CREATE CATEGORY ---
            if current_id not in categories:
                categories[current_id] = {
                    "Category Code": current_id,
                    "Parent Category Code": parent_id,
                    "Name": make_name(title),
                    "Description": description, # Clean text
                    "Active": "TRUE"
                }
        else:
            # --- CREATE PRODUCT ---
            # Dedup check
            if not any(p['Part Number'] == current_id for p in products):
                products.append({
                    "Product Identifier": current_id, # PRIMARY KEY for Import
                    "System ID": current_id,          # Backup Key
                    "Product Name": make_name(title),
                    "Category Code": parent_id,
                    "Part Number": current_id,
                    "Product Type": "Configurable",
                    "Display Type": "Configuration",
                    "Active": "TRUE",
                    "Description": description
                })

            # Safety: Create Parent Category if missing
            if parent_id not in categories and parent_name != "ROOT":
                categories[parent_id] = {
                    "Category Code": parent_id,
                    "Parent Category Code": root_id,
                    "Name": make_name(parent_name),
                    "Description": "",
                    "Active": "TRUE"
                }

    # --- OUTPUT GENERATION ---

    # 1. Categories Excel
    cat_df = pd.DataFrame(list(categories.values()))
    cat_cols = ["Category Code", "Parent Category Code", "Name", "Description", "Active"]
    # Add missing columns
    for c in cat_cols:
        if c not in cat_df.columns: cat_df[c] = ""
    cat_df = cat_df[cat_cols]

    cat_df.to_excel(CAT_OUTPUT_FILE, index=False)
    print(f"✅ Generated {CAT_OUTPUT_FILE} ({len(cat_df)} Categories)")

    # 2. Products Excel
    if products:
        prod_df = pd.DataFrame(products)

        # Exact column order for CPQ Import
        prod_cols = ["Product Identifier", "System ID", "Product Name", "Category Code", "Part Number", "Product Type", "Display Type", "Active", "Description"]
        for c in prod_cols:
            if c not in prod_df.columns: prod_df[c] = ""
        prod_df = prod_df[prod_cols]

        prod_df.to_excel(PROD_OUTPUT_FILE, index=False)
        print(f"✅ Generated {PROD_OUTPUT_FILE} ({len(prod_df)} Products)")
    else:
        print("⚠️ No products found in JSON data.")

if __name__ == "__main__":
    process_data()