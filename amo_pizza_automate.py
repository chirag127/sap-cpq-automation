import requests
import json
import time
import sys

# --- CONFIGURATION ---
# SAP CPQ Base URL and Credentials (Hardcoded as per request - one-time use only)
CPQ_BASE_URL = "https://tataconsultancyservices-partner1.cpq.cloud.sap"
TOKEN_URL = f"{CPQ_BASE_URL}/basic/api/token"

# API Endpoints (Based on standard SAP CPQ REST APIs)
CAT_API = f"{CPQ_BASE_URL}/api/products/v1/categories"
PROD_API = f"{CPQ_BASE_URL}/api/products/v1/products"
ATTR_API = f"{CPQ_BASE_URL}/api/products/v1/attributes"
RULE_API = f"{CPQ_BASE_URL}/api/products/v1/rules"
MARKET_API = f"{CPQ_BASE_URL}/api/pricing/v1/markets"  # For creating markets if needed
PRICING_TABLE_API = f"{CPQ_BASE_URL}/api/pricing/v1/pricingTables"  # For custom pricing tables
PRICING_ENTRY_API = f"{CPQ_BASE_URL}/api/pricing/v1/pricingTableEntries"  # For entries in tables
FILES_API = f"{CPQ_BASE_URL}/api/files/v1/files"  # For true image uploads (extended but commented out; manual if needed)

CPQ_USERNAME = "REDACTED_CPQ_USERNAME<=="  # Username only
CPQ_DOMAIN = "TATACONSULTANCYSERVICESLIMITED_PARTNER1"
CPQ_PASSWORD = "REDACTED_CPQ_PASSWORD<=="  # Hardcoded password as per request

EMP_ID = "2800815"  # Your emp ID for naming

# Token Management
current_token = None
last_token_time = 0
TOKEN_LIFETIME = 240  # Refresh 10s before 250s expiry

