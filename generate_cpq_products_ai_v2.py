import pandas as pd
import json
import re
import os

# --- CONFIGURATION ---
INPUT_JSON_FILE = 'agco_complete_data.json'
OUTPUT_EXCEL_FILE = 'Max_Columns_CPQ_Import_Fixed.xlsx'

# User Settings
USER_PREFIX = "CS"
USER_FULL_NAME = "Chirag Singhal"
DEFAULT_PRICE = "50000"

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

    # 1. Define Columns (FIXED: Changed 'Category' to 'Categories')
    all_columns = [
        "Product System ID", "Product Name", "Part Number", "Categories", # <--- FIXED
        "Product Type", "Display Type", "Active", "Price", "Description",
        "ID", "UPC", "MPN", "Product Family Code", "Image",
        "AlternativeText", "Cost", "Rank", "Weight", "Start Date",
        "End Date", "Quote Description", "Long Description", "Permissions",
        "UI type", "Recurring Price", "Recurring Cost", "Delete", "External Id",
        "Inventory", "Lead Time", "Product Version", "Pricing Mechanism", "Pricing Code",
        "Is Synced From Back Office", "Order Item Type", "Auto Renewal Indicator",
        "Unit Of Measure", "General Item Category Group", "S/4 Subscription Item Category Type",
        "User can enter quantity", "End of Life Status", "Replacement Product",
        "Created By", "Date Created", "Modified By", "Modified Date",
        "shipp::Express", "shipp::Express Shipping", "shipp::Standard", "shipp::Standard Shipping",
        "Status"
    ]

    rows = []

    # 2. Iterate JSON Data
    for item in data:
        title = item.get('title', 'Unknown')
        parent_name = item.get('parent', 'ROOT')
        depth = item.get('depth', 0)
        is_leaf = item.get('isLeaf', False)
        description = item.get('description', '')
        image_url = item.get('image', '')

        sys_id = make_sys_id(title)

        # Determine Category Code (Parent)
        if parent_name in ["ROOT", "Home"]:
            cat_code = make_sys_id("Massey Ferguson")
        else:
            cat_code = make_sys_id(parent_name)

        # Logic: Is this a Product?
        if is_leaf or depth >= 3:

            # 3. Map Data to Columns
            row = {col: "" for col in all_columns} # Initialize all empty

            # Core Identity
            row["Product System ID"] = sys_id
            row["Part Number"] = sys_id
            row["Product Name"] = make_name(title)
            row["Categories"] = cat_code  # <--- Mapped to new column name

            # Details
            row["Description"] = description[:255] if description else title
            row["Long Description"] = description
            row["Quote Description"] = f"{title} - Configurable Tractor"
            row["Image"] = image_url

            # Configuration Settings
            row["Product Type"] = "Configurable"
            row["Display Type"] = "Configuration" # CPQ often expects "Configuration" or "1"
            row["UI type"] = "Configuration"
            row["Active"] = "TRUE"

            # Pricing & Logistics
            row["Price"] = DEFAULT_PRICE
            row["Cost"] = "35000"
            row["Pricing Mechanism"] = "Custom Pricing"
            row["Unit Of Measure"] = "PC"
            row["User can enter quantity"] = "TRUE"

            # Defaults
            row["Rank"] = "1"
            row["Weight"] = "1000"
            row["Delete"] = "FALSE"
            row["Is Synced From Back Office"] = "FALSE"

            rows.append(row)

    # --- 3. OUTPUT GENERATION ---
    if rows:
        df = pd.DataFrame(rows)
        df = df[all_columns] # Enforce order

        print(f"💾 Writing to {OUTPUT_EXCEL_FILE}...")
        df.to_excel(OUTPUT_EXCEL_FILE, index=False)
        print(f"✅ Success! Generated {OUTPUT_EXCEL_FILE} with {len(df)} products.")
        print("   -> 'Category' column renamed to 'Categories'. Try uploading this file.")
    else:
        print("⚠️ No products found in JSON data.")

if __name__ == "__main__":
    process_data()