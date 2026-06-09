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

import json
import logging
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models.recipe import Recipe

_logger = logging.getLogger(__name__)

# 모듈 전역 — 시동 시 fit_corpus() 호출로 초기화. 운영 단일 인스턴스.
_VECTORIZER: TfidfVectorizer | None = None
_MATRIX = None  # scipy.sparse.csr_matrix — 1667 × vocab
_RECIPE_IDS: list[str] = []
# recipe_id → 자연어 description (LLM-Augmented Content Vectorization, Wang 2023).
# 시동 시 1회 로드. 누락 시 빈 dict — _recipe_text 가 graceful fallback.
_DESCRIPTIONS: dict[str, str] = {}

# 백엔드 런타임 오버라이드 (평가 ablation 용). None 이면 settings.embedding_backend 사용.
# evaluate_semantic_nl.py 가 set_backend("tfidf"|"semantic") 으로 동일 프로세스 내 전환.
_BACKEND_OVERRIDE: str | None = None


def set_backend(name: str | None) -> None:
    """평가용 — 자연어 점수 백엔드를 런타임 강제. None 이면 설정값으로 복원."""
    global _BACKEND_OVERRIDE
    _BACKEND_OVERRIDE = name


def _active_backend() -> str:
    from app.core.config import settings
    return _BACKEND_OVERRIDE or settings.embedding_backend


def _load_descriptions() -> dict[str, str]:
    """recipe_descriptions.json (1667 항목) 로드.

    파일 부재·파싱 실패 시 빈 dict 반환 → vocab 풍부화만 비활성, TF-IDF 기본 동작 유지.
    """
    path = Path(__file__).resolve().parents[2] / "data" / "recipe_descriptions.json"
    if not path.exists():
        _logger.warning("recipe_descriptions.json missing — vocab 풍부화 비활성화")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        _logger.info("loaded %d descriptions from %s", len(data), path.name)
        return data
    except (OSError, json.JSONDecodeError) as e:
        _logger.warning("descriptions load failed: %s", e)
        return {}


def _recipe_text(r: Recipe) -> str:
    """레시피 → TF-IDF 입력 텍스트.

    레시피 이름 + 주재료 + 자연어 description 을 공백으로 합쳐 단어 단위 벡터화.
    description 은 LLM-Augmented Content Vectorization (Wang 2023) 으로 자연어 도메인
    어휘(계절·상황·맛·대상)를 흡수해 사용자 자연어 쿼리 매칭률을 높인다.
    description 누락 시 기존 name+ingredients 만 사용 (graceful fallback).
    """
    desc = _DESCRIPTIONS.get(r.recipe_id, "")
    return f"{r.name} {' '.join(r.whole_ingredients)} {desc}".strip()


def fit_corpus(recipes: list[Recipe]) -> None:
    """시동 시 1회 호출 — 전체 코퍼스로 TF-IDF 학습 + sparse matrix 캐시.

    한국어 토큰 패턴: 한글·영문·숫자 단어 단위.
    max_features=5000 — description 통합 후 vocab 도메인 어휘 증가 흡수
    (이전 2000 → name+ingredients 만 학습, 현 5000 → +description 자연어 어휘).
    sublinear_tf=True — 빈도 polynomial 완화 (long-tail 어휘 보존).
    """
    global _VECTORIZER, _MATRIX, _RECIPE_IDS, _DESCRIPTIONS
    if not recipes:
        _logger.warning("fit_corpus: 빈 recipes — 임베딩 비활성화")
        return
    # description 사전 로드 — _recipe_text 에서 참조.
    _DESCRIPTIONS = _load_descriptions()
    texts = [_recipe_text(r) for r in recipes]
    _VECTORIZER = TfidfVectorizer(
        analyzer="word",
        token_pattern=r"[가-힣A-Za-z0-9]+",
        max_features=5000,
        sublinear_tf=True,
    )
    _MATRIX = _VECTORIZER.fit_transform(texts)
    _RECIPE_IDS = [r.recipe_id for r in recipes]
    _logger.info(
        "TF-IDF fit complete: %d docs, vocab=%d, descriptions=%d",
        len(recipes), len(_VECTORIZER.vocabulary_), len(_DESCRIPTIONS),
    )
    # 의미 임베딩 백엔드 설정 시 사전계산 캐시 + 모델 준비 (실패해도 TF-IDF 폴백 유지).
    if _active_backend() in ("semantic", "hybrid"):
        from app.services import semantic_embedding_service as sem
        if sem.ensure_ready():
            _logger.info("의미 임베딩 백엔드 활성(%s): %s", _active_backend(), sem.stats())
        else:
            _logger.warning("의미 임베딩 준비 실패 → TF-IDF 폴백 유지")


