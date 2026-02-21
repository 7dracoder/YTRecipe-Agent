import os
from dotenv import load_dotenv
from loguru import logger
from services.transcript import get_transcript
from agents.extractor import run_extraction
from agents.normalizer import run_normalization
from agents.cart_agent import run_cart_mapping
from agents.recipe_composer import run_recipe_composition
from services.nutrition import get_nutrition_data
from app_redis.state import set_step, get_step, get_all_steps
import json


load_dotenv()

def run_pipeline(youtube_url: str, user_id: str = "default"):
    """
    Master pipeline controller.
    Each step checks Redis state before running.
    Skips already-completed steps automatically.
    """
    video_id = extract_video_id(youtube_url)
    logger.info(f"🚀 Starting pipeline for video: {video_id}")

    # ── Step 1: Transcript ─────────────────────────────────────
    if not get_step(video_id, "transcript_extracted"):
        logger.info("📝 Step 1: Extracting transcript...")
        transcript = get_transcript(video_id)
        set_step(video_id, "transcript_extracted", {"transcript": transcript})
    else:
        logger.info("⚡ Step 1: Skipping — transcript already cached")
        transcript = get_step(video_id, "transcript_extracted")["data"]["transcript"]

    # ── Step 2: Ingredient Extraction (Claude #1) ───────────────
    if not get_step(video_id, "ingredients_extracted"):
        logger.info("🤖 Step 2: Running Claude extraction agent...")
        ingredients = run_extraction(transcript)
        set_step(video_id, "ingredients_extracted", {"ingredients": ingredients})
    else:
        logger.info("⚡ Step 2: Skipping — ingredients already extracted")
        ingredients = get_step(video_id, "ingredients_extracted")["data"]["ingredients"]

    # ── Step 3: Normalization (Claude #2) ──────────────────────
    if not get_step(video_id, "ingredients_normalized"):
        logger.info("🔧 Step 3: Normalizing ingredients...")
        normalized = run_normalization(ingredients)
        set_step(video_id, "ingredients_normalized", {"normalized": normalized})
    else:
        logger.info("⚡ Step 3: Skipping — already normalized")
        normalized = get_step(video_id, "ingredients_normalized")["data"]["normalized"]

    # ── Step 4: Instacart Mapping (Claude #3) ──────────────────
    if not get_step(video_id, "instacart_mapped"):
        logger.info("🛒 Step 4: Mapping to Instacart products...")
        cart = run_cart_mapping(normalized, user_id=user_id)
        set_step(video_id, "instacart_mapped", {"cart": cart})
    else:
        logger.info("⚡ Step 4: Skipping — already mapped")
        cart = get_step(video_id, "instacart_mapped")["data"]["cart"]

    # ── Step 5: Nutrition Calculation ──────────────────────────
    if not get_step(video_id, "nutrition_calculated"):
        logger.info("🥗 Step 5: Calculating nutrition...")
        nutrition = get_nutrition_data(normalized.get("normalized", []))
        set_step(video_id, "nutrition_calculated", {"nutrition": nutrition})
    else:
        logger.info("⚡ Step 5: Skipping — nutrition already calculated")
        nutrition = get_step(video_id, "nutrition_calculated")["data"]["nutrition"]

    # ── Step 6: Final Recipe (Claude #4) ───────────────────────
    if not get_step(video_id, "recipe_generated"):
        logger.info("📖 Step 6: Composing final recipe...")
        recipe = run_recipe_composition(
            transcript=transcript,
            ingredients=normalized,
            nutrition=nutrition
        )
        set_step(video_id, "recipe_generated", {"recipe": recipe})
    else:
        logger.info("⚡ Step 6: Skipping — recipe already generated")
        recipe = get_step(video_id, "recipe_generated")["data"]["recipe"]

    # ── Save Output ────────────────────────────────────────────
    output_path = f"output/{video_id}_recipe.json"
    os.makedirs("output", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(recipe, f, indent=2)

    logger.success(f"✅ Pipeline complete! Recipe saved to {output_path}")
    return recipe


def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from any URL format."""
    import re
    patterns = [
        r"v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"embed/([a-zA-Z0-9_-]{11})"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from URL: {url}")


if __name__ == "__main__":
    url = input("Enter YouTube URL: ").strip()
    result = run_pipeline(url)
    print(json.dumps(result, indent=2))
