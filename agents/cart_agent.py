import os
import re
import json
import anthropic
from loguru import logger
from services.grocery import search_product
from app_redis.state import get_user_preferences
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """
You are a grocery shopping AI. Given a list of search results for each ingredient,
select the BEST product match.

Prioritize in this order:
1. Exact name match
2. User dietary preferences
3. Organic if available and price difference < 20%
4. Lowest price otherwise
5. Best reviewed

Return ONLY valid JSON:
{
  "cart": [
    {
      "ingredient": "olive oil",
      "selected_product": "California Olive Ranch Extra Virgin Olive Oil",
      "sku": "12345",
      "price": 8.99,
      "reason": "Best match, organic, within budget"
    }
  ]
}
"""


def run_cart_mapping(normalized_data: dict, user_id: str = "default") -> dict:
    """
    Claude Agent #3 — Match ingredients to best Instacart products.
    Uses user preferences from Redis to personalize selections.
    """
    ingredients = normalized_data.get("normalized", [])
    user_prefs = get_user_preferences(user_id)

    logger.info(f"🛒 Claude #3: Mapping {len(ingredients)} items to Instacart products...")

    search_results = []
    for item in ingredients:
        results = search_product(item["normalized_name"])
        search_results.append({
            "ingredient": item["normalized_name"],
            "search_results": results
        })

    message = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5"),
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"User preferences: {json.dumps(user_prefs)}\n\n"
                    f"Select best products from these search results:\n\n"
                    f"{json.dumps(search_results, indent=2)}"
                )
            }
        ]
    )

    raw_response = message.content[0].text
    try:
        cleaned = re.sub(r"```(?:json)?|```", "", raw_response).strip()
        result = json.loads(cleaned)
        logger.success(f"✅ Cart mapped with {len(result.get('cart', []))} items")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"❌ Cart mapping JSON parse failed: {e}")
        return {"cart": [], "error": str(e)}
