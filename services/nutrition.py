import os
import requests
from loguru import logger
from app_redis.cache import get_cache, set_cache, make_key
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv
from utils.config import get_secret

load_dotenv()

TTL = int(os.getenv("REDIS_TTL_NUTRITION", 43200))


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5))
def get_nutrition_data(ingredients: list) -> dict:
    """
    Fetch nutrition data from USDA FoodData Central.
    Results are cached per ingredient list hash.
    """
    ingredient_names = [i.get("normalized_name", i.get("name", "")) for i in ingredients]
    cache_key = make_key("nutrition", str(sorted(ingredient_names)))
    cached = get_cache(cache_key)
    if cached:
        return cached

    logger.info(f"🥗 Fetching nutrition for {len(ingredients)} ingredients...")

    nutrition_results = []
    for ingredient in ingredients:
        data = _query_usda(ingredient.get("normalized_name", ingredient.get("name", "")))
        if data:
            nutrition_results.append({
                "ingredient": ingredient.get("normalized_name", ingredient.get("name", "")),
                "calories_per_100g": data.get("calories"),
                "protein_g": data.get("protein"),
                "carbs_g": data.get("carbs"),
                "fat_g": data.get("fat")
            })

    result = {
        "ingredients": nutrition_results,
        "total_calories": sum(
            (r.get("calories_per_100g") or 0) for r in nutrition_results
        )
    }
    # Only cache if we actually got data back
    if nutrition_results:
        set_cache(cache_key, result, TTL)
    return result


def _query_usda(food_name: str) -> dict:
    """Query a single ingredient from USDA API."""
    try:
        resp = requests.get(
            f"{get_secret('USDA_BASE_URL', 'https://api.nal.usda.gov/fdc/v1')}/foods/search",
            params={"query": food_name, "api_key": get_secret("USDA_API_KEY"), "pageSize": 1}
        )
        resp.raise_for_status()
        foods = resp.json().get("foods", [])
        if not foods:
            return {}
        food = foods[0]
        nutrients = {n["nutrientName"]: n["value"] for n in food.get("foodNutrients", [])}
        return {
            "calories": nutrients.get("Energy", 0),
            "protein":  nutrients.get("Protein", 0),
            "carbs":    nutrients.get("Carbohydrate, by difference", 0),
            "fat":      nutrients.get("Total lipid (fat)", 0)
        }
    except Exception as e:
        logger.warning(f"USDA query failed for '{food_name}': {e}")
        return {}
