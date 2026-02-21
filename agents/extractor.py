import os
import re
import json
import anthropic
from loguru import logger
from app_redis.cache import get_cache, set_cache, make_key
from dotenv import load_dotenv
from utils.config import get_secret

load_dotenv()

TTL = int(os.getenv("REDIS_TTL_EXTRACTION", 86400))

SYSTEM_PROMPT = """
You are an expert culinary AI. Your task is to extract all ingredients 
from a cooking video transcript.

Return ONLY valid JSON — no extra text, no markdown, no explanation.

Output format:
{
  "ingredients": [
    {
      "name": "olive oil",
      "quantity": 2,
      "unit": "tablespoons",
      "optional": false,
      "is_garnish": false,
      "substitutions": []
    }
  ],
  "servings": 4,
  "dish_name": "Pasta Aglio e Olio"
}
"""


def run_extraction(transcript_data: dict) -> dict:
    """
    Claude Agent #1 — Extract structured ingredients from transcript.
    Results are cached in Redis by transcript hash.
    """
    transcript_text = transcript_data.get("text", "")
    cache_key = make_key("extraction", transcript_text[:500])
    cached = get_cache(cache_key)
    if cached:
        logger.info("⚡ Extraction: Using cached result")
        return cached

    logger.info("🤖 Claude #1: Extracting ingredients...")

    client = anthropic.Anthropic(api_key=get_secret("ANTHROPIC_API_KEY"))
    message = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5"),
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Extract all ingredients from this cooking transcript:\n\n{transcript_text}"
            }
        ]
    )

    raw_response = message.content[0].text
    try:
        cleaned = re.sub(r"```(?:json)?|```", "", raw_response).strip()
        result = json.loads(cleaned)
        set_cache(cache_key, result, TTL)
        logger.success(f"✅ Extracted {len(result.get('ingredients', []))} ingredients")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"❌ Claude returned invalid JSON: {e}")
        logger.debug(f"Raw response: {raw_response}")
        return {"ingredients": [], "error": str(e)}