# Pricing Data (Hardcoded from PDF - USD prices; CAD = 1.1 * USD)
PRICING_DATA = [
    {"part_number": "BX001", "description": "Gift box packing", "price_usd": 1, "price_cad": 1.1},
    {"part_number": "PZ_SmTh", "description": "Small Thin Crust Pizza", "price_usd": 10, "price_cad": 11},
    {"part_number": "PZ_MdTh", "description": "Medium Thin Crust Pizza", "price_usd": 12, "price_cad": 13.2},
    {"part_number": "PZ_MdDd", "description": "Medium Deep Dish Pizza", "price_usd": 15, "price_cad": 16.5},
    {"part_number": "PZ_LgTh", "description": "Large Thin Crust Pizza", "price_usd": 17, "price_cad": 18.7},
    {"part_number": "PZ_LgDd", "description": "Large Deep Dish Pizza", "price_usd": 20, "price_cad": 22},
    {"part_number": "TP001", "description": "Add Sausage", "price_usd": 1, "price_cad": 1.1},
    {"part_number": "TP002", "description": "Add Pepperoni", "price_usd": 1, "price_cad": 1.1},
    {"part_number": "TP003", "description": "Add Green Pepper", "price_usd": 1, "price_cad": 1.1},
    {"part_number": "TP004", "description": "Add Onion", "price_usd": 1, "price_cad": 1.1},
    {"part_number": "TP005", "description": "Add Mushrooms", "price_usd": 1, "price_cad": 1.1},
    {"part_number": "TP006", "description": "Add Anchovy", "price_usd": 1, "price_cad": 1.1},
    {"part_number": "ICC001", "description": "Small Ice Cream Cone with nuts", "price_usd": 1.25, "price_cad": 1.375},
    {"part_number": "ICC002", "description": "Small Ice Cream Cone without nuts", "price_usd": 1, "price_cad": 1.1},
    {"part_number": "HFS001", "description": "Small Hot Fudge Sundae with nuts", "price_usd": 1.75, "price_cad": 1.925},
    {"part_number": "HFS002", "description": "Small Hot Fudge Sundae without nuts", "price_usd": 1.5, "price_cad": 1.65},
    {"part_number": "MS001", "description": "Small Milkshake with nuts", "price_usd": 1.5, "price_cad": 1.65},
    {"part_number": "MS002", "description": "Small Milkshake without nuts", "price_usd": 1.25, "price_cad": 1.375},
    {"part_number": "YP001", "description": "Small Yogurt Parfait with nuts", "price_usd": 1.5, "price_cad": 1.65},
    {"part_number": "YP002", "description": "Small Yogurt Parfait without nuts", "price_usd": 1.25, "price_cad": 1.375},
    {"part_number": "CTL001", "description": "Small Chai Tea Latte with nuts", "price_usd": 1.5, "price_cad": 1.65},
    {"part_number": "CTL002", "description": "Small Chai Tea Latte without nuts", "price_usd": 1.25, "price_cad": 1.375},
    {"part_number": "ICC003", "description": "Medium Ice Cream Cone with nuts", "price_usd": 1.75, "price_cad": 1.925},
    {"part_number": "ICC004", "description": "Medium Ice Cream Cone without nuts", "price_usd": 1.5, "price_cad": 1.65},
    {"part_number": "HFS003", "description": "Medium Hot Fudge Sundae with nuts", "price_usd": 2.25, "price_cad": 2.475},
    {"part_number": "HFS004", "description": "Medium Hot Fudge Sundae without nuts", "price_usd": 2, "price_cad": 2.2},
    {"part_number": "MS003", "description": "Medium Milkshake with nuts", "price_usd": 2, "price_cad": 2.2},
    {"part_number": "MS004", "description": "Medium Milkshake without nuts", "price_usd": 1.75, "price_cad": 1.925},
    {"part_number": "YP003", "description": "Medium Yogurt Parfait with nuts", "price_usd": 2, "price_cad": 2.2},
    {"part_number": "YP004", "description": "Medium Yogurt Parfait without nuts", "price_usd": 1.75, "price_cad": 1.925},
    {"part_number": "CTL003", "description": "Medium Chai Tea Latte with nuts", "price_usd": 2, "price_cad": 2.2},
    {"part_number": "CTL004", "description": "Medium Chai Tea Latte without nuts", "price_usd": 1.75, "price_cad": 1.925},
    {"part_number": "ICC005", "description": "Large Ice Cream Cone with nuts", "price_usd": 2.25, "price_cad": 2.475},
    {"part_number": "ICC006", "description": "Large Ice Cream Cone without nuts", "price_usd": 2, "price_cad": 2.2},
    {"part_number": "HFS005", "description": "Large Hot Fudge Sundae with nuts", "price_usd": 2.75, "price_cad": 3.025},
    {"part_number": "HFS006", "description": "Large Hot Fudge Sundae without nuts", "price_usd": 2.5, "price_cad": 2.75},
    {"part_number": "MS005", "description": "Large Milkshake with nuts", "price_usd": 2.5, "price_cad": 2.75},
    {"part_number": "MS006", "description": "Large Milkshake without nuts", "price_usd": 2.25, "price_cad": 2.475},
    {"part_number": "YP005", "description": "Large Yogurt Parfait with nuts", "price_usd": 2.5, "price_cad": 2.75},
    {"part_number": "YP006", "description": "Large Yogurt Parfait without nuts", "price_usd": 2.25, "price_cad": 2.475},
    {"part_number": "CTL005", "description": "Large Chai Tea Latte with nuts", "price_usd": 2.5, "price_cad": 2.75},
    {"part_number": "CTL006", "description": "Large Chai Tea Latte without nuts", "price_usd": 2.25, "price_cad": 2.475},
]

