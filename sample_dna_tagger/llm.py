"""
LLM Layer — sends structured audio features to an OpenAI-compatible endpoint
and receives expressive semantic tags in return.

The LLM never sees raw audio. It receives only:
- The structured feature vector from the scanner (BPM, key, spectral data)
- The instrument classification result

Returns tags for: energy, texture, mood, emotional quality, motion,
plus refined instrument type/subtype classification.

Configuration is persisted in the `settings` table of the SQLite database.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Optional

import openai

from sample_dna_tagger import db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

TAGGING_SYSTEM_PROMPT = """You are an audio analysis expert for music producers. You receive structured audio features extracted from a single audio sample and return expressive semantic tags. The features include an instrument_category detected by a local classifier — use it to refine instrument_type and instrument_subtype instead of guessing from scratch.

IMPORTANT RULES:
- Respond with ONLY a JSON object. No markdown, no explanation, no code fences.
- All tag values must be valid JSON strings or null.
- If you're uncertain about a tag, use null rather than guessing.
- Be specific and musically useful — a producer is searching their library with these tags.
- Use the instrument_category as a starting point, then refine based on the audio features.

Return this exact JSON structure:
{
  "energy": "low" | "medium" | "high" | null,
  "texture": "smooth" | "gritty" | "glassy" | "warm" | "cold" | "airy" | "dense" | "crisp" | "fuzzy" | "metallic" | "woody" | "organic" | null,
  "mood": "dark" | "bright" | "tense" | "calm" | "euphoric" | "melancholic" | "mysterious" | "playful" | "aggressive" | null,
  "emotional_quality": "aggressive" | "peaceful" | "anxious" | "hopeful" | "cinematic" | "dreamy" | "intense" | "nostalgic" | null,
  "motion": "static" | "evolving" | "pulsing" | "rising" | "falling" | "swinging" | "erratic" | null,
  "instrument_type": refined type e.g. "Punchy Kick", "Crisp Hi-hat", "Warm Pad", "Pluck Bass" | null,
  "instrument_subtype": refined subtype e.g. "Sub Kick", "Open Hi-hat", "Analog Pad", "808 Bass" | null,
  "descriptive_tags": [array of 2-5 short descriptive words/phrases]
}

---
EXAMPLES OF GOOD RESPONSES:

Example 1 — Kick drum:
Input features: {"rms_energy": 0.78, "spectral_centroid": 120.5, "spectral_flatness": 0.12, "zero_crossing_rate": 0.03, "bpm": 140, "key": null, "instrument_category": "kick"}
Response:
{
  "energy": "high",
  "texture": "woody",
  "mood": "aggressive",
  "emotional_quality": "intense",
  "motion": "pulsing",
  "instrument_type": "Punchy Kick",
  "instrument_subtype": "Hardstyle Kick",
  "descriptive_tags": ["punchy", "low-end", "transient-heavy", "distorted"]
}

Example 2 — Pad:
Input features: {"rms_energy": 0.32, "spectral_centroid": 840.3, "spectral_flatness": 0.41, "zero_crossing_rate": 0.18, "bpm": null, "key": "A minor", "instrument_category": "pad"}
Response:
{
  "energy": "low",
  "texture": "airy",
  "mood": "calm",
  "emotional_quality": "dreamy",
  "motion": "evolving",
  "instrument_type": "Warm Pad",
  "instrument_subtype": "Analog Pad",
  "descriptive_tags": ["lush", "evolving", "ambient", "cinematic"]
}

Example 3 — Hi-hat:
Input features: {"rms_energy": 0.15, "spectral_centroid": 6200.0, "spectral_flatness": 0.68, "zero_crossing_rate": 0.52, "bpm": null, "key": null, "instrument_category": "hihat"}
Response:
{
  "energy": "medium",
  "texture": "crisp",
  "mood": "bright",
  "emotional_quality": null,
  "motion": "static",
  "instrument_type": "Crisp Hi-hat",
  "instrument_subtype": "Closed Hi-hat",
  "descriptive_tags": ["bright", "short", "metallic", "sizzle"]
}
---"""

SEARCH_QUERY_SYSTEM_PROMPT = """You are a search query parser for a music sample library. You receive a natural-language search query from a music producer and return structured audio filters.

