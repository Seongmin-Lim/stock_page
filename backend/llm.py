"""Optional LLM layer (Google Gemini) — used ONLY for language tasks, never for numbers.

The app computes every score/factor/verdict deterministically in code; the LLM only turns
those into a fluent Korean trader comment. If no key, or the call fails, callers fall back
to the rule-based text — so this is always optional. Responses are cached to respect the
free-tier rate limit.
"""

from __future__ import annotations

import hashlib

from backend import config
from backend.cache import cache_json


def available() -> bool:
    return config.has_gemini()


def _call(prompt: str, system: str | None = None) -> str | None:
    if not available():
        return None
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        kwargs: dict = {
            "temperature": 0.4,
            "max_output_tokens": 600,
            # disable "thinking" so the token budget goes to the actual answer (flash is a
            # reasoning model; otherwise hidden thoughts eat the budget and truncate the reply)
            "thinking_config": types.ThinkingConfig(thinking_budget=0),
        }
        if system:
            kwargs["system_instruction"] = system
        cfg = types.GenerateContentConfig(**kwargs)
        r = client.models.generate_content(
            model=config.GEMINI_MODEL, contents=prompt, config=cfg
        )
        text = (r.text or "").strip()
        return text or None
    except Exception:  # noqa: BLE001 - LLM is best-effort; caller falls back
        return None


def comment(
    prompt: str, system: str | None, cache_key: str, ttl: int = 3600
) -> str | None:
    """Cached LLM call. cache_key should fold in the inputs so stale text isn't reused."""
    if not available():
        return None
    digest = hashlib.sha1((cache_key + (system or "")).encode("utf-8")).hexdigest()[:16]
    out = cache_json(f"llm:{digest}", ttl, lambda: {"t": _call(prompt, system)})
    return out.get("t") if isinstance(out, dict) else None
