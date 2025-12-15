import requests
import json
import time
import sys
import logging
from datetime import datetime
from urllib.parse import urljoin

# --- LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Reduce noise from urllib3
logging.getLogger("urllib3").setLevel(logging.WARNING)

# --- REQUEST/RESPONSE LOGGING ---
def log_request(method, url, headers, body=None):
    """Log outgoing request details"""
    logger.info(f"{'='*60}")
    logger.info(f"📤 REQUEST: {method.upper()} {url}")
    logger.debug(f"   Headers: {json.dumps({k: v[:50] + '...' if len(str(v)) > 50 else v for k, v in headers.items()}, indent=2)}")
    if body:
        body_str = json.dumps(body, indent=2) if isinstance(body, dict) else str(body)
        logger.debug(f"   Body: {body_str[:500]}{'...' if len(body_str) > 500 else ''}")

def log_response(resp, elapsed_time=None):
    """Log incoming response details"""
    status_emoji = "✅" if resp.status_code in [200, 201] else "⚠️" if resp.status_code < 400 else "❌"
    logger.info(f"📥 RESPONSE: {status_emoji} {resp.status_code} {resp.reason}")
    if elapsed_time:
        logger.debug(f"   Elapsed: {elapsed_time:.2f}s")
    logger.debug(f"   Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
    try:
        resp_text = resp.text[:1000] if len(resp.text) > 1000 else resp.text
        logger.debug(f"   Body: {resp_text}")
    except Exception as e:
        logger.debug(f"   Body: <Could not decode: {e}>")
    logger.info(f"{'='*60}")

# --- CONFIGURATION ---
# SAP CPQ Base URL and Credentials (Hardcoded as per request - one-time use only)
CPQ_BASE_URL = "https://tataconsultancyservices-partner1.cpq.cloud.sap"
TOKEN_URL = f"{CPQ_BASE_URL}/basic/api/token"

# Updated API Endpoints (Based on SAP CPQ Admin REST APIs from documentation)
ADMIN_BASE = f"{CPQ_BASE_URL}/setup/api/v1/admin"
CAT_API = f"{ADMIN_BASE}/categories"
PROD_API = f"{ADMIN_BASE}/products"
ATTR_API = f"{ADMIN_BASE}/attributes"
RULE_API = f"{ADMIN_BASE}/rules"
MARKET_API = f"{CPQ_BASE_URL}/api/pricing/v1/markets"  # Keep as is; pricing may differ
PRICING_TABLE_API = f"{ADMIN_BASE}/customtables"  # Custom tables for pricing
PRICING_ENTRY_API = f"{ADMIN_BASE}/customtablerows"  # Rows for entries (assumed; adjust if needed)

CPQ_USERNAME = "REDACTED_CPQ_USERNAME<=="  # Username only
CPQ_DOMAIN = "TATACONSULTANCYSERVICESLIMITED_PARTNER1"
CPQ_PASSWORD = "REDACTED_CPQ_PASSWORD<=="  # Hardcoded password as per request

EMP_ID = "2800815"  # Your emp ID for naming

# Token Management
current_token = None
last_token_time = 0
TOKEN_LIFETIME = 240  # Refresh 10s before 250s expiry

# Helper to generate SystemId
def generate_system_id(name):
    clean = name.lower().replace(' ', '_').replace('-', '_')
    return f"{clean}_cpq"

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

# Attribute Definitions (From PDF, with EMP_ID suffix; simplified for API)
ATTRIBUTES = [
    {"name": f"Size_{EMP_ID}", "data_type": "Text", "attr_type": "SingleSelectMenu", "menu_options": "Small,Medium,Large", "default": "Small", "image_menu": True},
    {"name": f"Crust Type_{EMP_ID}", "data_type": "Text", "attr_type": "SingleSelectMenu", "menu_options": "Thin Crust,Deep Dish", "default": "Thin Crust", "image_menu": True},
    {"name": f"Specialty_{EMP_ID}", "data_type": "Text", "attr_type": "SingleSelectMenu", "menu_options": "Custom Pizza,Meat Lovers,The Works", "default": "Custom Pizza", "image_menu": True},
    {"name": f"Toppings_{EMP_ID}", "data_type": "Text", "attr_type": "MultiSelectMenu", "menu_options": "Sausage,Pepperoni,Green Peppers,Onion,Mushrooms,Anchovy", "default": None, "image_menu": True},
    {"name": f"Include Desserts_{EMP_ID}", "data_type": "Boolean", "attr_type": None, "menu_options": None, "default": "False", "image_menu": False},
    # Container/Array Attributes (Note: API may require separate config for arrays/containers; basic here)
    {"name": f"Number of Desserts_{EMP_ID}", "data_type": "Integer", "attr_type": "TextField", "menu_options": None, "default": "1", "array_type": "NO", "array_control": True},
    {"name": f"Dessert Type_{EMP_ID}", "data_type": "Text", "attr_type": "SingleSelectMenu", "menu_options": "Ice Cream Cone,Hot Fudge Sundae,Milkshake,Yogurt Parfait,Chai Tea Latte", "default": None, "array_type": "YES", "array_control": False},
    {"name": f"Dessert Size_{EMP_ID}", "data_type": "Text", "attr_type": "SingleSelectMenu", "menu_options": "Small,Medium,Large", "default": None, "array_type": "YES", "array_control": False},
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
        resp = requests.post(TOKEN_URL, data=payload, headers=headers, timeout=30)
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

# --- IMAGE HANDLING (Placeholders Only) ---
def get_image_url(entity_name, entity_type="product"):
    query = entity_name.replace(f"_{EMP_ID}", "").replace(" ", "+")
    print(f"   🖼️  Generating placeholder for '{entity_name}'")
    safe_text = query[:20]  # Truncate for readability
    return f"https://placehold.co/800x600/EFEFEF/A6192E/png?text={safe_text}"

# --- API HELPER WITH TOKEN REFRESH & TIMEOUT ---
def api_call(method, url, headers, **kwargs):
    refresh_token_if_needed()
    auth_header = {'Authorization': f'Bearer {current_token}'}
    full_headers = {**headers, **auth_header}
    kwargs['timeout'] = kwargs.get('timeout', 30)  # Default 30s timeout
    if method.upper() == 'GET':
        resp = requests.get(url, headers=full_headers, **kwargs)
    elif method.upper() == 'POST':
        resp = requests.post(url, headers=full_headers, **kwargs)
    else:
        raise ValueError("Unsupported method")
    return resp

# --- 3. CREATE OR FIND ENTITY (Generic Helper) ---
def create_or_find(headers, api_url, payload, find_key="Name", find_value=None):
    if find_value is None:
        find_value = payload.get(find_key, "")

    # First, try to find existing (local filter; add $filter if needed for large lists)
    print(f"   🔍 Searching for: {find_value}")
    search_resp = api_call('GET', api_url, headers)
    if search_resp.status_code == 200:
        existing = search_resp.json()
        existing_list = existing if isinstance(existing, list) else existing.get('Items', []) or existing.get('Value', [])
        for item in existing_list:
            if str(item.get(find_key, "")).strip() == str(find_value).strip():
                sys_id = item.get('SystemId')
                print(f"   🎯 Found existing: {find_value} (SystemId: {sys_id})")
                return sys_id  # Return SystemId for associations
    else:
        print(f"   ⚠️  Search failed ({search_resp.status_code}): {search_resp.text}")

    # Create if not found
    print(f"   ➕ Creating: {find_value}")
    # Add SystemId if not present
    if 'SystemId' not in payload:
        payload['SystemId'] = generate_system_id(find_value)
    create_resp = api_call('POST', api_url, headers, json=payload)
    if create_resp.status_code in [200, 201]:
        new_data = create_resp.json()
        new_id = new_data.get('Id') or new_data.get('SystemId')
        sys_id = payload['SystemId']
        print(f"   ✅ Created SystemId: {sys_id} (ID: {new_id})")
        return sys_id
    else:
        print(f"   ❌ Create Failed ({create_resp.status_code}): {create_resp.text}")
        return None

# --- 4. MAIN AUTOMATION STEPS ---
def run_automation():
    global current_token
    current_token = get_token()
    headers = {'Content-Type': 'application/json'}

    created_ids = {}  # Track SystemIds for associations

    # Step 1: Create Categories and Product (Practice 8-1)
    print("\n🍕 Step 1: Defining Configurable Product Structure")

    # Main Category: "Amo la Pizza"
    main_cat_payload = {
        "Name": "Amo la Pizza",
        "ImageUrl": get_image_url("Amo la Pizza", "pizza category")
    }
    main_cat_sys_id = create_or_find(headers, CAT_API, main_cat_payload)
    if main_cat_sys_id:
        created_ids['main_cat'] = main_cat_sys_id

    # Subcategory: "Pizza Menu_2800815" (child of main_cat)
    sub_cat_payload = {
        "Name": f"Pizza Menu_{EMP_ID}",
        "ParentSystemId": main_cat_sys_id,
        "ImageUrl": get_image_url(f"Pizza Menu_{EMP_ID}")
    }
    sub_cat_sys_id = create_or_find(headers, CAT_API, sub_cat_payload)
    if sub_cat_sys_id:
        created_ids['sub_cat'] = sub_cat_sys_id

    # Product: "Pizza Order_2800815", Type: "Accessories", Base Price: 0, Category: sub_cat
    prod_payload = {
        "Name": f"Pizza Order_{EMP_ID}",
        "ProductType": "Accessories",  # As per lab; may map to 'Simple' or confirm in UI
        "BasePrice": 0,
        "CategorySystemId": sub_cat_sys_id,
        "ImageUrl": get_image_url(f"Pizza Order_{EMP_ID}", "product")
    }
    prod_sys_id = create_or_find(headers, PROD_API, prod_payload, "Name", f"Pizza Order_{EMP_ID}")
    if prod_sys_id:
        created_ids['product'] = prod_sys_id
        print(f"   📦 Product SystemId: {prod_sys_id}")

    # Step 2: Add Attributes (Practice 8-2 & 8-3) - Associate via ProductSystemId
    print("\n⚙️ Step 2: Adding Configurable & Container Attributes")
    attr_sys_ids = {}
    for attr in ATTRIBUTES:
        attr_payload = {
            "Name": attr["name"],
            "DataType": attr["data_type"],
            "AttributeType": attr.get("attr_type"),
            "MenuOptions": attr.get("menu_options"),
            "DefaultValue": attr.get("default"),
            "ImageMenu": attr.get("image_menu", False),
            "ProductSystemId": prod_sys_id,  # Key association
            # Array/Container fields (may need UI tweak for full config)
            "ArrayType": attr.get("array_type"),
            "ArrayControl": attr.get("array_control", False)
        }
        # For container, add included (assumed field; adjust if needed)
        if attr["data_type"] == "Container":
            attr_payload["IncludedAttributes"] = attr["included_attrs"]
            attr_payload["ArrayControlAttribute"] = attr["array_control_attr"]
        attr_sys_id = create_or_find(headers, ATTR_API, attr_payload)
        if attr_sys_id:
            attr_sys_ids[attr["name"]] = attr_sys_id
            print(f"   ✅ Attribute: {attr['name']} (SystemId: {attr_sys_id})")

    # Step 3: Add Rules (Practice 8-5)
    print("\n📋 Step 3: Adding Configuration Rules")
    for rule in RULES:
        rule_payload = {
            "Name": rule["name"],
            "RuleType": rule["type"],
            "Condition": rule["condition"],
            "Action": rule["action"],
            "Message": rule["message"],
            "ProductSystemId": prod_sys_id  # Association
        }
        rule_sys_id = create_or_find(headers, RULE_API, rule_payload)
        if rule_sys_id:
            print(f"   ✅ Rule: {rule['name']} (SystemId: {rule_sys_id})")

    # Step 4: Add Pricing Table & Entries (Practice 8-6) - Using Custom Tables
    print("\n💰 Step 4: Adding Table-Based Pricing")

    # Create CAD Market if needed (keep original)
    cad_market_payload = {"Name": "CAD", "Currency": "CAD"}
    market_resp = api_call('POST', MARKET_API, headers, json=cad_market_payload)
    market_id = None
    if market_resp.status_code in [200, 201]:
        market_id = market_resp.json().get('Id')
        print(f"   🌍 CAD Market ID: {market_id}")
    else:
        print(f"   ⚠️ Market create failed; assuming USD only: {market_resp.text}")

    # Create Custom Pricing Table
    table_payload = {
        "SystemId": generate_system_id(f"Amo La Pizza Pricing_{EMP_ID}"),
        "Name": f"Amo La Pizza Pricing_{EMP_ID}",
        "Description": "Custom pricing for pizza config"
        # Add more fields if needed, e.g., "TableType": "Pricing"
    }
    table_sys_id = create_or_find(headers, PRICING_TABLE_API, table_payload)
    if table_sys_id:
        print(f"   📊 Pricing Table SystemId: {table_sys_id}")

        # Add Entries (Rows)
        for entry in PRICING_DATA:
            entry_payload = {
                "CustomTableSystemId": table_sys_id,
                "Column1": entry["part_number"],  # Assume columns: part_number, description, price_usd, price_cad
                "Column2": entry["description"],
                "Column3": str(entry["price_usd"]),
                "Column4": str(entry["price_cad"])
            }
            entry_resp = api_call('POST', PRICING_ENTRY_API, headers, json=entry_payload)
            if entry_resp.status_code in [200, 201]:
                print(f"   💵 Entry Added: {entry['part_number']}")
            else:
                print(f"   ❌ Entry Failed: {entry['part_number']} - {entry_resp.text}")

    # Step 5: Layout (Practice 8-4) - MANUAL STEP
    print("\n🎨 Step 5: Creating Layout - MANUAL REQUIRED")
    print("   ⚠️  Layout (grids/images) via UI: Products > Pizza Order_2800815 > Layout Editor.")
    print("   Drag attributes; set ImageMenu images (placeholders set).")
    print("   For pricing lookup: Associate table via UI Rules/Pricing tab if not auto.")
    print("   Test: Config page - rules/pricing should work; tweak containers/arrays in UI.")

    print("\n✅ Automation Complete! Verify in UI. If errors (e.g., fields), check Swagger /webapihelp.")

if __name__ == "__main__":
    run_automation()