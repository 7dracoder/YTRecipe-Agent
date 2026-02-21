import os
import re
import json
import anthropic
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """
You are a professional recipe writer AI. Generate a clean, complete, 
publication-ready recipe from the provided ingredients, transcript, and nutrition data.

Include:
- Recipe name
- Prep time and cook time
- Serving size
- Ingredients as plain strings (e.g. "2 tablespoons olive oil", "3 cloves garlic, minced") — NOT objects or dicts
- Step-by-step instructions (inferred from transcript)
- Calories per serving
- Full nutrition info
- Storage instructions
- Serving suggestions

Return ONLY valid JSON in this format:
{
  "recipe": {
    "name": "string",
    "prep_time_minutes": 10,
    "cook_time_minutes": 30,
    "servings": 4,
    "calories_per_serving": 450,
    "ingredients": ["2 tablespoons olive oil", "3 cloves garlic, minced"],
    "instructions": ["Step 1...", "Step 2..."],
    "nutrition": {},
    "storage": "string",
    "serving_suggestions": "string"
  }
}
"""


def run_recipe_composition(transcript: dict, ingredients: dict, nutrition: dict) -> dict:
    """
    Claude Agent #4 — Generate the final polished recipe.
    """
    logger.info("📖 Claude #4: Composing final recipe...")

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    message = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5"),
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Transcript:\n{transcript.get('text', '')[:8000]}\n\n"
                    f"Ingredients:\n{json.dumps(ingredients, indent=2)}\n\n"
                    f"Nutrition Data:\n{json.dumps(nutrition, indent=2)}"
                )
            }
        ]
    )

    raw_response = message.content[0].text
    try:
        cleaned = re.sub(r"```(?:json)?|```", "", raw_response).strip()
        result = json.loads(cleaned)
        logger.success("✅ Final recipe generated")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"❌ Recipe composition JSON parse failed: {e}")
        return {"recipe": {}, "error": str(e)}
