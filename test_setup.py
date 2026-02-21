import os
import redis
from dotenv import load_dotenv

load_dotenv()

print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("  SYSTEM SETUP VERIFICATION")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

# ── 1. Check imports ──────────────────────────────────────────
try:
    import anthropic
    import requests
    import rq
    from youtube_transcript_api import YouTubeTranscriptApi
    from loguru import logger
    from tenacity import retry
    from pydantic import BaseModel
    print("✅ All packages imported successfully")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    print("   Run: pip install -r requirements.txt")

# ── 2. Check env vars ─────────────────────────────────────────
keys = ["ANTHROPIC_API_KEY", "INSTACART_API_KEY", "USDA_API_KEY", "REDIS_URL"]
print()
for key in keys:
    val = os.getenv(key)
    status = "✅" if val else "❌ MISSING"
    masked = f"{val[:8]}..." if val else "NOT SET"
    print(f"{status} {key}: {masked}")

# ── 3. Check Redis connection ─────────────────────────────────
print()
try:
    r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                              decode_responses=True)
    r.ping()
    print("✅ Redis connected")
    r.set("test_key", "hello_world", ex=10)
    val = r.get("test_key")
    print(f"✅ Redis read/write OK → value: '{val}'")
except redis.exceptions.ConnectionError:
    print("❌ Redis not running!")
    print("   Start with: docker run -d -p 6379:6379 redis:alpine")

# ── 4. Check Anthropic key (without spending tokens) ─────────
print()
try:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    print("✅ Anthropic client initialized")
except Exception as e:
    print(f"❌ Anthropic client failed: {e}")

# ── 5. Check output folder ────────────────────────────────────
os.makedirs("output", exist_ok=True)
print("\n✅ Output folder ready")
print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("  Run 'python main.py' to start")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
