import os
import requests
import base64
from dotenv import load_dotenv
from app_redis.cache import get_cache, set_cache, make_key

load_dotenv()

KROGER_BASE = os.getenv("KROGER_BASE_URL")
KROGER_ID = os.getenv("KROGER_CLIENT_ID")
KROGER_SECRET = os.getenv("KROGER_CLIENT_SECRET")
OFF_URL = os.getenv("OPEN_FOOD_FACTS_URL")
TTL = int(os.getenv("REDIS_TTL_GROCERY", 3600))


# ──────────────────────────────────────────────────────────────
# KROGER — Primary
# ──────────────────────────────────────────────────────────────

def _get_kroger_token() -> str:
    """
    Fetch a fresh OAuth2 token from Kroger.
    Cached in Redis for 25 minutes (token expires at 30 min).
    """
    cache_key = "kroger:oauth_token"
    cached = get_cache(cache_key)
    if cached:
        return cached["token"]

    credentials = base64.b64encode(
        f"{KROGER_ID}:{KROGER_SECRET}".encode()
    ).decode()

    resp = requests.post(
        f"{KROGER_BASE}/connect/oauth2/token",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        data={
            "grant_type": "client_credentials",
            "scope": "product.compact"
        }
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")

    # Cache token for 25 min (expires at 30 min)
    set_cache(cache_key, {"token": token}, ttl=1500)
    return token


def search_kroger(query: str) -> list:
    """
    Search Kroger product catalog.
    Returns up to 5 matching products with name, brand, price, image.
    Falls back to Open Food Facts if Kroger fails.
    """
    cache_key = make_key("kroger:search", query)
    cached = get_cache(cache_key)
    if cached:
        print(f"✅ Kroger cache hit → {query}")
        return cached

    print(f"🔍 Searching Kroger: '{query}'")

    try:
        token = _get_kroger_token()
        resp = requests.get(
            f"{KROGER_BASE}/products",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "filter.term": query,
                "filter.limit": 5
            }
        )
        resp.raise_for_status()
        raw_products = resp.json().get("data", [])

        results = []
        for p in raw_products:
            price_info = p.get("items", [{}])[0].get("price", {})
            results.append({
                "source": "kroger",
                "name": p.get("description", ""),
                "brand": p.get("brand", ""),
                "sku": p.get("productId", ""),
                "price": price_info.get("regular", 0.0),
                "image": p.get("images", [{}])[0].get("sizes", [{}])[0].get("url", ""),
                "category": p.get("categories", [""])[0]
            })

        set_cache(cache_key, results, TTL)
        print(f"✅ Kroger found {len(results)} results for '{query}'")
        return results

    except Exception as e:
        print(f"⚠️  Kroger search failed for '{query}': {e}")
        print(f"↩️  Falling back to Open Food Facts...")
        return search_open_food_facts(query)


# ──────────────────────────────────────────────────────────────
# OPEN FOOD FACTS — Fallback (No API key needed)
# ──────────────────────────────────────────────────────────────

def search_open_food_facts(query: str) -> list:
    """
    Search Open Food Facts — completely free, no API key.
    Used as fallback when Kroger fails or returns no results.
    """
    cache_key = make_key("openfoodfacts:search", query)
    cached = get_cache(cache_key)
    if cached:
        print(f"✅ Open Food Facts cache hit → {query}")
        return cached

    print(f"🔍 Searching Open Food Facts: '{query}'")

    try:
        resp = requests.get(
            OFF_URL,
            params={
                "search_terms": query,
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": 5,
                "fields": "product_name,brands,nutriments,image_url,categories"
            }
        )
        resp.raise_for_status()
        raw_products = resp.json().get("products", [])

        results = []
        for p in raw_products:
            if not p.get("product_name"):
                continue
            results.append({
                "source": "open_food_facts",
                "name": p.get("product_name", ""),
                "brand": p.get("brands", ""),
                "sku": None,
                "price": None,
                "image": p.get("image_url", ""),
                "category": p.get("categories", ""),
                "calories": p.get("nutriments", {}).get("energy-kcal_100g", 0),
                "protein_g": p.get("nutriments", {}).get("proteins_100g", 0),
                "carbs_g": p.get("nutriments", {}).get("carbohydrates_100g", 0),
                "fat_g": p.get("nutriments", {}).get("fat_100g", 0)
            })

        set_cache(cache_key, results, TTL)
        print(f"✅ Open Food Facts found {len(results)} results for '{query}'")
        return results

    except Exception as e:
        print(f"❌ Open Food Facts also failed for '{query}': {e}")
        return []


# ──────────────────────────────────────────────────────────────
# MAIN SEARCH — Smart router between Kroger + OFF
# ──────────────────────────────────────────────────────────────

def search_product(query: str) -> list:
    """
    Master product search.
    Tries Kroger first, falls back to Open Food Facts automatically.
    This is the only function the rest of the app should call.
    """
    results = search_kroger(query)

    # If Kroger gave nothing, try Open Food Facts
    if not results:
        print(f"↩️  Kroger empty — trying Open Food Facts for '{query}'")
        results = search_open_food_facts(query)

    return results


def search_multiple(ingredients: list) -> dict:
    """
    Search for multiple ingredients at once.
    Returns a dict keyed by ingredient name.

    Input: [{"normalized_name": "olive oil"}, ...]
    Output: {"olive oil": [...results], "garlic": [...results]}
    """
    results = {}
    for item in ingredients:
        name = item.get("normalized_name", "")
        if name:
            results[name] = search_product(name)
    return results
