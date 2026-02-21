import os
import re
import json
import anthropic
from loguru import logger
from app_redis.cache import get_cache, set_cache, make_key
from dotenv import load_dotenv
from utils.config import get_secret

load_dotenv()

SYSTEM_PROMPT = """
You are a grocery normalization AI. Convert raw ingredient names 
into clean, standardized grocery-store product names.

Rules:
- Strip brand names
- Resolve synonyms (EVOO → olive oil)
- Standardize units (tbsp → tablespoon)
- Convert vague amounts ("handful" → "1 cup", "splash" → "1 tablespoon")
- Add category tag: produce, dairy, meat, pantry, spice, frozen, other

Return ONLY valid JSON:
{
  "normalized": [
    {
      "original": "EVOO",
      "normalized_name": "olive oil",
      "quantity": 2,
      "unit": "tablespoon",
      "category": "pantry",
      "optional": false
    }
  ]
}
"""


def run_normalization(extracted_data: dict) -> dict:
    """
    Claude Agent #2 — Normalize and standardize ingredient list.
    """
    ingredients = extracted_data.get("ingredients", [])
    cache_key = make_key("normalization", json.dumps(ingredients, sort_keys=True))
    cached = get_cache(cache_key)
    if cached:
        logger.info("⚡ Normalization: Using cached result")
        return cached

    logger.info("🔧 Claude #2: Normalizing ingredients...")

    client = anthropic.Anthropic(api_key=get_secret("ANTHROPIC_API_KEY"))
    message = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5"),
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Normalize these ingredients:\n\n{json.dumps(ingredients, indent=2)}"
            }
        ]
    )

    raw_response = message.content[0].text
    try:
        cleaned = re.sub(r"```(?:json)?|```", "", raw_response).strip()
        result = json.loads(cleaned)
        set_cache(cache_key, result, 86400)
        logger.success(f"✅ Normalized {len(result.get('normalized', []))} ingredients")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"❌ Normalization JSON parse failed: {e}")
        return {"normalized": [], "error": str(e)}
