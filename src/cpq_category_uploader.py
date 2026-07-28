import json
import logging
import sys
import time

import requests

# --- LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Reduce noise from urllib3
logging.getLogger("urllib3").setLevel(logging.WARNING)


# --- REQUEST/RESPONSE LOGGING ---
def log_request(method, url, headers, body=None):
    """Log outgoing request details"""
    logger.info(f"{'=' * 60}")
    logger.info(f"📤 REQUEST: {method.upper()} {url}")
    logger.debug(
        f"   Headers: {json.dumps({k: v[:50] + '...' if len(str(v)) > 50 else v for k, v in headers.items()}, indent=2)}"
    )
    if body:
        body_str = json.dumps(body, indent=2) if isinstance(body, dict) else str(body)
        logger.debug(f"   Body: {body_str[:500]}{'...' if len(body_str) > 500 else ''}")


def log_response(resp, elapsed_time=None):
    """Log incoming response details"""
    status_emoji = (
        "✅"
        if resp.status_code in [200, 201]
        else "⚠️"
        if resp.status_code < 400
        else "❌"
    )
    logger.info(f"📥 RESPONSE: {status_emoji} {resp.status_code} {resp.reason}")
    if elapsed_time:
        logger.debug(f"   Elapsed: {elapsed_time:.2f}s")
    logger.debug(f"   Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
    try:
        resp_text = resp.text[:1000] if len(resp.text) > 1000 else resp.text
        logger.debug(f"   Body: {resp_text}")
    except Exception as e:
        logger.debug(f"   Body: <Could not decode: {e}>")
    logger.info(f"{'=' * 60}")


# --- CONFIGURATION ---
# SAP CPQ Base URL and Credentials (Hardcoded as per request - one-time use only)
CPQ_BASE_URL = "https://tataconsultancyservices-partner1.cpq.cloud.sap"
TOKEN_URL = f"{CPQ_BASE_URL}/basic/api/token"

# Updated API Endpoints (Based on SAP CPQ REST APIs from documentation)
# Categories and Attributes use /api/products/v1/
PRODUCTS_API_BASE = f"{CPQ_BASE_URL}/api/products/v1"
CAT_API = f"{PRODUCTS_API_BASE}/categories"
ATTR_API = f"{PRODUCTS_API_BASE}/attributes"

# Admin APIs for products, rules, etc.
ADMIN_BASE = f"{CPQ_BASE_URL}/setup/api/v1/admin"
PROD_API = f"{ADMIN_BASE}/products"  # Products use admin API!
RULE_API = f"{ADMIN_BASE}/rules"

# Pricing APIs
MARKET_API = f"{CPQ_BASE_URL}/api/pricing/v1/markets"
PRICING_TABLE_API = f"{ADMIN_BASE}/customtables"
PRICING_ENTRY_API = f"{ADMIN_BASE}/customtablerows"

CPQ_USERNAME = os.environ.get("CPQ_USERNAME", "")
CPQ_DOMAIN = os.environ.get("CPQ_DOMAIN", "TATACONSULTANCYSERVICESLIMITED_PARTNER1")
CPQ_PASSWORD = os.environ.get("CPQ_PASSWORD", "")

EMP_ID = os.environ.get("EMP_ID", "2800815")

# Token Management
current_token = None
last_token_time = 0
TOKEN_LIFETIME = 240  # Refresh 10s before 250s expiry


# Helper to generate SystemId
def generate_system_id(name):
    clean = name.lower().replace(" ", "_").replace("-", "_")
    return f"{clean}_cpq"


# Pricing Data (Hardcoded from PDF - USD prices; CAD = 1.1 * USD)
PRICING_DATA = [
    {
        "part_number": "BX001",
        "description": "Gift box packing",
        "price_usd": 1,
        "price_cad": 1.1,
    },
    {
        "part_number": "PZ_SmTh",
        "description": "Small Thin Crust Pizza",
        "price_usd": 10,
        "price_cad": 11,
    },
    {
        "part_number": "PZ_MdTh",
        "description": "Medium Thin Crust Pizza",
        "price_usd": 12,
        "price_cad": 13.2,
    },
    {
        "part_number": "PZ_MdDd",
        "description": "Medium Deep Dish Pizza",
        "price_usd": 15,
        "price_cad": 16.5,
    },
    {
        "part_number": "PZ_LgTh",
        "description": "Large Thin Crust Pizza",
        "price_usd": 17,
        "price_cad": 18.7,
    },
    {
        "part_number": "PZ_LgDd",
        "description": "Large Deep Dish Pizza",
        "price_usd": 20,
        "price_cad": 22,
    },
    {
        "part_number": "TP001",
        "description": "Add Sausage",
        "price_usd": 1,
        "price_cad": 1.1,
    },
    {
        "part_number": "TP002",
        "description": "Add Pepperoni",
        "price_usd": 1,
        "price_cad": 1.1,
    },
    {
        "part_number": "TP003",
        "description": "Add Green Pepper",
        "price_usd": 1,
        "price_cad": 1.1,
    },
    {
        "part_number": "TP004",
        "description": "Add Onion",
        "price_usd": 1,
        "price_cad": 1.1,
    },
    {
        "part_number": "TP005",
        "description": "Add Mushrooms",
        "price_usd": 1,
        "price_cad": 1.1,
    },
    {
        "part_number": "TP006",
        "description": "Add Anchovy",
        "price_usd": 1,
        "price_cad": 1.1,
    },
    {
        "part_number": "ICC001",
        "description": "Small Ice Cream Cone with nuts",
        "price_usd": 1.25,
        "price_cad": 1.375,
    },
    {
        "part_number": "ICC002",
        "description": "Small Ice Cream Cone without nuts",
        "price_usd": 1,
        "price_cad": 1.1,
    },
    {
        "part_number": "HFS001",
        "description": "Small Hot Fudge Sundae with nuts",
        "price_usd": 1.75,
        "price_cad": 1.925,
    },
    {
        "part_number": "HFS002",
        "description": "Small Hot Fudge Sundae without nuts",
        "price_usd": 1.5,
        "price_cad": 1.65,
    },
    {
        "part_number": "MS001",
        "description": "Small Milkshake with nuts",
        "price_usd": 1.5,
        "price_cad": 1.65,
    },
    {
        "part_number": "MS002",
        "description": "Small Milkshake without nuts",
        "price_usd": 1.25,
        "price_cad": 1.375,
    },
    {
        "part_number": "YP001",
        "description": "Small Yogurt Parfait with nuts",
        "price_usd": 1.5,
        "price_cad": 1.65,
    },
    {
        "part_number": "YP002",
        "description": "Small Yogurt Parfait without nuts",
        "price_usd": 1.25,
        "price_cad": 1.375,
    },
    {
        "part_number": "CTL001",
        "description": "Small Chai Tea Latte with nuts",
        "price_usd": 1.5,
        "price_cad": 1.65,
    },
    {
        "part_number": "CTL002",
        "description": "Small Chai Tea Latte without nuts",
        "price_usd": 1.25,
        "price_cad": 1.375,
    },
    {
        "part_number": "ICC003",
        "description": "Medium Ice Cream Cone with nuts",
        "price_usd": 1.75,
        "price_cad": 1.925,
    },
    {
        "part_number": "ICC004",
        "description": "Medium Ice Cream Cone without nuts",
        "price_usd": 1.5,
        "price_cad": 1.65,
    },
    {
        "part_number": "HFS003",
        "description": "Medium Hot Fudge Sundae with nuts",
        "price_usd": 2.25,
        "price_cad": 2.475,
    },
    {
        "part_number": "HFS004",
        "description": "Medium Hot Fudge Sundae without nuts",
        "price_usd": 2,
        "price_cad": 2.2,
    },
    {
        "part_number": "MS003",
        "description": "Medium Milkshake with nuts",
        "price_usd": 2,
        "price_cad": 2.2,
    },
    {
        "part_number": "MS004",
        "description": "Medium Milkshake without nuts",
        "price_usd": 1.75,
        "price_cad": 1.925,
    },
    {
        "part_number": "YP003",
        "description": "Medium Yogurt Parfait with nuts",
        "price_usd": 2,
        "price_cad": 2.2,
    },
    {
        "part_number": "YP004",
        "description": "Medium Yogurt Parfait without nuts",
        "price_usd": 1.75,
        "price_cad": 1.925,
    },
    {
        "part_number": "CTL003",
        "description": "Medium Chai Tea Latte with nuts",
        "price_usd": 2,
        "price_cad": 2.2,
    },
    {
        "part_number": "CTL004",
        "description": "Medium Chai Tea Latte without nuts",
        "price_usd": 1.75,
        "price_cad": 1.925,
    },
    {
        "part_number": "ICC005",
        "description": "Large Ice Cream Cone with nuts",
        "price_usd": 2.25,
        "price_cad": 2.475,
    },
    {
        "part_number": "ICC006",
        "description": "Large Ice Cream Cone without nuts",
        "price_usd": 2,
        "price_cad": 2.2,
    },
    {
        "part_number": "HFS005",
        "description": "Large Hot Fudge Sundae with nuts",
        "price_usd": 2.75,
        "price_cad": 3.025,
    },
    {
        "part_number": "HFS006",
        "description": "Large Hot Fudge Sundae without nuts",
        "price_usd": 2.5,
        "price_cad": 2.75,
    },
    {
        "part_number": "MS005",
        "description": "Large Milkshake with nuts",
        "price_usd": 2.5,
        "price_cad": 2.75,
    },
    {
        "part_number": "MS006",
        "description": "Large Milkshake without nuts",
        "price_usd": 2.25,
        "price_cad": 2.475,
    },
    {
        "part_number": "YP005",
        "description": "Large Yogurt Parfait with nuts",
        "price_usd": 2.5,
        "price_cad": 2.75,
    },
    {
        "part_number": "YP006",
        "description": "Large Yogurt Parfait without nuts",
        "price_usd": 2.25,
        "price_cad": 2.475,
    },
    {
        "part_number": "CTL005",
        "description": "Large Chai Tea Latte with nuts",
        "price_usd": 2.5,
        "price_cad": 2.75,
    },
    {
        "part_number": "CTL006",
        "description": "Large Chai Tea Latte without nuts",
        "price_usd": 2.25,
        "price_cad": 2.475,
    },
]

# Attribute Definitions (From PDF, with EMP_ID suffix; simplified for API)
ATTRIBUTES = [
    {
        "name": f"Size_{EMP_ID}",
        "data_type": "Text",
        "attr_type": "SingleSelectMenu",
        "menu_options": "Small,Medium,Large",
        "default": "Small",
        "image_menu": True,
    },
    {
        "name": f"Crust Type_{EMP_ID}",
        "data_type": "Text",
        "attr_type": "SingleSelectMenu",
        "menu_options": "Thin Crust,Deep Dish",
        "default": "Thin Crust",
        "image_menu": True,
    },
    {
        "name": f"Specialty_{EMP_ID}",
        "data_type": "Text",
        "attr_type": "SingleSelectMenu",
        "menu_options": "Custom Pizza,Meat Lovers,The Works",
        "default": "Custom Pizza",
        "image_menu": True,
    },
    {
        "name": f"Toppings_{EMP_ID}",
        "data_type": "Text",
        "attr_type": "MultiSelectMenu",
        "menu_options": "Sausage,Pepperoni,Green Peppers,Onion,Mushrooms,Anchovy",
        "default": None,
        "image_menu": True,
    },
    {
        "name": f"Include Desserts_{EMP_ID}",
        "data_type": "Boolean",
        "attr_type": None,
        "menu_options": None,
        "default": "False",
        "image_menu": False,
    },
    # Container/Array Attributes (Note: API may require separate config for arrays/containers; basic here)
    {
        "name": f"Number of Desserts_{EMP_ID}",
        "data_type": "Integer",
        "attr_type": "TextField",
        "menu_options": None,
        "default": "1",
        "array_type": "NO",
        "array_control": True,
    },
    {
        "name": f"Dessert Type_{EMP_ID}",
        "data_type": "Text",
        "attr_type": "SingleSelectMenu",
        "menu_options": "Ice Cream Cone,Hot Fudge Sundae,Milkshake,Yogurt Parfait,Chai Tea Latte",
        "default": None,
        "array_type": "YES",
        "array_control": False,
    },
    {
        "name": f"Dessert Size_{EMP_ID}",
        "data_type": "Text",
        "attr_type": "SingleSelectMenu",
        "menu_options": "Small,Medium,Large",
        "default": None,
        "array_type": "YES",
        "array_control": False,
    },
    {
        "name": f"Dessert Options_{EMP_ID}",
        "data_type": "Container",
        "included_attrs": [f"Dessert Type_{EMP_ID}", f"Dessert Size_{EMP_ID}"],
        "array_control_attr": f"Number of Desserts_{EMP_ID}",
    },
]

# Rules Definitions (From PDF, with EMP_ID suffix)
RULES = [
    {
        "name": f"Constrain Size by Crust Type_{EMP_ID}",
        "type": "Constraint",
        "condition": "Size is Small",
        "action": "Do not allow Deep Dish as a selection for Crust Type",
        "message": "Deep Dish Not Available in Size Small",
    },
    {
        "name": f"Specialty Meat Lovers_{EMP_ID}",
        "type": "Recommendation",
        "condition": "Specialty is Meat Lovers",
        "action": "Force Set Toppings to Sausage and Pepperoni",
        "message": None,
    },
    {
        "name": f"Specialty The Works_{EMP_ID}",
        "type": "Recommendation",
        "condition": "Specialty is The Works",
        "action": "Force Set Toppings to Sausage, Pepperoni, Green Peppers, Onion, and Mushrooms",
        "message": None,
    },
    {
        "name": f"Hide Dessert Options_{EMP_ID}",
        "type": "HidingAttributes",
        "condition": "Include Desserts is False",
        "action": "Hide Number of Desserts, Dessert Type, and Dessert Size",
        "message": None,
    },
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
        "grant_type": "password",
        "username": CPQ_USERNAME,
        "password": CPQ_PASSWORD,
        "domain": CPQ_DOMAIN,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        resp = requests.post(TOKEN_URL, data=payload, headers=headers, timeout=30)
        if resp.status_code != 200:
            print(f"❌ Auth Failed ({resp.status_code}): {resp.text}")
            sys.exit(1)
        token = resp.json()["access_token"]
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


# --- API HELPER WITH TOKEN REFRESH, LOGGING, RETRY & TIMEOUT ---
MAX_RETRIES = 3
REQUEST_TIMEOUT = 15  # Reduced from 30s to fail faster on hangs


def api_call(method, url, headers, retry_count=0, **kwargs):
    """
    Make an API call with comprehensive logging and retry support.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        url: Full URL to call
        headers: Request headers (auth will be added)
        retry_count: Current retry attempt (internal)
        **kwargs: Additional args for requests (json, data, params, etc.)

    Returns:
        Response object
    """
    refresh_token_if_needed()
    auth_header = {"Authorization": f"Bearer {current_token}"}
    full_headers = {**headers, **auth_header}

    # Set timeout - use shorter timeout to detect hangs faster
    kwargs["timeout"] = kwargs.get("timeout", REQUEST_TIMEOUT)

    # Extract body for logging (if present)
    body = kwargs.get("json") or kwargs.get("data")

    # Log the request
    log_request(method, url, full_headers, body)
    logger.info(
        f"   ⏱️  Timeout: {kwargs['timeout']}s | Retry: {retry_count}/{MAX_RETRIES}"
    )

    start_time = time.time()

    try:
        if method.upper() == "GET":
            resp = requests.get(url, headers=full_headers, **kwargs)
        elif method.upper() == "POST":
            resp = requests.post(url, headers=full_headers, **kwargs)
        elif method.upper() == "PUT":
            resp = requests.put(url, headers=full_headers, **kwargs)
        elif method.upper() == "DELETE":
            resp = requests.delete(url, headers=full_headers, **kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        elapsed = time.time() - start_time
        log_response(resp, elapsed)

        # Check for specific error codes that indicate wrong endpoint/method
        if resp.status_code == 405:
            logger.error(f"❌ HTTP 405 - Method '{method}' not allowed for URL: {url}")
            logger.error(
                "   💡 This usually means the API endpoint doesn't support this HTTP method."
            )
            logger.error(
                "   💡 Check SAP CPQ API documentation for correct endpoint structure."
            )

        if resp.status_code == 404:
            logger.error(f"❌ HTTP 404 - Endpoint not found: {url}")
            logger.error(
                "   💡 The API endpoint may not exist or requires different path structure."
            )

        return resp

    except requests.exceptions.Timeout as e:
        elapsed = time.time() - start_time
        logger.error(f"❌ TIMEOUT after {elapsed:.2f}s: {url}")
        logger.error(f"   Exception: {type(e).__name__}: {e}")

        if retry_count < MAX_RETRIES:
            wait_time = 2**retry_count  # Exponential backoff: 1s, 2s, 4s
            logger.warning(
                f"   🔄 Retrying in {wait_time}s... (attempt {retry_count + 1}/{MAX_RETRIES})"
            )
            time.sleep(wait_time)
            return api_call(method, url, headers, retry_count + 1, **kwargs)
        else:
            logger.error(f"   ❌ Max retries ({MAX_RETRIES}) exceeded. Giving up.")
            # Return a mock response object for graceful handling
            return _create_error_response(504, "Gateway Timeout", str(e))

    except requests.exceptions.ConnectionError as e:
        elapsed = time.time() - start_time
        logger.error(f"❌ CONNECTION ERROR after {elapsed:.2f}s: {url}")
        logger.error(f"   Exception: {type(e).__name__}: {e}")

        if retry_count < MAX_RETRIES:
            wait_time = 2**retry_count
            logger.warning(
                f"   🔄 Retrying in {wait_time}s... (attempt {retry_count + 1}/{MAX_RETRIES})"
            )
            time.sleep(wait_time)
            return api_call(method, url, headers, retry_count + 1, **kwargs)
        else:
            logger.error(f"   ❌ Max retries ({MAX_RETRIES}) exceeded. Giving up.")
            return _create_error_response(503, "Service Unavailable", str(e))

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"❌ UNEXPECTED ERROR after {elapsed:.2f}s: {url}")
        logger.error(f"   Exception: {type(e).__name__}: {e}")
        return _create_error_response(500, "Internal Error", str(e))


class MockResponse:
    """Mock response object for error cases"""

    def __init__(self, status_code, reason, text):
        self.status_code = status_code
        self.reason = reason
        self.text = text
        self.headers = {"Content-Type": "application/json"}

    def json(self):
        return {"error": self.reason, "message": self.text}


def _create_error_response(status_code, reason, message):
    """Create a mock response for connection failures"""
    return MockResponse(status_code, reason, message)


# --- 3. CREATE OR FIND ENTITY (Generic Helper) ---
def create_or_find(headers, api_url, payload, find_key="Name", find_value=None):
    if find_value is None:
        find_value = payload.get(find_key, "")

    logger.info(f"🔍 SEARCH: Looking for '{find_value}' in {api_url}")

    # First, try to find existing
    search_resp = api_call("GET", api_url, headers)

    if search_resp.status_code == 200:
        existing = search_resp.json()

        # Log the structure of the response to understand API format
        logger.debug(f"   Response type: {type(existing).__name__}")
        if isinstance(existing, dict):
            logger.debug(f"   Response keys: {list(existing.keys())}")

        # Handle different response structures - SAP CPQ uses 'pagedRecords' for paginated results
        if isinstance(existing, list):
            existing_list = existing
        else:
            existing_list = (
                existing.get("pagedRecords", [])  # SAP CPQ paginated format
                or existing.get("Items", [])
                or existing.get("Value", [])
                or existing.get("value", [])
            )

        logger.info(f"   Found {len(existing_list)} items in response")

        for item in existing_list:
            # Check both PascalCase and camelCase field names since API may use either
            item_name = str(
                item.get(find_key, "") or item.get(find_key.lower(), "")
            ).strip()
            logger.debug(f"   Checking: '{item_name}' vs '{find_value}'")
            if (
                item_name.lower() == str(find_value).strip().lower()
            ):  # Case-insensitive compare
                sys_id = (
                    item.get("SystemId")
                    or item.get("systemId")
                    or item.get("Id")
                    or item.get("id")
                )
                logger.info(f"   🎯 Found existing: {find_value} (ID: {sys_id})")
                return sys_id

        logger.info(f"   ℹ️  Entity '{find_value}' not found in existing items")
    else:
        logger.warning(
            f"   ⚠️  Search failed ({search_resp.status_code}): {search_resp.text[:200]}"
        )

    # Create if not found
    logger.info(f"➕ CREATE: Attempting to create '{find_value}'")
    logger.info(f"   API URL: {api_url}")

    # Add SystemId if not present
    if "SystemId" not in payload:
        payload["SystemId"] = generate_system_id(find_value)

    logger.debug(f"   Payload: {json.dumps(payload, indent=2)[:500]}")

    create_resp = api_call("POST", api_url, headers, json=payload)

    if create_resp.status_code in [200, 201]:
        new_data = create_resp.json()
        new_id = new_data.get("Id") or new_data.get("SystemId") or new_data.get("id")
        sys_id = payload["SystemId"]
        logger.info(f"   ✅ Created successfully: {sys_id} (ID: {new_id})")
        return sys_id
    elif create_resp.status_code == 405:
        logger.error(f"   ❌ HTTP 405 - POST not supported at: {api_url}")
        logger.error(
            "   💡 SAP CPQ Admin API may require different endpoint structure."
        )
        logger.error(
            "   💡 Try checking if POSTing to a sub-resource is needed (e.g., /products/create)"
        )
        return None
    else:
        logger.error(
            f"   ❌ Create Failed ({create_resp.status_code}): {create_resp.text[:300]}"
        )
        return None


# --- 4. MAIN AUTOMATION STEPS ---
def run_automation():
    global current_token
    current_token = get_token()
    headers = {"Content-Type": "application/json"}

    created_ids = {}  # Track IDs for associations

    # Step 1: Create Categories and Product (Practice 8-1)
    logger.info("\n🍕 Step 1: Defining Configurable Product Structure")

    # Main Category: "Amo la Pizza"
    # Using lowercase field names as per SAP CPQ API documentation
    # Note: mainImage has 50 char max - skip for now, set in UI
    main_cat_payload = {
        "name": "Amo la Pizza",
        "systemId": generate_system_id("Amo la Pizza"),
        "active": True,
        "visibleToEveryone": True,
        "parentCategory": 0,  # 0 = root category (not null!)
    }
    get_image_url("Amo la Pizza", "pizza category")  # Just log placeholder
    main_cat_id = create_or_find(headers, CAT_API, main_cat_payload, find_key="name")
    if main_cat_id:
        created_ids["main_cat"] = main_cat_id
        logger.info(f"   ✅ Main Category ID: {main_cat_id}")

    # Subcategory: "Pizza Menu_2800815" (child of main_cat)
    # parentCategory must be an int (the category ID, not systemId)
    sub_cat_payload = {
        "name": f"Pizza Menu_{EMP_ID}",
        "systemId": generate_system_id(f"Pizza Menu_{EMP_ID}"),
        "parentCategory": main_cat_id if main_cat_id else 0,  # Parent category ID (int)
        "active": True,
        "visibleToEveryone": True,
    }
    get_image_url(f"Pizza Menu_{EMP_ID}")  # Just log placeholder
    sub_cat_id = create_or_find(headers, CAT_API, sub_cat_payload, find_key="name")
    if sub_cat_id:
        created_ids["sub_cat"] = sub_cat_id
        logger.info(f"   ✅ Sub Category ID: {sub_cat_id}")

    # Product: "Pizza Order_2800815", Type: "Accessories", Base Price: 0, Category: sub_cat
    # Products use /setup/api/v1/admin/products - field names may differ
    get_image_url(f"Pizza Order_{EMP_ID}", "product")  # Just log placeholder
    prod_payload = {
        "name": f"Pizza Order_{EMP_ID}",
        "systemId": generate_system_id(f"Pizza Order_{EMP_ID}"),
        "productType": "Accessories",  # As per lab
        "active": True,
        # Note: Category association may need to be done separately via UI or different API
    }
    prod_id = create_or_find(
        headers,
        PROD_API,
        prod_payload,
        find_key="name",
        find_value=f"Pizza Order_{EMP_ID}",
    )
    if prod_id:
        created_ids["product"] = prod_id
        logger.info(f"   📦 Product ID: {prod_id}")

    # Step 2: Add Attributes (Practice 8-2 & 8-3)
    # Attributes API uses lowercase field names based on API response
    logger.info("\n⚙️ Step 2: Adding Configurable & Container Attributes")
    attr_sys_ids = {}

    # Map our attr_type values to SAP CPQ type values
    TYPE_MAPPING = {
        "SingleSelectMenu": "Single Select Menu",
        "MultiSelectMenu": "Multi Select Menu",
        "TextField": "Text Field",
        None: "Check Box",  # Default for Boolean
    }

    for attr in ATTRIBUTES:
        # Skip container type for now - requires special handling
        if attr["data_type"] == "Container":
            logger.warning(
                f"   ⚠️  Skipping Container attribute '{attr['name']}' - requires UI setup"
            )
            continue

        # Build payload with lowercase field names as returned by API
        attr_payload = {
            "name": attr["name"],
            "systemId": generate_system_id(attr["name"]),
            "type": TYPE_MAPPING.get(
                attr.get("attr_type"), attr.get("attr_type")
            ),  # Required field!
        }

        # Add optional fields if present
        if attr.get("menu_options"):
            # For menus, we need to create values separately or include them
            attr_payload["values"] = [
                {"value": opt.strip(), "valueCode": opt.strip().replace(" ", "_")}
                for opt in attr["menu_options"].split(",")
            ]

        attr_sys_id = create_or_find(headers, ATTR_API, attr_payload, find_key="name")
        if attr_sys_id:
            attr_sys_ids[attr["name"]] = attr_sys_id
            logger.info(f"   ✅ Attribute: {attr['name']} (ID: {attr_sys_id})")

    # Step 3: Add Rules (Practice 8-5)
    print("\n📋 Step 3: Adding Configuration Rules")
    for rule in RULES:
        rule_payload = {
            "Name": rule["name"],
            "RuleType": rule["type"],
            "Condition": rule["condition"],
            "Action": rule["action"],
            "Message": rule["message"],
            "ProductSystemId": prod_id,  # Association
        }
        rule_sys_id = create_or_find(headers, RULE_API, rule_payload)
        if rule_sys_id:
            print(f"   ✅ Rule: {rule['name']} (SystemId: {rule_sys_id})")

    # Step 4: Add Pricing Table & Entries (Practice 8-6) - Using Custom Tables
    print("\n💰 Step 4: Adding Table-Based Pricing")

    # Create CAD Market if needed (keep original)
    cad_market_payload = {"Name": "CAD", "Currency": "CAD"}
    market_resp = api_call("POST", MARKET_API, headers, json=cad_market_payload)
    market_id = None
    if market_resp.status_code in [200, 201]:
        market_id = market_resp.json().get("Id")
        print(f"   🌍 CAD Market ID: {market_id}")
    else:
        print(f"   ⚠️ Market create failed; assuming USD only: {market_resp.text}")

    # Create Custom Pricing Table
    table_payload = {
        "SystemId": generate_system_id(f"Amo La Pizza Pricing_{EMP_ID}"),
        "Name": f"Amo La Pizza Pricing_{EMP_ID}",
        "Description": "Custom pricing for pizza config",
        # Add more fields if needed, e.g., "TableType": "Pricing"
    }
    table_sys_id = create_or_find(headers, PRICING_TABLE_API, table_payload)
    if table_sys_id:
        print(f"   📊 Pricing Table SystemId: {table_sys_id}")

        # Add Entries (Rows)
        for entry in PRICING_DATA:
            entry_payload = {
                "CustomTableSystemId": table_sys_id,
                "Column1": entry[
                    "part_number"
                ],  # Assume columns: part_number, description, price_usd, price_cad
                "Column2": entry["description"],
                "Column3": str(entry["price_usd"]),
                "Column4": str(entry["price_cad"]),
            }
            entry_resp = api_call(
                "POST", PRICING_ENTRY_API, headers, json=entry_payload
            )
            if entry_resp.status_code in [200, 201]:
                print(f"   💵 Entry Added: {entry['part_number']}")
            else:
                print(f"   ❌ Entry Failed: {entry['part_number']} - {entry_resp.text}")

    # Step 5: Layout (Practice 8-4) - MANUAL STEP
    print("\n🎨 Step 5: Creating Layout - MANUAL REQUIRED")
    print(
        "   ⚠️  Layout (grids/images) via UI: Products > Pizza Order_2800815 > Layout Editor."
    )
    print("   Drag attributes; set ImageMenu images (placeholders set).")
    print(
        "   For pricing lookup: Associate table via UI Rules/Pricing tab if not auto."
    )
    print(
        "   Test: Config page - rules/pricing should work; tweak containers/arrays in UI."
    )

    print(
        "\n✅ Automation Complete! Verify in UI. If errors (e.g., fields), check Swagger /webapihelp."
    )


if __name__ == "__main__":
    run_automation()