The available filter dimensions are:
- energy: "low" | "medium" | "high"
- texture: "smooth" | "gritty" | "glassy" | "warm" | "cold" | "airy" | "dense" | "crisp" | "fuzzy" | "metallic" | "woody" | "organic"
- mood: "dark" | "bright" | "tense" | "calm" | "euphoric" | "melancholic" | "mysterious" | "playful" | "aggressive"
- emotional_quality: "aggressive" | "peaceful" | "anxious" | "hopeful" | "cinematic" | "dreamy" | "intense" | "nostalgic"
- motion: "static" | "evolving" | "pulsing" | "rising" | "falling" | "swinging" | "erratic"
- frequency_range: "sub" | "low" | "low-mid" | "mid" | "mid-high" | "high" | "air"
- instrument_type: any string (partial match against instrument_type field)
- instrument_category: "kick" | "snare" | "clap" | "hihat" | "cymbal" | "tom" | "percussion" | "bass" | "synth" | "pad" | "lead" | "pluck" | "keys" | "piano" | "organ" | "guitar" | "strings" | "brass" | "woodwind" | "vocal" | "fx" | "texture" | "drone" | "loop" | "one_shot"
- transients: "sharp" | "soft" | "none" — use "any" when the user says "no transients"
- bpm_min, bpm_max: numeric BPM range
- key: any string (musical key, e.g. "C minor", "F#")

For each filter, include:
- "dimension": the dimension name
- "value": the value (string or number)
- "negate": true if the user is excluding or saying "no XYZ", false otherwise

IMPORTANT RULES:
- Respond with ONLY a JSON object. No markdown, no explanation.
- If the user says "no transients" or "without transients", set dimension="transients", value="any", negate=true.
- If the user says "high tension", that maps to mood="tense" with negate=false.
- "mid-high range" maps to frequency_range="mid-high".
- If a dimension is not mentioned, do NOT include it in the filters array.
- For BPM queries like "120-140 bpm", split into bpm_min=120 and bpm_max=140.
- For key queries like "in C minor", set dimension="key", value="C minor".

Return this exact JSON structure:
{
  "filters": [
    {"dimension": "...", "value": "...", "negate": false},
    ...
  ]
}

---
EXAMPLES:

Query: "high energy, dark mood, no transients"
Response:
{
  "filters": [
    {"dimension": "energy", "value": "high", "negate": false},
    {"dimension": "mood", "value": "dark", "negate": false},
    {"dimension": "transients", "value": "any", "negate": true}
  ]
}

Query: "warm pads in C minor at 80-100 bpm"
Response:
{
  "filters": [
    {"dimension": "texture", "value": "warm", "negate": false},
    {"dimension": "instrument_category", "value": "pad", "negate": false},
    {"dimension": "key", "value": "C minor", "negate": false},
    {"dimension": "bpm_min", "value": 80, "negate": false},
    {"dimension": "bpm_max", "value": 100, "negate": false}
  ]
}

