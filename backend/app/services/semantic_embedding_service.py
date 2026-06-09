"""의미 기반 문장 임베딩 추천 — multilingual-e5-small.

TF-IDF(단어 빈도 매칭)와 본질적으로 다르다. TF-IDF 는 "장마철" 과 "비 오는 날" 을
서로 다른 토큰으로 보아 매칭하지 못하지만, 문장 임베딩은 두 표현을 의미상 가까운
벡터로 사상(寫像)해 **패러프레이즈(다양한 말투)** 를 매칭한다.

설계:
  1. 오프라인(scripts/precompute_embeddings.py): 1667 레시피 description 을 인코딩 →
     data/recipe_embeddings.npz 캐시 (recipe_ids + 정규화 임베딩 행렬).
  2. 시동(lazy): 캐시 로드 + e5 모델 1회 로드.
  3. 요청: 쿼리 인코딩 → 캐시와 코사인 → {recipe_id: score} dict 반환.

e5 규약(intfloat 공식 권장):
  - 문서(레시피) 는 "passage: " 접두사로 인코딩 (precompute 단계).
  - 쿼리(사용자 입력) 는 "query: " 접두사로 인코딩.
  - normalize_embeddings=True → 임베딩이 단위벡터이므로 코사인 = 내적.

NFR-OPS-001(운영 512MB): 모델(~110MB int8 / ~470MB fp32)이 무거우므로 운영 기본
백엔드는 TF-IDF 유지(config.embedding_backend="tfidf"). 본 모듈은 평가·시연 환경에서
EMBEDDING_BACKEND=semantic 일 때 활성화된다. 모델/캐시 부재 시 빈 dict → 안전 폴백.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import settings

_logger = logging.getLogger(__name__)

# 모듈 전역 — 시동 시 1회 로드. 운영 단일 인스턴스.
_MODEL = None  # sentence_transformers.SentenceTransformer
_MATRIX = None  # np.ndarray [N, dim] — 정규화된 문서 임베딩
_RECIPE_IDS: list[str] = []

# 캐시 경로: backend/data/recipe_embeddings.npz
_CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "recipe_embeddings.npz"


def cache_path() -> Path:
    return _CACHE_PATH


def _get_model():
    """e5 모델 lazy 로드 — 최초 호출 시 1회. import/다운로드 실패 시 None."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        _logger.warning("sentence-transformers 미설치 → 의미 임베딩 비활성화 (TF-IDF 폴백)")
        return None
    try:
        _MODEL = SentenceTransformer(settings.embedding_model)
        _logger.info("의미 임베딩 모델 로드: %s", settings.embedding_model)
    except Exception as e:  # noqa: BLE001 — 네트워크/디스크 실패 시 안전 폴백.
        _logger.warning("의미 임베딩 모델 로드 실패 (%s) → TF-IDF 폴백", e)
        _MODEL = None
    return _MODEL


def load_cache() -> bool:
    """사전계산 임베딩 캐시(.npz) 로드. 성공 True. 부재/실패 시 False → 폴백."""
    global _MATRIX, _RECIPE_IDS
    if not _CACHE_PATH.exists():
        _logger.warning("의미 임베딩 캐시 없음: %s — precompute_embeddings.py 먼저 실행", _CACHE_PATH)
        return False
    try:
        import numpy as np

        data = np.load(_CACHE_PATH, allow_pickle=True)
        _MATRIX = data["embeddings"].astype("float32")
        _RECIPE_IDS = [str(x) for x in data["recipe_ids"].tolist()]
        _logger.info(
            "의미 임베딩 캐시 로드: %d docs, dim=%d",
            len(_RECIPE_IDS), _MATRIX.shape[1] if _MATRIX is not None else 0,
        )
        return True
    except Exception as e:  # noqa: BLE001
        _logger.warning("의미 임베딩 캐시 로드 실패: %s", e)
        _MATRIX = None
        _RECIPE_IDS = []
        return False


def ensure_ready() -> bool:
    """시동 훅 — 캐시 + 모델 준비. 둘 중 하나라도 실패하면 False (TF-IDF 폴백)."""
    ok = load_cache()
    if not ok:
        return False
    return _get_model() is not None


def score_query(query_text: str) -> dict[str, float]:
    """사용자 쿼리 → {recipe_id: 코사인 유사도} dict.

    모델/캐시 미준비 또는 빈 쿼리 시 빈 dict → 가중합에 0 기여(안전 폴백, TF-IDF 와 동일 계약).
    정규화 임베딩이므로 코사인 = 내적. 값 범위 대략 [-1, 1] (e5 는 보통 0.7~0.95 양수대).
    """
    if _MATRIX is None or not query_text or not query_text.strip():
        return {}
    model = _get_model()
    if model is None:
        return {}
    try:
        import numpy as np

        q = model.encode(
            [f"query: {query_text}"],
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).astype("float32")
        sims = (q @ _MATRIX.T).flatten()
        sims = np.nan_to_num(sims, nan=0.0, posinf=0.0, neginf=0.0)
        return {rid: float(s) for rid, s in zip(_RECIPE_IDS, sims, strict=False)}
    except Exception as e:  # noqa: BLE001
        _logger.warning("의미 임베딩 score_query 실패: %s — 빈 dict 폴백", e)
        return {}


def is_ready() -> bool:
    return _MATRIX is not None and _MODEL is not None


def stats() -> dict:
    if _MATRIX is None:
        return {"ready": False, "backend": "semantic"}
    return {
        "ready": is_ready(),
        "backend": "semantic",
        "model": settings.embedding_model,
        "n_docs": len(_RECIPE_IDS),
        "dim": int(_MATRIX.shape[1]) if _MATRIX is not None else 0,
    }


def _reset_for_tests() -> None:
    """테스트 격리용 — 모델은 유지(재로드 비용↑), 행렬만 초기화."""
    global _MATRIX, _RECIPE_IDS
    _MATRIX = None
    _RECIPE_IDS = []
