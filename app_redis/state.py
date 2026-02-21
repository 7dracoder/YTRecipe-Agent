import redis
import json
import os
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

try:
    r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
    r.ping()
except Exception:
    import fakeredis
    logger.warning("⚠️  Redis unavailable — using in-memory fakeredis")
    r = fakeredis.FakeRedis(decode_responses=True)

PIPELINE_STEPS = [
    "transcript_extracted",
    "ingredients_extracted",
    "ingredients_normalized",
    "instacart_mapped",
    "cart_ready",
    "nutrition_calculated",
    "recipe_generated"
]


def set_step(video_id: str, step: str, data: dict = {}):
    """Mark a pipeline step as complete and store its output."""
    key = f"pipeline:state:{video_id}"
    payload = json.dumps({"step": step, "data": data})
    r.hset(key, step, payload)
    r.expire(key, 86400)  # Auto-expire full pipeline state after 24h
    logger.info(f"📌 State saved → [{video_id}] {step}")


def get_step(video_id: str, step: str):
    """Get the stored output for a completed step. Returns None if not done."""
    key = f"pipeline:state:{video_id}"
    val = r.hget(key, step)
    return json.loads(val) if val else None


def get_all_steps(video_id: str) -> dict:
    """Get full pipeline status for a video."""
    key = f"pipeline:state:{video_id}"
    raw = r.hgetall(key)
    return {k: json.loads(v) for k, v in raw.items()}


def reset_pipeline(video_id: str):
    """Clear all state for a video — forces full re-run."""
    key = f"pipeline:state:{video_id}"
    r.delete(key)
    logger.warning(f"🔄 Pipeline state reset for {video_id}")


def save_user_preferences(user_id: str, prefs: dict):
    """Persist user preferences with no expiry (permanent)."""
    key = f"user:prefs:{user_id}"
    r.set(key, json.dumps(prefs))
    logger.info(f"👤 Saved preferences for user: {user_id}")


def get_user_preferences(user_id: str) -> dict:
    """Retrieve user preferences. Returns empty dict if none saved."""
    key = f"user:prefs:{user_id}"
    val = r.get(key)
    return json.loads(val) if val else {}


def update_user_preference(user_id: str, key_name: str, value):
    """Update a single preference key without overwriting everything."""
    prefs = get_user_preferences(user_id)
    prefs[key_name] = value
    save_user_preferences(user_id, prefs)