# Attribute Definitions (From PDF, with EMP_ID suffix)
ATTRIBUTES = [
    {"name": f"Size_{EMP_ID}", "data_type": "Text", "attr_type": "SingleSelectMenu", "menu_options": "Small,Medium,Large", "default": "Small", "image_menu": True},
    {"name": f"Crust Type_{EMP_ID}", "data_type": "Text", "attr_type": "SingleSelectMenu", "menu_options": "Thin Crust,Deep Dish", "default": "Thin Crust", "image_menu": True},
    {"name": f"Specialty_{EMP_ID}", "data_type": "Text", "attr_type": "SingleSelectMenu", "menu_options": "Custom Pizza,Meat Lovers,The Works", "default": "Custom Pizza", "image_menu": True},
    {"name": f"Toppings_{EMP_ID}", "data_type": "Text", "attr_type": "MultiSelectMenu", "menu_options": "Sausage,Pepperoni,Green Peppers,Onion,Mushrooms,Anchovy", "default": None, "image_menu": True},
    {"name": f"Include Desserts_{EMP_ID}", "data_type": "Boolean", "attr_type": None, "menu_options": None, "default": "False", "image_menu": False},
    # Container/Array Attributes
    {"name": f"Number of Desserts_{EMP_ID}", "data_type": "Integer", "attr_type": "TextField", "menu_options": None, "default": "1", "array_type": "NO", "array_control": True},
    {"name": f"Dessert Type_{EMP_ID}", "data_type": "Text", "attr_type": "SingleSelectMenu", "menu_options": "Ice Cream Cone,Hot Fudge Sundae,Milkshake,Yogurt Parfait,Chai Tea Latte", "default": None, "array_type": "YES", "array_control": False},
    {"name": f"Dessert Size_{EMP_ID}", "data_type": "Text", "attr_type": "SingleSelectMenu", "menu_options": "Small,Medium,Large", "default": None, "array_type": "YES", "array_control": False},
    # Container
    {"name": f"Dessert Options_{EMP_ID}", "data_type": "Container", "included_attrs": [f"Dessert Type_{EMP_ID}", f"Dessert Size_{EMP_ID}"], "array_control_attr": f"Number of Desserts_{EMP_ID}"},
]

# Rules Definitions (From PDF, with EMP_ID suffix)
RULES = [
    {"name": f"Constrain Size by Crust Type_{EMP_ID}", "type": "Constraint", "condition": "Size is Small", "action": "Do not allow Deep Dish as a selection for Crust Type", "message": "Deep Dish Not Available in Size Small"},
    {"name": f"Specialty Meat Lovers_{EMP_ID}", "type": "Recommendation", "condition": "Specialty is Meat Lovers", "action": "Force Set Toppings to Sausage and Pepperoni", "message": None},
    {"name": f"Specialty The Works_{EMP_ID}", "type": "Recommendation", "condition": "Specialty is The Works", "action": "Force Set Toppings to Sausage, Pepperoni, Green Peppers, Onion, and Mushrooms", "message": None},
    {"name": f"Hide Dessert Options_{EMP_ID}", "type": "HidingAttributes", "condition": "Include Desserts is False", "action": "Hide Number of Desserts, Dessert Type, and Dessert Size", "message": None},
]

# --- TOKEN MANAGEMENT ---
def refresh_token_if_needed():
    global current_token, last_token_time
    if time.time() - last_token_time > TOKEN_LIFETIME:
        print("🔄 Refreshing token...")
        current_token = get_token()
        last_token_time = time.time()
    return current_token

