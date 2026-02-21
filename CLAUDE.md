# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A multi-agent AI pipeline that converts YouTube cooking videos into structured recipes with shopping lists and nutrition data. It uses Claude (Anthropic) as the backbone for 4 sequential AI agents, with Redis for caching and job queuing.

## Running the Project

```bash
# Validate environment, imports, Redis connection, and Anthropic client
python test_setup.py

# Run the interactive pipeline (prompts for a YouTube URL)
python main.py

# Install dependencies
pip install -r requirements.txt
```

There is no formal test suite or Makefile. `test_setup.py` is the closest equivalent to a health check.

## Required Environment Variables

Copy `.env` and fill in API keys before running:

- `ANTHROPIC_API_KEY` — Claude API
- `INSTACART_API_KEY` / `INSTACART_BASE_URL`
- `USDA_API_KEY` / `USDA_BASE_URL` — FoodData Central
- `NUTRITIONIX_APP_ID` / `NUTRITIONIX_API_KEY`
- `REDIS_URL` — defaults to `redis://localhost:6379/0`
- `CLAUDE_MODEL` — defaults to `claude-sonnet-4-5`
- TTL variables: `TRANSCRIPT_TTL`, `EXTRACTION_TTL`, `NUTRITION_TTL`, `INSTACART_TTL`

Redis must be running locally before launching the pipeline.

## Pipeline Architecture

`main.py` orchestrates 6 sequential steps with Redis state tracking per `video_id`. Completed steps are skipped automatically on re-runs.

```
YouTube URL
  → 1. Transcript Extraction   (services/transcript.py, cached 24h)
  → 2. Ingredient Extraction   (agents/extractor.py — Claude Agent #1)
  → 3. Normalization           (agents/normalizer.py — Claude Agent #2)
  → 4. Instacart Mapping       (agents/cart_agent.py — Claude Agent #3)
  → 5. Nutrition Calculation   (services/nutrition.py, USDA API, cached 12h)
  → 6. Recipe Composition      (agents/recipe_composer.py — Claude Agent #4)
  → output/{video_id}_recipe.json
```

## Key Module Responsibilities

| Module | Role |
|---|---|
| `agents/extractor.py` | Claude prompt → structured JSON with ingredients, quantities, servings |
| `agents/normalizer.py` | Standardizes ingredient names, resolves synonyms, tags by category (produce/dairy/meat/pantry/spice/frozen) |
| `agents/cart_agent.py` | Maps normalized ingredients to Instacart products using user preferences |
| `agents/recipe_composer.py` | Generates final publication-ready recipe JSON (timing, instructions, nutrition, storage tips) |
| `services/transcript.py` | Fetches YouTube transcript via `YouTubeTranscriptApi`; yt-dlp/Whisper fallback (partially implemented) |
| `services/nutrition.py` | Queries USDA FoodData Central with retry logic (tenacity, exponential backoff) |
| `services/instacart.py` | Instacart product search (partially implemented — marked for Step 4-5 completion) |
| `redis/cache.py` | Generic TTL-based caching with MD5 key hashing |
| `redis/state.py` | Pipeline step status tracking and user preferences persistence per video |
| `redis/queue.py` | RQ job queue setup (6 queues: transcript, extraction, normalizer, cart, nutrition, recipe) |
| `utils/helpers.py` | YouTube video ID extraction, safe JSON parsing (strips markdown fences), recipe→Markdown formatting, text chunking for Claude context windows |

## Important Implementation Notes

- **Local package naming**: The `app_redis/` directory contains the project's own Redis helpers. It was originally named `redis/` which shadowed the installed `redis` library — do NOT rename it back.
- **Grocery backend**: Despite what some comments say, the code uses **Kroger API** as primary and **Open Food Facts** as fallback. There is no Instacart integration; the `INSTACART_API_KEY` env var is unused.
- **Transcript API**: `youtube-transcript-api` 1.2.4+ uses an instance-based API (`ytt = YouTubeTranscriptApi(); ytt.fetch(video_id)`). Many videos return `VideoUnavailable` due to YouTube bot detection — this is a YouTube-side restriction, not a code bug.
- **Claude responses**: All agents strip markdown fences before JSON parsing with `re.sub(r"```(?:json)?|```", "", raw_response).strip()`. Always do this — Claude wraps JSON in fences even when instructed not to.
- **Redis fallback**: `app_redis/cache.py` and `app_redis/state.py` fall back to `fakeredis` (in-memory) if no Redis server is reachable. Install with `pip install fakeredis`.
- **Nutrition field names**: Normalized ingredients use `normalized_name` (not `name`). All USDA lookups in `services/nutrition.py` use `ingredient.get("normalized_name", ingredient.get("name", ""))`.
- **Logging**: Uses `loguru` with colored emoji-prefixed log levels throughout. Add new log calls with `from loguru import logger`.
- **Retry pattern**: External API calls use `tenacity` with exponential backoff (see `services/nutrition.py` as the reference implementation).
