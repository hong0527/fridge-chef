"""TF-IDF 임베딩 추천 — 학부 SW공학론 'AI 기반 추천 시스템' 요구 충족.

설계:
  1. 시동 시 1667 레시피 텍스트 → TfidfVectorizer.fit_transform() → sparse matrix 캐시
  2. 요청 시 사용자 입력(보유 재료 + user_context) → transform() → 코사인 유사도
  3. score_query() 가 recipe_id → 유사도 score dict 반환

학계 근거:
  - Salton & McGill 1983 "Information Retrieval" TF-IDF 표준
  - Aggarwal 2016 §4.5 Set Similarity (content-based)
  - 본 프로젝트 Wu et al. 2023 LLM-as-Reranker 와 결합 (Gemini 큐레이션은 별도)

NFR-PERF-003: 응답 시간 영향 < 10ms (sparse cosine 매우 빠름).
NFR-OPS-001: Render Free 512MB 호환 (TF-IDF 모델 ~5MB).
"""

from __future__ import annotations

import logging

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models.recipe import Recipe

_logger = logging.getLogger(__name__)

# 모듈 전역 — 시동 시 fit_corpus() 호출로 초기화. 운영 단일 인스턴스.
_VECTORIZER: TfidfVectorizer | None = None
_MATRIX = None  # scipy.sparse.csr_matrix — 1667 × vocab
_RECIPE_IDS: list[str] = []


def _recipe_text(r: Recipe) -> str:
    """레시피 → TF-IDF 입력 텍스트.

    레시피 이름 + 주재료 토큰을 공백으로 합쳐 단어 단위 벡터화에 적합.
    BASIC_SEASONINGS(소금·간장 등) 도 포함해 풍부한 도메인 어휘 활용.
    """
    return f"{r.name} {' '.join(r.whole_ingredients)}"


def fit_corpus(recipes: list[Recipe]) -> None:
    """시동 시 1회 호출 — 전체 코퍼스로 TF-IDF 학습 + sparse matrix 캐시.

    한국어 토큰 패턴: 한글·영문·숫자 단어 단위.
    max_features=2000 — vocab 크기 제한으로 메모리·계산 안정.
    sublinear_tf=True — 빈도 polynomial 완화 (long-tail 어휘 보존).
    """
    global _VECTORIZER, _MATRIX, _RECIPE_IDS
    if not recipes:
        _logger.warning("fit_corpus: 빈 recipes — 임베딩 비활성화")
        return
    texts = [_recipe_text(r) for r in recipes]
    _VECTORIZER = TfidfVectorizer(
        analyzer="word",
        token_pattern=r"[가-힣A-Za-z0-9]+",
        max_features=2000,
        sublinear_tf=True,
    )
    _MATRIX = _VECTORIZER.fit_transform(texts)
    _RECIPE_IDS = [r.recipe_id for r in recipes]
    _logger.info(
        "TF-IDF fit complete: %d docs, vocab=%d", len(recipes), len(_VECTORIZER.vocabulary_)
    )


def score_query(query_text: str) -> dict[str, float]:
    """사용자 쿼리 텍스트 → recipe_id : 코사인 유사도 점수 dict.

    빈 vectorizer(시동 실패) 또는 빈 쿼리 시 빈 dict 반환 → 가중합에 0 기여 (안전 폴백).
    """
    if _VECTORIZER is None or _MATRIX is None or not query_text.strip():
        return {}
    q = _VECTORIZER.transform([query_text])
    sims = cosine_similarity(q, _MATRIX).flatten()
    # numpy float → Python float (JSON 직렬화·SQL 호환)
    return {rid: float(s) for rid, s in zip(_RECIPE_IDS, sims, strict=False)}


def is_ready() -> bool:
    """헬스체크용 — 임베딩 모델 로드 여부."""
    return _VECTORIZER is not None and _MATRIX is not None


def stats() -> dict:
    """디버그용 통계."""
    if not is_ready():
        return {"ready": False}
    return {
        "ready": True,
        "n_docs": len(_RECIPE_IDS),
        "vocab_size": len(_VECTORIZER.vocabulary_) if _VECTORIZER else 0,
        "matrix_shape": list(_MATRIX.shape) if _MATRIX is not None else None,
    }


def _reset_for_tests() -> None:
    """테스트 격리용 — 전역 상태 초기화."""
    global _VECTORIZER, _MATRIX, _RECIPE_IDS
    _VECTORIZER = None
    _MATRIX = None
    _RECIPE_IDS = []
