"""재료 자동완성 검색 API 통합 테스트 — FR-FRIDGE-03.

엔드포인트: GET /api/ingredients/search?q=<prefix>&limit=<n>

NFR 적용 범위:
- NFR-USE-001: 신규 회원이 교육 없이 3분 이내 재료 등록 + 추천 수행 가능.
              자동완성이 오류 없이 동작해야 원활한 입력 UX 보장.
- NFR-EXT-001: 수집 개인정보는 이메일·알레르기로 한정.
              이 엔드포인트는 인증 불필요, 재료 prefix 문자열만 처리하여 개인정보 미관여.

참고: app/api/ingredients.py 모듈 주석의 "NFR-PERF-001: 자동완성 < 50ms"는
      SRS NFR-PERF-001(레시피 목록 LCP ≤ 2s)과 ID가 불일치한다.
      본 테스트 파일은 스펙 기준 NFR ID만 사용한다 (프로덕션 코드는 별도 수정 필요).

동작 원리:
- _ALL_INGREDIENTS = SYNONYM_MAP.keys() ∪ SYNONYM_MAP.values()
- prefix 매칭 후 정규형(canonical) 우선 정렬
- normalize() 기반 dedup: 동의어("달걀", "메추리알") → 정규형("계란") 하나만 출력
- q가 빈 문자열이거나 파라미터 미전달 시 [] 반환 (오류 없음)

테스트 케이스:
- IG-001: q=닭 → 닭 관련 정규형("닭고기") 포함 리스트
- IG-002: q=계란 → "계란" 포함 리스트
          (태스크 기술 예시의 q=김치는 SYNONYM_MAP에 없어 [] 반환; 실존 재료로 조정)
- IG-003: q= (빈 문자열) → 200 + []  # NFR-USE-001
- IG-004: q=존재하지않는재료xyz → 200 + []  # NFR-USE-001
- IG-005: q 파라미터 미전달 → 200 + []  # NFR-USE-001
"""

from __future__ import annotations


class TestIngredientsSearch:
    """GET /api/ingredients/search — FR-FRIDGE-03 자동완성 prefix 매칭."""

    # ──────────────────────────────────────────────────────────
    # IG-001 ~ IG-005: 필수 테스트 케이스
    # ──────────────────────────────────────────────────────────

    async def test_IG_001_search_닭_returns_닭고기(self, async_client) -> None:
        """# IG-001 — q='닭' → 200 + 닭 관련 정규형 포함.

        닭가슴살·닭다리·닭날개 등 동의어가 모두 "닭고기"로 정규화되므로
        dedup 결과는 ["닭고기"] 하나만 반환된다.
        """
        resp = await async_client.get("/api/ingredients/search", params={"q": "닭"})
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) > 0
        assert "닭고기" in body

    async def test_IG_002_search_계란_returns_계란(self, async_client) -> None:
        """# IG-002 — q='계란' → 200 + '계란' 포함된 리스트.

        '계란'은 SYNONYM_MAP 정규형 값이므로 prefix 매칭 후 그대로 반환된다.
        달걀·메추리알 등 동의어도 "계란"으로 dedup된다.
        """
        resp = await async_client.get("/api/ingredients/search", params={"q": "계란"})
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert "계란" in body

    async def test_IG_003_empty_query_returns_empty_list(self, async_client) -> None:
        """# IG-003 — q='' (빈 문자열) → 200 + [] (422가 아닌 빈 리스트).

        # NFR-USE-001 — 프론트엔드 입력창이 비어 있을 때 오류 없이 빈 목록을 받아야
        3분 내 재료 등록 UX가 끊기지 않는다.
        """
        resp = await async_client.get("/api/ingredients/search", params={"q": ""})
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_IG_004_unknown_ingredient_returns_empty_list(self, async_client) -> None:
        """# IG-004 — q='존재하지않는재료xyz' → 200 + [].

        # NFR-USE-001 — 매칭 결과가 없어도 오류 없이 빈 리스트를 반환해야
        사용자 입력 흐름이 중단되지 않는다.
        """
        resp = await async_client.get(
            "/api/ingredients/search", params={"q": "존재하지않는재료xyz"}
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_IG_005_no_q_param_returns_empty_list(self, async_client) -> None:
        """# IG-005 — q 파라미터 미전달 → 200 + [] (Query default='').

        # NFR-USE-001 — q를 전달하지 않아도 422가 아닌 200 + []를 반환해야
        프론트엔드가 파라미터 없이 초기 로드할 때도 안전하게 처리된다.
        """
        resp = await async_client.get("/api/ingredients/search")
        assert resp.status_code == 200
        assert resp.json() == []

    # ──────────────────────────────────────────────────────────
    # 추가 케이스 — 커버리지 80% 달성 및 핵심 동작 검증
    # ──────────────────────────────────────────────────────────

    async def test_synonym_resolves_to_canonical(self, async_client) -> None:
        """동의어('달걀') 검색 시 정규형('계란')이 반환된다.

        # NFR-USE-001 — 사용자가 동의어를 타이핑해도 정규형을 제안받으므로
        재료 등록이 3분 내에 자연스럽게 완료된다.
        SYNONYM_MAP: 달걀 → 계란. prefix='달걀'은 동의어 키에 매칭,
        dedup 후 normalize('달걀')='계란'만 출력.
        """
        resp = await async_client.get("/api/ingredients/search", params={"q": "달걀"})
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert "계란" in body
        assert "달걀" not in body, "동의어가 아닌 정규형만 반환되어야 한다"

    async def test_limit_parameter_caps_results(self, async_client) -> None:
        """limit 파라미터가 반환 개수를 제한한다."""
        resp = await async_client.get(
            "/api/ingredients/search", params={"q": "마", "limit": "1"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) <= 1

    async def test_response_is_list_of_strings(self, async_client) -> None:
        """응답 타입이 list[str]임을 확인한다 (response_model=list[str])."""
        resp = await async_client.get("/api/ingredients/search", params={"q": "마늘"})
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        for item in body:
            assert isinstance(item, str)

    async def test_canonical_result_deduplicated(self, async_client) -> None:
        """같은 정규형으로 수렴하는 동의어가 중복 없이 한 번만 반환된다."""
        resp = await async_client.get("/api/ingredients/search", params={"q": "닭"})
        assert resp.status_code == 200
        body = resp.json()
        # 중복 없음
        assert len(body) == len(set(body))

    async def test_whitespace_only_query_returns_empty_list(self, async_client) -> None:
        """공백만 포함한 q는 strip 후 빈 문자열이 되어 [] 반환."""
        resp = await async_client.get("/api/ingredients/search", params={"q": "   "})
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_long_query_within_max_length_ok(self, async_client) -> None:
        """max_length=50 이내 긴 쿼리는 정상 처리된다."""
        q = "가" * 50
        resp = await async_client.get("/api/ingredients/search", params={"q": q})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_query_exceeding_max_length_returns_422(self, async_client) -> None:
        """max_length=50 초과 쿼리는 FastAPI 유효성 검사 오류(422).

        # NFR-EXT-001 — 과도한 문자열 입력을 서버 레벨에서 차단하여
        수집 데이터 범위를 재료 prefix로 한정한다.
        """
        q = "가" * 51
        resp = await async_client.get("/api/ingredients/search", params={"q": q})
        assert resp.status_code == 422
