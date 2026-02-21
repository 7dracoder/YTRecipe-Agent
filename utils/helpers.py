import re
import json
from loguru import logger


def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from any URL format."""
    patterns = [
        r"v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"embed/([a-zA-Z0-9_-]{11})"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from: {url}")


def safe_parse_json(text: str, fallback: dict = {}) -> dict:
    """Parse JSON safely, returning fallback if parsing fails."""
    try:
        # Strip markdown code fences if Claude wrapped in ```json
        cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed: {e}")
        return fallback


def format_recipe_markdown(recipe: dict) -> str:
    """Convert recipe JSON into clean Markdown string for display."""
    r = recipe.get("recipe", {})
    lines = [
        f"# {r.get('name', 'Recipe')}",
        f"**Prep:** {r.get('prep_time_minutes')} min | "
        f"**Cook:** {r.get('cook_time_minutes')} min | "
        f"**Serves:** {r.get('servings')}",
        f"**Calories per serving:** {r.get('calories_per_serving')} kcal",
        "\n## Ingredients"
    ]
    for ing in r.get("ingredients", []):
        lines.append(f"- {ing.get('quantity', '')} {ing.get('unit', '')} {ing.get('name', '')}")

    lines.append("\n## Instructions")
    for i, step in enumerate(r.get("instructions", []), 1):
        lines.append(f"{i}. {step}")

    lines.append(f"\n## Storage\n{r.get('storage', '')}")
    lines.append(f"\n## Serving Suggestions\n{r.get('serving_suggestions', '')}")
    return "\n".join(lines)


def chunk_text(text: str, max_chars: int = 8000) -> list:
    """Split long transcript into chunks for Claude's context window."""
    return [text[i:i+max_chars] for i in range(0, len(text), max_chars)]
