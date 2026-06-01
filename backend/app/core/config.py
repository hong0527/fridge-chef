"""환경설정 (NFR-SEC-001 — API 키 환경변수 격리)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_timeout_s: float = float(os.getenv("GEMINI_TIMEOUT_S", "8.0"))
    recommend_timeout_s: float = float(os.getenv("RECOMMEND_TIMEOUT_S", "10.0"))
    top_k_model_a: int = int(os.getenv("TOP_K_MODEL_A", "10"))
    top_k_model_b_pre: int = int(os.getenv("TOP_K_MODEL_B_PRE", "10"))
    top_k_model_b_final: int = int(os.getenv("TOP_K_MODEL_B_FINAL", "3"))
    missing_ingredients_max: int = int(os.getenv("MISSING_INGREDIENTS_MAX", "5"))
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    mailpit_host: str = os.getenv("MAILPIT_HOST", "localhost")
    mailpit_port: int = int(os.getenv("MAILPIT_PORT", "1025"))


settings = Settings()
