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
    # ── 자연어 추천 임베딩 백엔드 (Issue #72 후속 — 의미 임베딩 도입) ──
    # "tfidf"    : sklearn TF-IDF 단어빈도 매칭 (경량, 운영 기본 — 512MB 안전).
    # "semantic" : multilingual-e5-small 문장 임베딩 (의미/패러프레이즈 매칭, 평가·시연용).
    # 운영은 메모리 안전을 위해 tfidf 기본, 로컬 평가/시연은 EMBEDDING_BACKEND=semantic.
    embedding_backend: str = os.getenv("EMBEDDING_BACKEND", "tfidf")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    # 자연어(user_context) TF-IDF/임베딩 점수의 최종 가중치. 나머지 (1 - nl_weight)는 선호 가중합.
    # 0.20 → 0.35 상향 검토 중 (자연어 신호가 실제 재랭킹에 반영되도록, ablation 으로 검증).
    nl_weight: float = float(os.getenv("NL_WEIGHT", "0.20"))
    # 자연어 의미검색 후보 생성(retrieval) 주입 개수. 0 이면 비활성(기존 재정렬 전용 동작 유지).
    # >0 이면 user_context 의미 유사 상위 K개를, 재료 overlap·theme 필터를 우회해 후보풀에 합류
    # (알레르기·국가·조리시간·맵기·난이도 안전/선호 필터는 유지). 의미 추천을 "재정렬→검색"으로 격상.
    nl_retrieval_k: int = int(os.getenv("NL_RETRIEVAL_K", "0"))
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    smtp_host: str = os.getenv("SMTP_HOST", "localhost")
    smtp_port: int = int(os.getenv("SMTP_PORT", "1025"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")


settings = Settings()
