"""환경설정 (NFR-SEC-001 — API 키 환경변수 격리)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    # Gemini 2.5 Flash 가 한국어 reason 3개 생성에 평균 5~12초 소요 — 8초 timeout 시연 중
    # 빈번히 폴백(reason 빈 문자열) 발생. 20초로 상향해 안정성 확보.
    gemini_timeout_s: float = float(os.getenv("GEMINI_TIMEOUT_S", "20.0"))
    recommend_timeout_s: float = float(os.getenv("RECOMMEND_TIMEOUT_S", "10.0"))
    top_k_model_a: int = int(os.getenv("TOP_K_MODEL_A", "10"))
    top_k_model_b_pre: int = int(os.getenv("TOP_K_MODEL_B_PRE", "10"))
    top_k_model_b_final: int = int(os.getenv("TOP_K_MODEL_B_FINAL", "3"))
    missing_ingredients_max: int = int(os.getenv("MISSING_INGREDIENTS_MAX", "5"))
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    smtp_host: str = os.getenv("SMTP_HOST", "localhost")
    smtp_port: int = int(os.getenv("SMTP_PORT", "1025"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")


settings = Settings()
