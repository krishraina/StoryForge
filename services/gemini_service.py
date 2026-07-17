"""
services/gemini_service.py
Sequential generation with retry logic. Uses new google-genai SDK.
"""

import time
import random
import logging
from google import genai
from google.genai import types

from core.config import settings
from services.prompt_builder import build_prompt
from core.constants import STORY_FORMATS

logger = logging.getLogger(__name__)


def _get_client():
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _classify_gemini_error(exc: Exception) -> str:
    """
    Maps a raw Gemini/SDK exception to a short, editor-friendly message.
    Uses the same keyword signals as the retry classifier above, so the
    "why did this fail" story stays consistent with the "should we retry"
    decision — this function only changes what's *displayed*, never the
    retry/backoff behaviour itself.
    """
    exc_str = str(exc).lower()

    if any(k in exc_str for k in ("429", "quota", "resource_exhausted")):
        return "Daily Gemini quota reached. Please try again later."
    if any(k in exc_str for k in ("rate", "too many")):
        return "Too many requests. Please wait a moment and retry."
    if "timeout" in exc_str or "deadline" in exc_str:
        return "Generation timed out. Please retry."
    if any(k in exc_str for k in ("503", "unavailable", "connection", "network")):
        return "Unable to contact Gemini service. Please check your connection and retry."
    return "Generation failed due to an unexpected error. Please retry."


def generate_story(participant: dict, fmt: str) -> dict:
    prompt = build_prompt(participant, fmt)
    last_error = None

    for attempt in range(1, settings.GEMINI_RETRY_ATTEMPTS + 1):
        try:
            client = _get_client()
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.85,
                    max_output_tokens=4096,
                ),
            )

            content = (response.text or "").strip()

            if not content:
                return {"error": "Empty response from AI model.", "prompt": prompt}

            # Check whether the model stopped because it ran out of tokens
            # (= a truncated / mid-sentence story) rather than finishing naturally.
            finish_reason = None
            if response.candidates:
                finish_reason = getattr(response.candidates[0], "finish_reason", None)
                finish_reason = str(finish_reason) if finish_reason else None

            if finish_reason and "MAX_TOKENS" in finish_reason:
                last_error = "Response was cut off before completing (hit token limit)."
                if attempt < settings.GEMINI_RETRY_ATTEMPTS:
                    logger.warning(
                        "Truncated response (MAX_TOKENS) attempt %d/%d, retrying...",
                        attempt, settings.GEMINI_RETRY_ATTEMPTS,
                    )
                    time.sleep(settings.GEMINI_RETRY_DELAY_BASE)
                    continue
                else:
                    return {
                        "error": (
                            "Generation kept getting cut off before finishing "
                            f"(after {settings.GEMINI_RETRY_ATTEMPTS} attempts). "
                            "The partial text below was kept — you can edit it "
                            "manually or try Regenerate."
                        ),
                        "content": content,  # keep partial content, still editable
                        "prompt": prompt,
                    }

            return {"content": content, "prompt": prompt}

        except Exception as exc:
            last_error = exc
            exc_str = str(exc).lower()
            is_retryable = any(k in exc_str for k in (
                "429", "quota", "rate", "resource_exhausted",
                "too many", "503", "unavailable", "timeout"
            ))
            if is_retryable and attempt < settings.GEMINI_RETRY_ATTEMPTS:
                delay = settings.GEMINI_RETRY_DELAY_BASE * (2 ** (attempt - 1)) + random.uniform(0, 1.5)
                logger.warning("Gemini error attempt %d/%d, retrying in %.1fs: %s", attempt, settings.GEMINI_RETRY_ATTEMPTS, delay, exc)
                time.sleep(delay)
            else:
                break

    # Friendly message for the editor; raw exception kept in detail for logs.
    if isinstance(last_error, Exception):
        friendly = _classify_gemini_error(last_error)
        detail = str(last_error)
    else:
        # last_error is the MAX_TOKENS string set above, or None
        friendly = str(last_error) if last_error else "Generation failed for an unknown reason."
        detail = friendly

    return {
        "error": friendly,
        "error_detail": detail,
        "prompt": prompt,
    }


def generate_stories_sequential(participant: dict, formats: list, progress_callback=None) -> dict:
    results = {}
    total = len(formats)

    for idx, fmt in enumerate(formats):
        if progress_callback:
            progress_callback(fmt, idx, total, "generating")

        result = generate_story(participant, fmt)
        results[fmt] = result

        status = "success" if "content" in result and "error" not in result else "error"
        if progress_callback:
            progress_callback(fmt, idx + 1, total, status)

        if idx < total - 1:
            time.sleep(settings.GEMINI_SEQUENTIAL_DELAY)

    return results


def is_api_configured() -> bool:
    return bool(settings.GEMINI_API_KEY)


def count_words(text: str) -> int:
    return len(text.split()) if text else 0