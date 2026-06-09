"""환경설정 (NFR-SEC-001 — API 키 환경변수 격리)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    # CRITICAL: gemini_timeout_s < recommend_timeout_s 여야 한다.
    # recommend_dual 이 model_a/b 를 recommend_timeout_s 로 감싸는데, 그 내부 Gemini 호출이
    # 더 오래 걸리면 model 전체가 잘려 '빈 추천'이 된다(작동키 사용 시 Gemini가 실제로 느려 재현).
    # 따라서 Gemini(8s)가 먼저 만료→결정론 reason 폴백→추천은 정상 반환(12s 안)되도록 둔다.
    gemini_timeout_s: float = float(os.getenv("GEMINI_TIMEOUT_S", "8.0"))
    recommend_timeout_s: float = float(os.getenv("RECOMMEND_TIMEOUT_S", "12.0"))
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
    nl_weight: float = float(os.getenv("NL_WEIGHT", "0.30"))
    # 자연어 의도파싱 — Gemini가 자유 자연어("오늘 짜증나")를 음식 묘사("맵고 얼큰한 볶음")로
    # 번역해 추천 검색어를 풍부화. 운영 추천 경로(recommend_service)에 통합. 실패/레이트리밋 시 원문 폴백.
    nl_intent_enabled: bool = os.getenv("NL_INTENT_ENABLED", "true").lower() == "true"
    # 자연어 의미검색 후보 생성(retrieval) 주입 개수. 0 이면 비활성(기존 재정렬 전용 동작 유지).
    # >0 이면 user_context 의미 유사 상위 K개를, 재료 overlap·theme 필터를 우회해 후보풀에 합류
    # (알레르기·국가·조리시간·맵기·난이도 안전/선호 필터는 유지). 의미 추천을 "재정렬→검색"으로 격상.
    nl_retrieval_k: int = int(os.getenv("NL_RETRIEVAL_K", "12"))
    # NL 주입 후보의 makeable 하한 — 재료가 이만큼도 안 겹치면 '냉털'에 부적합이라 제외.
    # 0.0 이면 게이트 없음. LLM-judge 실측상 retrieval 켜면 적절성 2.75→4.50 (Δ+1.75) 개선되나,
    # 감사 지적대로 무제한 주입은 missing 과다 후보를 냉털에 섞으므로 약한 하한으로 계약 보존.
    nl_retrieval_overlap_floor: float = float(os.getenv("NL_RETRIEVAL_OVERLAP_FLOOR", "0.3"))
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    smtp_host: str = os.getenv("SMTP_HOST", "localhost")
    smtp_port: int = int(os.getenv("SMTP_PORT", "1025"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")


settings = Settings()