def score_query(query_text: str, nl_text: str = "") -> dict[str, float]:
    """사용자 쿼리 텍스트 → recipe_id : 코사인 유사도 점수 dict.

    빈 vectorizer(시동 실패) 또는 빈 쿼리 시 빈 dict 반환 → 가중합에 0 기여 (안전 폴백).
    NaN 방어: 0-norm sparse row(데이터 결손 레시피) 발생 시 sklearn cosine 이 NaN 반환 →
    정렬 시 후순위 결정 불가 (code-reviewer CRITICAL-2). nan_to_num 으로 0.0 강제.
    """
    # 의미 임베딩은 '자연어 의도' 매칭이 목적이므로, 냉장고 재료 토큰이 섞인 query_text 대신
    # 순수 자연어 nl_text 를 우선 인코딩한다 (재료 매칭은 overlap·가중합이 이미 담당).
    backend = _active_backend()
    if backend == "semantic":
        from app.services import semantic_embedding_service as sem
        if sem.is_ready():
            return sem.score_query(nl_text.strip() or query_text)
        return _tfidf_score_query(query_text)  # 의미 미준비 → TF-IDF 폴백
    if backend == "hybrid":
        # 단어매칭(TF-IDF)과 의미매칭(e5)의 상호보완 — 쿼리에 음식 단어가 있으면 TF-IDF가,
        # 어휘 겹침 없는 패러프레이즈는 e5가 잡는다. 각자 코퍼스 min-max 정규화 후 per-recipe max.
        from app.services import semantic_embedding_service as sem
        tf = _tfidf_score_query(query_text)
        sm = sem.score_query(nl_text.strip() or query_text) if sem.is_ready() else {}
        return _combine_scores(tf, sm)
    return _tfidf_score_query(query_text)


def _tfidf_score_query(query_text: str) -> dict[str, float]:
    """순수 TF-IDF 코사인 — 단어 빈도 매칭. 빈 vectorizer/쿼리 시 빈 dict."""
    if _VECTORIZER is None or _MATRIX is None or not query_text.strip():
        return {}
    import numpy as np
    q = _VECTORIZER.transform([query_text])
    sims = cosine_similarity(q, _MATRIX).flatten()
    sims = np.nan_to_num(sims, nan=0.0, posinf=0.0, neginf=0.0)
    return {rid: float(s) for rid, s in zip(_RECIPE_IDS, sims, strict=False)}


def _combine_scores(tf: dict[str, float], sm: dict[str, float]) -> dict[str, float]:
    """TF-IDF·의미 점수 결합 — 각 코퍼스 min-max 정규화 후 per-recipe max (둘 중 강한 신호 채택)."""
    if not sm:
        return tf
    if not tf:
        return sm

    def _norm(d: dict[str, float]) -> dict[str, float]:
        vs = list(d.values())
        lo, hi = min(vs), max(vs)
        rng = hi - lo
        if rng < 1e-9:
            return {k: 0.0 for k in d}
        return {k: (v - lo) / rng for k, v in d.items()}

    tfn, smn = _norm(tf), _norm(sm)
    keys = set(tf) | set(sm)
    return {k: max(tfn.get(k, 0.0), smn.get(k, 0.0)) for k in keys}


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
