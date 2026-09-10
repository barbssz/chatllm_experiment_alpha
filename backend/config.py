from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL_DEFAULT = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

SQLITE_PATH = Path(os.getenv("SQLITE_PATH", str(ROOT_DIR / "database" / "chat.db")))
SQLALCHEMY_DATABASE_URL = f"sqlite:///{SQLITE_PATH}"

AUTH_COOKIE_NAME = "chatllm_session"
AUTH_SESSION_SECONDS = int(os.getenv("AUTH_SESSION_SECONDS", "86400"))
if AUTH_SESSION_SECONDS <= 0:
    raise ValueError("AUTH_SESSION_SECONDS deve ser positivo.")
AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"
ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "ALLOWED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000"
    ).split(",")
    if origin.strip()
]
if not ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS:
    raise ValueError("ALLOWED_ORIGINS deve conter origens explicitas, sem wildcard.")