def get_token():
    print("🔑 Authenticating...")
    payload = {
        'grant_type': 'password',
        'username': CPQ_USERNAME,
        'password': CPQ_PASSWORD,
        'domain': CPQ_DOMAIN
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    try:
        resp = requests.post(TOKEN_URL, data=payload, headers=headers)
        if resp.status_code != 200:
            print(f"❌ Auth Failed ({resp.status_code}): {resp.text}")
            sys.exit(1)
        token = resp.json()['access_token']
        global last_token_time
        last_token_time = time.time()
        return token
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        sys.exit(1)

# --- IMAGE HANDLING (Placeholders Only - Google Removed; Upload Extension Commented) ---
def get_image_url(entity_name, entity_type="product"):
    # Simplified: Always use placeholder (reliable, no API issues)
    # For true bulk upload: Uncomment below and provide local image files or URLs to fetch/upload
    query = entity_name.replace(f"_{EMP_ID}", "").replace(" ", "+")
    print(f"   🖼️  Generating placeholder for '{entity_name}'")

    # Placeholder URL
    safe_text = query[:20]  # Truncate for readability
    return f"https://placehold.co/800x600/EFEFEF/A6192E/png?text={safe_text}"

    # Extension for True Uploads (Manual Prep: Download images to local dir, then upload)
    # Example: Assume local images in ./images/ folder named like 'small_pizza.jpg'
    # image_path = f"./images/{entity_name.lower().replace(' ', '_')}.jpg"
    # if os.path.exists(image_path):
    #     with open(image_path, 'rb') as f:
    #         files = {'file': f}
    #         upload_resp = requests.post(FILES_API, headers={'Authorization': f'Bearer {current_token}'}, files=files)
    #         if upload_resp.status_code == 201:
    #             file_id = upload_resp.json().get('Id')
    #             return f"{CPQ_BASE_URL}/api/files/v1/files({file_id})/content"  # Or use FileId in payloads
    # else:
    #     print(f"   ⚠️  No local image for {entity_name}; using placeholder")
    #     return get_placeholder_url(entity_name)

# --- API HELPER WITH TOKEN REFRESH ---
def api_call(method, url, headers, **kwargs):
    refresh_token_if_needed()
    auth_header = {'Authorization': f'Bearer {current_token}'}
    full_headers = {**headers, **auth_header}
    if method.upper() == 'GET':
        resp = requests.get(url, headers=full_headers, **kwargs)
    elif method.upper() == 'POST':
        resp = requests.post(url, headers=full_headers, **kwargs)
    elif method.upper() == 'PUT':
        resp = requests.put(url, headers=full_headers, **kwargs)
    else:
        raise ValueError("Unsupported method")
    return resp

# --- 3. CREATE OR FIND ENTITY (Generic Helper) ---
def create_or_find(headers, api_url, payload, find_key="Name", find_value=None):
    if find_value is None:
        find_value = payload.get(find_key, "")

    # First, try to find existing (use api_call for refresh)
    search_resp = api_call('GET', api_url, headers)
    if search_resp.status_code == 200:
        existing = search_resp.json()
        existing_list = existing if isinstance(existing, list) else existing.get('Items', []) or existing.get('Value', [])
        for item in existing_list:
            if str(item.get(find_key, "")).strip() == str(find_value).strip():
                print(f"   🎯 Found existing: {find_value}")
                return item.get('Id')

    # Create if not found
    print(f"   ➕ Creating: {find_value}")
    create_resp = api_call('POST', api_url, headers, json=payload)
    if create_resp.status_code in [200, 201]:
        new_id = create_resp.json().get('Id')
        print(f"   ✅ Created ID: {new_id}")
        return new_id
    else:
        print(f"   ❌ Create Failed: {create_resp.text}")
        return None

# --- 4. MAIN AUTOMATION STEPS ---
def run_automation():
    global current_token
    current_token = get_token()
    headers = {'Content-Type': 'application/json'}

    created_ids = {}  # Track IDs for associations

    # Step 1: Create Categories and Product (Practice 8-1)
    print("\n🍕 Step 1: Defining Configurable Product Structure")

    # Main Category: "Amo la Pizza"
    main_cat_payload = {"Name": "Amo la Pizza", "ImageUrl": get_image_url("Amo la Pizza", "pizza category")}
    cat_id = create_or_find(headers, CAT_API, main_cat_payload)
    if cat_id:
        created_ids['main_cat'] = cat_id

    # Subcategory: "Pizza Menu_2800815" (child of main_cat)
    sub_cat_payload = {"Name": f"Pizza Menu_{EMP_ID}", "ParentId": cat_id, "ImageUrl": get_image_url(f"Pizza Menu_{EMP_ID}")}
    sub_cat_id = create_or_find(headers, CAT_API, sub_cat_payload)
    if sub_cat_id:
        created_ids['sub_cat'] = sub_cat_id

    # Product: "Pizza Order_2800815", Type: "Accessories", Base Price: 0, Category: sub_cat
    prod_payload = {
        "Name": f"Pizza Order_{EMP_ID}",
        "ProductType": "Accessories",
        "BasePrice": 0,
        "CategoryId": sub_cat_id,
        "ImageUrl": get_image_url(f"Pizza Order_{EMP_ID}", "product")
    }
    prod_id = create_or_find(headers, PROD_API, prod_payload, "Name", f"Pizza Order_{EMP_ID}")
    if prod_id:
        created_ids['product'] = prod_id

    # Step 2: Add Attributes (Practice 8-2 & 8-3)
    print("\n⚙️ Step 2: Adding Configurable & Container Attributes")
    attr_ids = {}
    for attr in ATTRIBUTES:
        attr_payload = {
            "Name": attr["name"],
            "DataType": attr["data_type"],
            "AttributeType": attr["attr_type"],
            "MenuOptions": attr["menu_options"],
            "DefaultValue": attr["default"],
            "ImageMenu": attr["image_menu"],
            "ProductId": prod_id,  # Associate to product
            "ArrayType": attr.get("array_type"),
            "ArrayControl": attr.get("array_control", False)
        }
        if "Container" in attr["data_type"]:
            attr_payload["IncludedAttributes"] = attr["included_attrs"]
            attr_payload["ArrayControlAttribute"] = attr["array_control_attr"]
        attr_id = create_or_find(headers, ATTR_API, attr_payload)
        if attr_id:
            attr_ids[attr["name"]] = attr_id

    # Step 3: Add Rules (Practice 8-5)
    print("\n📋 Step 3: Adding Configuration Rules")
    for rule in RULES:
        rule_payload = {
            "Name": rule["name"],
            "RuleType": rule["type"],
            "Condition": rule["condition"],
            "Action": rule["action"],
            "Message": rule["message"],
            "ProductId": prod_id  # Associate to product
        }
        rule_id = create_or_find(headers, RULE_API, rule_payload)
        if rule_id:
            print(f"   ✅ Rule Created: {rule['name']}")

    # Step 4: Add Pricing Table & Entries (Practice 8-6)
    print("\n💰 Step 4: Adding Table-Based Pricing")

    # Create Market for CAD if needed (assume USD exists)
    cad_market_payload = {"Name": "CAD", "Currency": "CAD"}
    market_id = create_or_find(headers, MARKET_API, cad_market_payload, "Name", "CAD")
    if market_id:
        created_ids['cad_market'] = market_id

    # Create Custom Pricing Table
    table_payload = {"Name": f"Amo La Pizza Pricing_{EMP_ID}", "Description": "Custom pricing for pizza config"}
    table_id = create_or_find(headers, PRICING_TABLE_API, table_payload)
    if table_id:
        print(f"   📊 Pricing Table ID: {table_id}")

        # Add Entries
        for entry in PRICING_DATA:
            entry_payload = {
                "PartNumber": entry["part_number"],
                "Description": entry["description"],
                "PricingTableId": table_id,
                "Prices": [
                    {"MarketId": 1, "Price": entry["price_usd"]}  # Assume USD Market ID=1; adjust if needed
                ]
            }
            if market_id:
                entry_payload["Prices"].append({"MarketId": market_id, "Price": entry["price_cad"]})
            entry_resp = api_call('POST', PRICING_ENTRY_API, headers, json=entry_payload)
            if entry_resp.status_code in [200, 201]:
                print(f"   💵 Entry Added: {entry['part_number']}")

    # Step 5: Layout (Practice 8-4) - MANUAL STEP (API limited; use UI for drag-drop)
    print("\n🎨 Step 5: Creating Layout - MANUAL REQUIRED")
    print("   ⚠️  Layout configuration (e.g., grid positions for attributes/images) is UI-based in CPQ.")
    print("   Go to CPQ UI > Products > Pizza Order_2800815 > Layout Editor.")
    print("   Drag attributes to match screenshot: Size/Crust/Toppings/Desserts in grids.")
    print("   Associate images via Attribute settings (ImageMenu=True set; placeholders used).")
    print("   For attribute option images (e.g., Small pizza icon): Manually upload per option in UI if placeholders insufficient.")

    # Bulk Image Import Note: Placeholders used for product/category ImageUrl. For attribute grids:
    # - UI: Edit Attribute > Menu Options > Add Image URLs per option (e.g., https://placehold.co/... for 'Small').
    # - True Uploads: Prep local images, uncomment get_image_url upload logic, run script to POST to /api/files/v1/files.

    print("\n✅ Automation Complete! Check CPQ UI for verification. Manual: Only Layout & Fine-Tune Images.")

if __name__ == "__main__":
    run_automation()