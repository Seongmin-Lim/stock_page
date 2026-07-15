"""App config / secrets loader. Reads .env (git-ignored) once at import.

Keys are optional — the app works key-free; a present DART_API_KEY simply unlocks
Korean detailed financial statements (DART) on top of the key-free sources.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:  # noqa: BLE001 - dotenv optional; env vars may be set externally
    pass

DART_API_KEY: str | None = os.environ.get("DART_API_KEY") or None

# 키움증권 REST OpenAPI credentials (optional)
KIWOOM_APP_KEY: str | None = os.environ.get("KIWOOM_APP_KEY") or None
KIWOOM_APP_SECRET: str | None = os.environ.get("KIWOOM_APP_SECRET") or None
KIWOOM_ACCOUNT: str | None = os.environ.get("KIWOOM_ACCOUNT") or None
KIWOOM_MOCK: bool = os.environ.get("KIWOOM_MOCK", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)

# Google Gemini (optional LLM narrative layer)
GEMINI_API_KEY: str | None = os.environ.get("GEMINI_API_KEY") or None
GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def has_dart() -> bool:
    return bool(DART_API_KEY)


def has_kiwoom() -> bool:
    return bool(KIWOOM_APP_KEY and KIWOOM_APP_SECRET)


def has_gemini() -> bool:
    return bool(GEMINI_API_KEY)