Query: "aggressive kicks with sharp transients"
Response:
{
  "filters": [
    {"dimension": "emotional_quality", "value": "aggressive", "negate": false},
    {"dimension": "instrument_category", "value": "kick", "negate": false},
    {"dimension": "transients", "value": "sharp", "negate": false}
  ]
}
---"""


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------

class LLMClient:
    """Wraps an OpenAI-compatible client for tag generation and query parsing.

    Configuration is persisted in the SQLite `settings` table under these keys:
      - llm_base_url
      - llm_api_key
      - llm_model
    """

    SETTINGS_KEY_BASE_URL = "llm_base_url"
    SETTINGS_KEY_API_KEY = "llm_api_key"
    SETTINGS_KEY_MODEL = "llm_model"
    SETTINGS_KEY_RATE_LIMIT = "llm_calls_per_minute"

    def __init__(self):
        self._client: Optional[openai.AsyncOpenAI] = None
        self._base_url: Optional[str] = None
        self._api_key: Optional[str] = None
        self._model: str = "deepseek-chat"
        self._calls_per_minute: int = 0
        self._rate_semaphore: Optional[asyncio.Semaphore] = None
        self._configured: bool = False

    # ------------------------------------------------------------------
    # Configuration persistence
    # ------------------------------------------------------------------

    async def load_config(self) -> dict:
        """Read LLM configuration from the database settings table.

        Returns a dict with base_url, api_key, model, calls_per_minute.
        If no settings exist, returns defaults with empty strings.
        """
        try:
            conn = await db.get_connection()
            try:
                rows = await conn.execute_fetchall(
                    "SELECT key, value FROM settings WHERE key IN (?, ?, ?, ?)",
                    (
                        self.SETTINGS_KEY_BASE_URL,
                        self.SETTINGS_KEY_API_KEY,
                        self.SETTINGS_KEY_MODEL,
                        self.SETTINGS_KEY_RATE_LIMIT,
                    ),
                )
                settings = {row["key"]: row["value"] for row in rows}

                base_url = settings.get(self.SETTINGS_KEY_BASE_URL, "")
                api_key = settings.get(self.SETTINGS_KEY_API_KEY, "")
                model = settings.get(self.SETTINGS_KEY_MODEL, "deepseek-chat")
                rate_limit_str = settings.get(self.SETTINGS_KEY_RATE_LIMIT, "0")

                self._base_url = base_url or None
                self._api_key = api_key or None
                self._model = model or "deepseek-chat"

                try:
                    self._calls_per_minute = int(rate_limit_str)
                except (ValueError, TypeError):
                    self._calls_per_minute = 0

                self._recreate_client()
                self._configured = bool(self._base_url and self._api_key)

                if self._configured:
                    logger.info(
                        "LLM config loaded: model=%s base_url=%s calls_per_minute=%d",
                        self._model,
                        self._base_url,
                        self._calls_per_minute,
                    )

                return {
                    "base_url": self._base_url or "",
                    "api_key": "***" if self._api_key else "",
                    "model": self._model,
                    "calls_per_minute": self._calls_per_minute,
                }
            finally:
                await conn.close()
        except Exception:
            logger.exception("Failed to load LLM config from database")
            return {
                "base_url": self._base_url or "",
                "api_key": "***" if self._api_key else "",
                "model": self._model,
                "calls_per_minute": self._calls_per_minute,
            }

    async def configure(
        self,
        base_url: str,
        api_key: str,
        model: str,
        calls_per_minute: int = 0,
    ) -> None:
        """Set or update the API endpoint configuration and persist to database."""
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._calls_per_minute = calls_per_minute
        self._recreate_client()
        self._configured = bool(base_url and api_key)

        # Persist to database
        try:
            conn = await db.get_connection()
            try:
                await conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (self.SETTINGS_KEY_BASE_URL, base_url),
                )
                await conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (self.SETTINGS_KEY_API_KEY, api_key),
                )
                await conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (self.SETTINGS_KEY_MODEL, model),
                )
                await conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (self.SETTINGS_KEY_RATE_LIMIT, str(calls_per_minute)),
                )
                await conn.commit()
                logger.info("LLM config persisted: model=%s", model)
            finally:
                await conn.close()
        except Exception:
            logger.exception("Failed to persist LLM config to database")

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------

    async def test_connection(self) -> dict:
        """Test the LLM connection. Returns {"ok": true, "model": "..."} or
        {"ok": false, "error": "..."}."""
        if self._client is None:
            return {
                "ok": False,
                "error": "Not configured — set base URL and API key first",
            }

        try:
            response = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": "Respond with exactly: pong"}],
                    max_tokens=5,
                    temperature=0,
                ),
                timeout=15,
            )
            return {
                "ok": True,
                "model": self._model,
                "response": response.choices[0].message.content,
            }
        except Exception as e:
            logger.warning("LLM connection test failed: %s", e)
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Tag generation (single sample)
    # ------------------------------------------------------------------

    async def generate_tags(self, features: dict) -> dict:
        """Send structured audio features to the LLM and return parsed tags.

        Injects the detected instrument_category into the prompt so the LLM
        can refine rather than guess. Includes retry with exponential
        backoff, timeout, and partial-result fallback.
        """
        if not self._configured or self._client is None:
            raise RuntimeError("LLM client not configured — call configure() or load_config() first")

        instrument_category = features.get("instrument_category", "unknown")
        prompt = TAGGING_SYSTEM_PROMPT.replace(
            "{instrument_category}", instrument_category
        )

        features_json = json.dumps(features, indent=2)
        user_message = (
            f'Analyze these audio features and return semantic tags.\n\n'
            f'The scanner detected instrument_category = "{instrument_category}". '
            f'Use this as a starting point for instrument_type and instrument_subtype.\n\n'
            f"{features_json}"
        )

        try:
            result = await self._call_with_retry(
                system_prompt=prompt,
                user_message=user_message,
                temperature=0.3,
                max_tokens=500,
            )
            return result
        except Exception as e:
            logger.error(
                "Tag generation failed after all retries for %s: %s",
                features.get("filename", "unknown"),
                e,
            )
            # Return partial result — features without AI tags
            return {
                "energy": None,
                "texture": None,
                "mood": None,
                "emotional_quality": None,
                "motion": None,
                "instrument_type": None,
                "instrument_subtype": None,
                "descriptive_tags": [],
                "_error": str(e),
            }

    # ------------------------------------------------------------------
    # Batch tag generation
    # ------------------------------------------------------------------

    async def generate_tags_batch(self, features_list: list[dict]) -> list[dict]:
        """Tag multiple samples in a single LLM call to reduce API costs.

        Each item in features_list is a feature dict (same format as
        generate_tags). Returns a list of tag dicts in the same order.
        """
        if not features_list:
            return []

        if not self._configured or self._client is None:
            raise RuntimeError("LLM client not configured — call configure() or load_config() first")

        # Build a single message with all samples
        prompt = TAGGING_SYSTEM_PROMPT

        samples_text = ""
        for i, features in enumerate(features_list):
            instrument_category = features.get("instrument_category", "unknown")
            samples_text += (
                f"\n--- Sample {i + 1} ---\n"
                f"instrument_category: {instrument_category}\n"
                f"{json.dumps(features, indent=2)}\n"
            )

        user_message = (
            f"Analyze {len(features_list)} audio samples and return semantic tags "
            f"for each one. Return a JSON array with one object per sample, "
            f"in the same order.\n\n{samples_text}\n\n"
            f"Respond with ONLY a JSON array: [{{...}}, {{...}}, ...]"
        )

        try:
            result = await self._call_with_retry(
                system_prompt=prompt,
                user_message=user_message,
                temperature=0.3,
                max_tokens=500 * max(1, len(features_list)),
            )

            # If the LLM returned an array, return it directly
            if isinstance(result, list):
                # Pad or trim to match input length
                if len(result) < len(features_list):
                    logger.warning(
                        "Batch tag response has %d items but %d were requested; "
                        "padding with error entries",
                        len(result),
                        len(features_list),
                    )
                    for _ in range(len(features_list) - len(result)):
                        result.append({
                            "energy": None, "texture": None, "mood": None,
                            "emotional_quality": None, "motion": None,
                            "instrument_type": None, "instrument_subtype": None,
                            "descriptive_tags": [], "_error": "missing_from_batch",
                        })
                return result[: len(features_list)]

            # If the LLM returned a single object (shouldn't happen, but handle it)
            logger.warning("Batch tag call returned a single object; wrapping in list")
            return [result] + [
                {
                    "energy": None, "texture": None, "mood": None,
                    "emotional_quality": None, "motion": None,
                    "instrument_type": None, "instrument_subtype": None,
                    "descriptive_tags": [], "_error": "missing_from_batch",
                }
                for _ in range(len(features_list) - 1)
            ]

        except Exception as e:
            logger.error("Batch tag generation failed: %s", e)
            # Return partial results: features without tags
            empty_tag = {
                "energy": None, "texture": None, "mood": None,
                "emotional_quality": None, "motion": None,
                "instrument_type": None, "instrument_subtype": None,
                "descriptive_tags": [], "_error": str(e),
            }
            return [empty_tag for _ in features_list]

    # ------------------------------------------------------------------
    # Search query parsing
    # ------------------------------------------------------------------

    async def parse_search_query(self, query: str) -> dict:
        """Parse a natural-language search query into structured audio filters.

        Sends the query to the LLM and returns a dict with a "filters" key
        containing an array of filter objects, each with dimension, value,
        and negate fields.
        """
        if not self._configured or self._client is None:
            raise RuntimeError("LLM client not configured — call configure() or load_config() first")

        try:
            result = await self._call_with_retry(
                system_prompt=SEARCH_QUERY_SYSTEM_PROMPT,
                user_message=f"Parse this search query into structured audio filters:\n\n{query}",
                temperature=0.0,  # Deterministic for query parsing
                max_tokens=300,
            )

            if not isinstance(result, dict) or "filters" not in result:
                logger.warning(
                    "Search query parse returned unexpected structure: %s",
                    str(result)[:200],
                )
                return {"filters": [], "_raw": result}

            return result

        except Exception as e:
            logger.error("Search query parsing failed: %s", e)
            return {"filters": [], "_error": str(e)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _recreate_client(self) -> None:
        """Recreate the OpenAI client with current settings."""
        if self._base_url and self._api_key:
            self._client = openai.AsyncOpenAI(
                base_url=self._base_url,
                api_key=self._api_key,
                timeout=30.0,
            )
        else:
            self._client = None

        # Set up rate-limiter semaphore
        if self._calls_per_minute > 0:
            self._rate_semaphore = asyncio.Semaphore(self._calls_per_minute)
        else:
            self._rate_semaphore = None

    async def _acquire_rate_limit(self) -> None:
        """Wait until a rate-limit slot is available, if rate limiting is active."""
        if self._rate_semaphore is not None:
            await self._rate_semaphore.acquire()
            # Schedule release after 60 seconds
            asyncio.create_task(self._release_rate_limit())

    async def _release_rate_limit(self) -> None:
        """Release a rate-limit slot after 60 seconds."""
        await asyncio.sleep(60)
        if self._rate_semaphore is not None:
            self._rate_semaphore.release()

    async def _call_with_retry(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float,
        max_tokens: int,
        max_retries: int = 3,
    ) -> dict | list:
        """Call the LLM with exponential-backoff retry on transient errors.

        Args:
            system_prompt: The system message for the LLM.
            user_message: The user message.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the response.
            max_retries: Number of retry attempts (default 3).

        Returns:
            Parsed JSON response (dict or list).

        Raises:
            RuntimeError: If client is not configured.
            Exception: On persistent failure after all retries.
        """
        if self._client is None:
            raise RuntimeError("LLM client is not configured")

        last_error: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                # Rate-limit gate
                await self._acquire_rate_limit()

                response = await asyncio.wait_for(
                    self._client.chat.completions.create(
                        model=self._model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message},
                        ],
                        temperature=temperature,
                        max_tokens=max_tokens,
                    ),
                    timeout=30.0,
                )

                content = response.choices[0].message.content or "{}"
                return self._parse_llm_json(content)

            except asyncio.TimeoutError:
                last_error = asyncio.TimeoutError(
                    f"LLM call timed out after 30s (attempt {attempt + 1}/{max_retries})"
                )
                logger.warning("LLM call timed out (attempt %d/%d)", attempt + 1, max_retries)

            except openai.APIError as e:
                last_error = e
                # Only retry on transient errors (rate limits, server errors)
                if getattr(e, "status_code", 0) not in (429, 500, 502, 503, 504):
                    logger.error("Non-retryable API error: %s", e)
                    raise
                logger.warning(
                    "LLM API error (attempt %d/%d, status=%s): %s",
                    attempt + 1,
                    max_retries,
                    getattr(e, "status_code", "?"),
                    e,
                )

            except (json.JSONDecodeError, KeyError, AttributeError) as e:
                last_error = e
                logger.warning(
                    "LLM response parse failed (attempt %d/%d): %s",
                    attempt + 1,
                    max_retries,
                    e,
                )

            except Exception as e:
                last_error = e
                logger.warning(
                    "LLM call failed (attempt %d/%d): %s",
                    attempt + 1,
                    max_retries,
                    e,
                )

            # Exponential backoff with jitter before retry
            if attempt < max_retries - 1:
                delay = (2 ** attempt) + random.uniform(0, 1)
                logger.info("Retrying in %.1fs...", delay)
                await asyncio.sleep(delay)

        # All retries exhausted
        raise last_error or RuntimeError("LLM call failed after all retries")

    @staticmethod
    def _parse_llm_json(content: str) -> dict | list:
        """Parse JSON from LLM response, stripping markdown code fences if present."""
        content = content.strip()

        # Strip markdown code fences
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove opening fence (```json or ```)
            if lines[0].startswith("```"):
                lines = lines[1:]
            # Remove closing fence
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        return json.loads(content)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

llm_client = LLMClient()
