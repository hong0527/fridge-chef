"""embedding_service — TF-IDF + Cosine 임베딩 단위 테스트 (Issue #72).

검증 항목:
  1. fit_corpus 후 score_query 가 recipe_id : float dict 반환
  2. 빈 코퍼스 → 안전 폴백 (빈 dict, 예외 없음)
  3. 빈 query_text → 빈 dict (안전 폴백)
  4. 동일 query 결정론 (같은 입력 → 같은 결과)
  5. 의미 매칭: query 와 어휘 일치 레시피가 비일치 레시피보다 높은 점수
  6. is_ready / stats 헬스체크 정합
  7. _reset_for_tests — 격리 안전

학계 근거:
  - Salton & McGill 1983 TF-IDF
  - sklearn TfidfVectorizer 결정론 (동일 입력 → 동일 출력)
"""

from __future__ import annotations

import pytest

from app.models.recipe import Recipe
from app.services import embedding_service as es


@pytest.fixture(autouse=True)
def _reset_state():
    """각 테스트 전/후 전역 상태 초기화 — 테스트 격리."""
    es._reset_for_tests()
    yield
    es._reset_for_tests()


def _sample_recipes() -> list[Recipe]:
    """결정론적 미니 코퍼스 — 5개 레시피, 토큰 명확히 분리."""
    return [
        Recipe("r001", "간장계란밥", ["밥", "계란", "간장"]),
        Recipe("r002", "두부조림", ["두부", "간장", "마늘"]),
        Recipe("r003", "닭가슴살구이", ["닭가슴살", "올리브유"]),
        Recipe("r004", "파스타", ["면", "치즈", "마늘"]),
        Recipe("r005", "야채볶음", ["양파", "버섯", "당근"]),
    ]


def test_fit_corpus_basic() -> None:
    """fit_corpus 후 is_ready True + stats 정합."""
    assert es.is_ready() is False
    es.fit_corpus(_sample_recipes())
    assert es.is_ready() is True
    s = es.stats()
    assert s["ready"] is True
    assert s["n_docs"] == 5
    assert s["vocab_size"] > 0
    assert s["matrix_shape"] == [5, s["vocab_size"]]


def test_score_query_returns_dict_of_floats() -> None:
    """score_query 가 모든 recipe_id 에 대해 float 점수 dict 반환."""
    es.fit_corpus(_sample_recipes())
    scores = es.score_query("간장 계란")
    assert isinstance(scores, dict)
    assert len(scores) == 5
    assert set(scores.keys()) == {"r001", "r002", "r003", "r004", "r005"}
    for v in scores.values():
        assert isinstance(v, float)
        assert 0.0 <= v <= 1.0


def test_score_query_semantic_match() -> None:
    """의미 매칭 검증: 쿼리 어휘를 포함한 레시피가 더 높은 점수."""
    es.fit_corpus(_sample_recipes())
    scores = es.score_query("계란 밥")
    # '간장계란밥(r001)' 이 '야채볶음(r005)' 보다 점수 높아야 함 (어휘 일치)
    assert scores["r001"] > scores["r005"]
    # '간장계란밥(r001)' 이 '파스타(r004)' 보다 점수 높아야 함
    assert scores["r001"] > scores["r004"]


def test_empty_corpus_safe() -> None:
    """빈 코퍼스 fit_corpus — 예외 없이 비활성화 상태 유지."""
    es.fit_corpus([])
    assert es.is_ready() is False
    # 비활성화 상태에서 score_query 호출해도 빈 dict 반환 (폴백)
    assert es.score_query("간장 계란") == {}


def test_empty_query_returns_empty_dict() -> None:
    """빈 query_text — 빈 dict (가중합에 0 기여 안전 폴백)."""
    es.fit_corpus(_sample_recipes())
    assert es.score_query("") == {}
    assert es.score_query("   ") == {}


def test_deterministic_same_input_same_output() -> None:
    """동일 query → 동일 결과 (sklearn 결정론)."""
    es.fit_corpus(_sample_recipes())
    s1 = es.score_query("두부 간장")
    s2 = es.score_query("두부 간장")
    assert s1 == s2


def test_reset_for_tests_clears_state() -> None:
    """_reset_for_tests 후 다시 비활성화 상태."""
    es.fit_corpus(_sample_recipes())
    assert es.is_ready() is True
    es._reset_for_tests()
    assert es.is_ready() is False
    assert es.stats() == {"ready": False}


def test_score_query_before_fit_returns_empty() -> None:
    """fit_corpus 호출 전 score_query — 빈 dict (안전 폴백)."""
    assert es.score_query("간장 계란") == {}
