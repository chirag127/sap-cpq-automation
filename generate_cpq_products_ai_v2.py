import pandas as pd
import json
import re

# --- CONFIGURATION ---
INPUT_JSON_FILE = 'agco_complete_data.json'
OUTPUT_EXCEL_FILE = 'CPQ_Import_With_Paths.xlsx'
ROOT_NAME = "Massey Ferguson" # The top-level folder name in your catalog

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

# --- PATH BUILDER ---
def build_category_map(data):
    """Creates a lookup dictionary: {'CategoryName': 'ParentName'}"""
    parent_map = {}
    for item in data:
        name = item.get('title')
        parent = item.get('parent')
        if name and parent:
            parent_map[name] = parent
    return parent_map

def get_full_path(current_category, parent_map):
    """Recursively builds 'Root > Parent > Child' string"""
    path = []
    curr = current_category

    # Loop until we hit ROOT or a missing parent
    while curr and curr not in ["ROOT", "Home"]:
        path.insert(0, curr) # Add to front
        curr = parent_map.get(curr)

    # Prepend the Root Folder Name
    path.insert(0, ROOT_NAME)

    # Join with the specific CPQ separator
    return " > ".join(path)

# --- MAIN LOGIC ---
def process_data():
    print(f"📂 Reading {INPUT_JSON_FILE}...")
    try:
        with open(INPUT_JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        print("❌ File not found."); return

    # 1. Build Hierarchy Map
    parent_map = build_category_map(data)

    rows = []

    # 2. Process Items
    for item in data:
        title = item.get('title', 'Unknown')
        parent_name = item.get('parent', 'ROOT')
        depth = item.get('depth', 0)
        is_leaf = item.get('isLeaf', False)
        description = item.get('description', '')

        sys_id = make_sys_id(title)

        # Logic: Treat as Product if leaf or depth >= 3
        if is_leaf or depth >= 3:

            # CALCULATE FULL PATH
            # If parent is ROOT, path is just "Massey Ferguson"
            # If parent is "Tractors", path is "Massey Ferguson > Tractors"
            category_path = get_full_path(parent_name, parent_map)

            row = {
                "Product System ID": sys_id,
                "Product Name": make_name(title),
                "Part Number": sys_id,

                # FIX: Full Path String (e.g. "Massey Ferguson > Tractors")
                "Categories": category_path,

                "Product Type": "Configurable Product",
                "Display Type": "Configurable Product",
                "Active": "TRUE",
                "Price": "50000",
                "Description": description[:255] if description else title,
                "Unit Of Measure": "PC"
            }
            rows.append(row)

    # 3. Output
    if rows:
        df = pd.DataFrame(rows)
        # Reorder for neatness
        cols = ["Product System ID", "Product Name", "Categories", "Part Number",
                "Product Type", "Display Type", "Active", "Price", "Description", "Unit Of Measure"]
        df = df[cols]

        print(f"💾 Writing to {OUTPUT_EXCEL_FILE}...")
        df.to_excel(OUTPUT_EXCEL_FILE, index=False)
        print(f"✅ Success! Created {len(df)} products.")
        print("   -> 'Categories' column now contains full paths (e.g., 'Massey Ferguson > Tractors')")
    else:
        print("⚠️ No products found.")

if __name__ == "__main__":
    process_data()