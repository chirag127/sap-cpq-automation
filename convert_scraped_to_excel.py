import pandas as pd
import json
import re
import os

# --- CONFIGURATION ---
INPUT_JSON = 'agco_complete_data.json' # Ensure this matches your scraper output

# Output files now have 'Chirag' in the name
CAT_OUTPUT_FILE = '1_Upload_Categories_Chirag.xlsx'
PROD_OUTPUT_FILE = '2_Upload_Products_Chirag.xlsx'

# Changed from "CS" to "CHIRAG" as requested
USER_PREFIX = "CS"
USER_FULL_NAME = "Chirag Singhal"

# --- HELPER FUNCTIONS ---
def make_sys_id(text):
    """
    Generates a System ID prefixed with CHIRAG.
    Example: 'Tractors' -> 'CHIRAG_TRACTORS'
    """
    if not text: return f"{USER_PREFIX}_UNKNOWN"

    # Remove special chars and spaces, keep alphanumerics
    clean = re.sub(r'[^a-zA-Z0-9]', '_', str(text).strip())
    # Remove duplicate underscores
    clean = re.sub(r'_+', '_', clean)
    # Remove leading/trailing underscores
    clean = clean.strip('_')

    # Prepend CHIRAG
    return f"{USER_PREFIX}_{clean}".upper()

def make_name(text):
    """
    Generates Display Name prefixed with Chirag Singhal.
    Example: 'Tractors' -> 'Chirag Singhal - Tractors'
    """
    if not text: return f"{USER_FULL_NAME} - Unknown"
    # Prepend Name
    return f"{USER_FULL_NAME} - {str(text).strip()}"

# --- MAIN LOGIC ---
def process_data():
    print(f"Reading {INPUT_JSON}...")

    try:
        with open(INPUT_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Could not find {INPUT_JSON}. Did you run the scraper?")
        print(f"Current working directory: {os.getcwd()}")
        return

    print(f"Processing {len(data)} items...")

    categories = {}
    products = []

    # 1. First Pass: Identify Root Category
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

        # LOGIC:
        # If it is a leaf node (Model) OR Depth >= 3, treat as Product.
        # Otherwise, treat as Category.

        is_product = is_leaf or depth >= 3

        if not is_product:
            # --- CREATE CATEGORY ---
            if current_id not in categories:
                categories[current_id] = {
                    "Category Code": current_id,
                    "Parent Category Code": parent_id,
                    "Name": make_name(title),
                    "Description": description[:255] if description else f"Level {depth} Category",
                    "Active": "TRUE"
                }
        else:
            # --- CREATE PRODUCT ---
            # Dedup check
            if not any(p['Part Number'] == current_id for p in products):
                products.append({
                    "System ID": current_id,
                    "Product Name": make_name(title),
                    "Category Code": parent_id, # Link to parent folder
                    "Part Number": current_id,
                    "Product Type": "Configurable",
                    "Display Type": "Configuration",
                    "Active": "TRUE",
                    "Description": description[:255] if description else "Scraped Product"
                })

            # Safety: Ensure the parent category exists
            if parent_id not in categories and parent_name != "ROOT":
                categories[parent_id] = {
                    "Category Code": parent_id,
                    "Parent Category Code": root_id,
                    "Name": make_name(parent_name),
                    "Description": "Auto-generated Parent Category",
                    "Active": "TRUE"
                }

    # --- OUTPUT GENERATION ---

    # 1. Categories Excel
    cat_df = pd.DataFrame(list(categories.values()))

    cat_cols = ["Category Code", "Parent Category Code", "Name", "Description", "Active"]
    for c in cat_cols:
        if c not in cat_df.columns: cat_df[c] = ""
    cat_df = cat_df[cat_cols]

    cat_df.to_excel(CAT_OUTPUT_FILE, index=False)
    print(f"✅ Generated {CAT_OUTPUT_FILE} ({len(cat_df)} Categories)")

    # 2. Products Excel
    if products:
        prod_df = pd.DataFrame(products)

        prod_cols = ["System ID", "Product Name", "Category Code", "Part Number", "Product Type", "Display Type", "Active", "Description"]
        for c in prod_cols:
            if c not in prod_df.columns: prod_df[c] = ""
        prod_df = prod_df[prod_cols]

        prod_df.to_excel(PROD_OUTPUT_FILE, index=False)
        print(f"✅ Generated {PROD_OUTPUT_FILE} ({len(prod_df)} Products)")
    else:
        print("⚠️ No products found in JSON data.")

if __name__ == "__main__":
    process_data()