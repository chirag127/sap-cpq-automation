import pandas as pd
import json
import re
import os

# --- CONFIGURATION ---
INPUT_JSON = 'agco_complete_data.json'
CAT_OUTPUT_FILE = '1_Upload_Categories_CS.xlsx'
PROD_OUTPUT_FILE = '2_Upload_Products_CS.xlsx'

USER_INITIALS = "CS"
USER_FULL_NAME = "Chirag Singhal"

# --- HELPER FUNCTIONS ---
def make_sys_id(text):
    """Generates a System ID: 'Tractors' -> 'CS_TRACTORS'"""
    if not text: return f"{USER_INITIALS}_UNKNOWN"
    # Remove special chars and spaces, keep alphanumerics
    clean = re.sub(r'[^a-zA-Z0-9]', '_', str(text).strip())
    # Remove duplicate underscores
    clean = re.sub(r'_+', '_', clean)
    # Remove leading/trailing underscores
    clean = clean.strip('_')
    return f"{USER_INITIALS}_{clean}".upper()

def make_name(text):
    """Generates Display Name: 'Tractors - Chirag Singhal'"""
    if not text: return f"Unknown - {USER_FULL_NAME}"
    return f"{str(text).strip()} - {USER_FULL_NAME}"

# --- MAIN LOGIC ---
def process_data():
    print(f"Reading {INPUT_JSON}...")

    try:
        with open(INPUT_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Could not find {INPUT_JSON}. Make sure the file exists.")
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
        description = item.get('description', '')

        current_id = make_sys_id(title)

        # Determine Parent ID
        if parent_name == "ROOT" or parent_name == "Home":
            parent_id = root_id
        else:
            parent_id = make_sys_id(parent_name)

        # --- SMART LOGIC: Determine Category vs Product ---
        # Rule: If depth is 3 or greater, OR isLeaf is true -> It's a Product
        # Hierarchy: 0=Brand, 1=Category(Tractors), 2=Series(MF 4700), 3=Model(MF 4708)

        is_product = is_leaf or depth >= 3

        if is_product:
            # --- CREATE PRODUCT ---

            # Ensure unique Part Number (Some models might appear in multiple lists)
            if any(p['Part Number'] == current_id for p in products):
                continue # Skip duplicate

            products.append({
                "System ID": current_id,
                "Product Name": make_name(title),
                "Category Code": parent_id, # Link to parent folder
                "Part Number": current_id,
                "Product Type": "Configurable", # Critical for CPQ
                "Display Type": "Configuration",
                "Active": "TRUE",
                "Description": description[:255] if description else f"Scraped Model: {title}"
            })

            # Safety: Ensure the parent category exists
            # (If scraper missed the Category page but found the Product page)
            if parent_id not in categories and parent_name != "ROOT":
                categories[parent_id] = {
                    "Category Code": parent_id,
                    "Parent Category Code": root_id, # Default to root if grandparent unknown
                    "Name": make_name(parent_name),
                    "Description": "Auto-generated Parent Category",
                    "Active": "TRUE"
                }

        else:
            # --- CREATE CATEGORY ---
            if current_id not in categories:
                categories[current_id] = {
                    "Category Code": current_id,
                    "Parent Category Code": parent_id,
                    "Name": make_name(title),
                    "Description": description[:255] if description else f"Level {depth} Category",
                    "Active": "TRUE"
                }

    # --- OUTPUT GENERATION ---

    # 1. Categories Excel
    cat_df = pd.DataFrame(list(categories.values()))

    # Ensure correct columns for CPQ Import
    cat_cols = ["Category Code", "Parent Category Code", "Name", "Description", "Active"]
    for c in cat_cols:
        if c not in cat_df.columns: cat_df[c] = ""
    cat_df = cat_df[cat_cols]

    cat_df.to_excel(CAT_OUTPUT_FILE, index=False)
    print(f"✅ Generated {CAT_OUTPUT_FILE} ({len(cat_df)} Categories)")

    # 2. Products Excel
    if products:
        prod_df = pd.DataFrame(products)

        # Ensure correct columns for CPQ Import
        prod_cols = ["System ID", "Product Name", "Category Code", "Part Number", "Product Type", "Display Type", "Active", "Description"]
        for c in prod_cols:
            if c not in prod_df.columns: prod_df[c] = ""
        prod_df = prod_df[prod_cols]

        prod_df.to_excel(PROD_OUTPUT_FILE, index=False)
        print(f"✅ Generated {PROD_OUTPUT_FILE} ({len(prod_df)} Products)")
    else:
        print("⚠️ No products found. Check scraper depth logic.")

if __name__ == "__main__":
    process_data()