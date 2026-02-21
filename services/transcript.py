import os
from xml.etree.ElementTree import ParseError
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled, VideoUnavailable
from loguru import logger
from app_redis.cache import get_cache, set_cache, make_key
from dotenv import load_dotenv

load_dotenv()

TTL = int(os.getenv("REDIS_TTL_TRANSCRIPT", 86400))


def get_transcript(video_id: str) -> dict:
    """
    Fetch YouTube transcript with Redis caching.
    Falls back to yt-dlp + Whisper if no transcript available.
    """
    cache_key = make_key("transcript", video_id)
    cached = get_cache(cache_key)
    if cached:
        return cached

    logger.info(f"🎬 Fetching transcript for: {video_id}")

    try:
        ytt = YouTubeTranscriptApi()
        raw = ytt.fetch(video_id)
        full_text = " ".join([s.text for s in raw])
        segments = [{"text": s.text, "start": s.start, "duration": s.duration} for s in raw]
        result = {
            "video_id": video_id,
            "text": full_text,
            "segments": segments,
            "source": "youtube_api"
        }
        set_cache(cache_key, result, TTL)
        logger.success(f"✅ Transcript fetched ({len(full_text)} chars)")
        return result

    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable, ParseError, Exception):
        logger.warning("⚠️ No transcript — falling back to Whisper (yt-dlp)")
        return _whisper_fallback(video_id, cache_key)


def _whisper_fallback(video_id: str, cache_key: str) -> dict:
    """
    Fallback: Download audio via yt-dlp, transcribe with Whisper.
    Requires: pip install openai-whisper
    """
    # ── Placeholder — implemented in Step 2 ──────────────────
    logger.warning("🔧 Whisper fallback not yet implemented")
    return {
        "video_id": video_id,
        "text": "",
        "segments": [],
        "source": "whisper_pending"
    }
