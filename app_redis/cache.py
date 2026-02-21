import redis
import json
import hashlib
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


def make_key(prefix: str, value: str) -> str:
    """Create a consistent, collision-safe Redis key."""
    hashed = hashlib.md5(value.encode()).hexdigest()
    return f"{prefix}:{hashed}"


def get_cache(key: str):
    """Retrieve a cached value. Returns None on miss."""
    try:
        data = r.get(key)
        if data:
            logger.debug(f"✅ Cache HIT  → {key}")
            return json.loads(data)
        logger.debug(f"❌ Cache MISS → {key}")
        return None
    except redis.RedisError as e:
        logger.warning(f"Redis read error: {e}")
        return None


def set_cache(key: str, value: dict, ttl: int):
    """Store a value in cache with expiration (TTL in seconds)."""
    try:
        r.setex(key, ttl, json.dumps(value))
        logger.debug(f"💾 Cached → {key} (TTL: {ttl}s)")
    except redis.RedisError as e:
        logger.warning(f"Redis write error: {e}")


def delete_cache(key: str):
    """Manually invalidate a cached entry."""
    r.delete(key)
    logger.debug(f"🗑️  Deleted cache → {key}")


def flush_all_cache():
    """⚠️ Wipes ALL Redis data. Use only in dev/testing."""
    r.flushall()
    logger.warning("⚠️  All Redis cache flushed")
