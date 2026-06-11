"""gemini_client 전용 단위 테스트 (GC-001 ~ GC-012 + 커버리지 보완).

- _parse_response_text : JSON 파싱 함수 (GC-001~006)
- _build_prompt        : 프롬프트 생성 함수 (GC-007~009)
- gemini_select_top3   : 전체 흐름 결합 테스트 (GC-010~012)
- 보완 테스트           : success path, TimeoutError, _call_gemini_sdk 직접 호출
- _call_gemini_sdk._sync_call : 503/429/500 지수 백오프 재시도 (GC-RT-001~005)

API 키·네트워크 불필요 — _call_gemini_sdk 는 monkeypatch 로 격리.
"""

from __future__ import annotations

import json

import pytest

from app.services.gemini_client import (
    _build_prompt,
    _call_gemini_sdk,
    _parse_response_text,
    gemini_reasons_for_model_a,
    gemini_select_top3,
)

# ─── 공통 후보 픽스처 ─────────────────────────────────────────

_CANDIDATES_3 = [
    {
        "recipe_id": "r001",
        "name": "김치찌개",
        "cook_min": 30,
        "have": ["김치"],
        "missing": ["돼지고기"],
        "final_score": 0.8,
    },
    {
        "recipe_id": "r002",
        "name": "된장찌개",
        "cook_min": 20,
        "have": ["된장"],
        "missing": [],
        "final_score": 0.7,
    },
    {
        "recipe_id": "r003",
        "name": "계란볶음밥",
        "cook_min": 10,
        "have": ["밥", "계란"],
        "missing": [],
        "final_score": 0.9,
    },
]


# ─────────────────────────────────────────────────────────────
class TestParseResponseText:
    """_parse_response_text — Gemini 응답 JSON 추출 (GC-001~006)."""

    def test_gc001_plain_json_returns_dict(self) -> None:
        """GC-001 — 정상 JSON 문자열 → dict 반환."""
        text = '{"selected": ["r1", "r2", "r3"], "reasons": ["a", "b", "c"]}'
        result = _parse_response_text(text)
        assert isinstance(result, dict)
        assert result["selected"] == ["r1", "r2", "r3"]

    def test_gc002_code_fence_stripped_and_returns_dict(self) -> None:
        """GC-002 — ```json...``` 코드펜스 감싸진 경우 → 펜스 제거 후 dict 반환."""
        text = '```json\n{"selected": ["r1", "r2"], "reasons": ["a", "b"]}\n```'
        result = _parse_response_text(text)
        assert isinstance(result, dict)
        assert "selected" in result
        assert result["selected"] == ["r1", "r2"]

    def test_gc003_empty_string_returns_none(self) -> None:
        """GC-003 — 빈 문자열 → None 반환."""
        assert _parse_response_text("") is None

    def test_gc004_plain_text_no_brace_returns_none(self) -> None:
        """GC-004 — 중괄호 없는 일반 텍스트 → None 반환."""
        assert _parse_response_text("레시피를 찾을 수 없습니다.") is None

    def test_gc005_invalid_json_syntax_returns_none(self) -> None:
        """GC-005 — JSON 형식 오류 (쉼표 누락) → None 반환."""
        text = '{"selected": ["r1" "r2"]}'  # 원소 사이 쉼표 없음
        assert _parse_response_text(text) is None

    def test_gc006_json_surrounded_by_text_returns_dict(self) -> None:
        """GC-006 — JSON 앞뒤 불필요한 텍스트 → dict 반환."""
        text = '여기 결과입니다: {"selected": ["r1"], "reasons": ["이유"]} 이상입니다.'
        result = _parse_response_text(text)
        assert isinstance(result, dict)
        assert result["selected"] == ["r1"]


# ─────────────────────────────────────────────────────────────
class TestBuildPrompt:
    """_build_prompt — Gemini 프롬프트 생성 (GC-007~009)."""

    def test_gc007_all_recipe_ids_present_in_prompt(self) -> None:
        """GC-007 — 후보 3개 + 사용자 메모 → 결과 문자열에 recipe_id 모두 포함."""
        prompt = _build_prompt(_CANDIDATES_3, "빠르게 먹고 싶어요")
        assert "r001" in prompt
        assert "r002" in prompt
        assert "r003" in prompt

    def test_gc008_empty_memo_uses_default_placeholder(self) -> None:
        """GC-008 — 사용자 메모 빈 문자열 → '(특이사항 없음)' 포함."""
        prompt = _build_prompt(_CANDIDATES_3[:1], "")
        assert "(특이사항 없음)" in prompt

    def test_gc009_empty_candidates_has_no_candidate_lines(self) -> None:
        """GC-009 — 후보 목록 비어있음 → candidate 줄 포맷 없음."""
        prompt = _build_prompt([], "오늘 저녁")
        # 후보 줄은 "[N] id=..." 형식 (GC-007 참고) — candidates 가 비면 생성되지 않아야 함
        assert "[1] id=" not in prompt


# ─────────────────────────────────────────────────────────────
class TestGeminiSelectTop3:
    """gemini_select_top3 — 전체 흐름 결합 테스트 (GC-010~012)."""

    @pytest.mark.asyncio
    async def test_gc010_empty_candidates_returns_none(self) -> None:
        """GC-010 — 후보 없음 → None 반환 (SDK 호출 없음)."""
        result = await gemini_select_top3([], "테스트")
        assert result is None

    @pytest.mark.asyncio
    async def test_gc011_sdk_returns_none_propagates_none(self, monkeypatch) -> None:
        """GC-011 — SDK mock None 반환 → gemini_select_top3 도 None 반환."""
        import app.services.gemini_client as gc_mod

        async def _mock_none(_: str) -> None:
            return None

        monkeypatch.setattr(gc_mod, "_call_gemini_sdk", _mock_none)

        result = await gemini_select_top3(_CANDIDATES_3[:1], "")
        assert result is None

    @pytest.mark.asyncio
    async def test_gc012_response_without_selected_key_returns_none(
        self, monkeypatch
    ) -> None:
        """GC-012 — 응답에 'selected' 키 없음 → None 반환."""
        import app.services.gemini_client as gc_mod

        async def _mock_no_selected(_: str) -> str:
            return '{"reasons": ["이유1"], "citation_ids": []}'

        monkeypatch.setattr(gc_mod, "_call_gemini_sdk", _mock_no_selected)

        result = await gemini_select_top3(_CANDIDATES_3[:1], "")
        assert result is None


# ─────────────────────────────────────────────────────────────
class TestGeminiSelectTop3Coverage:
    """80% 라인 커버리지 달성을 위한 보완 테스트 — success path / TimeoutError."""

    @pytest.mark.asyncio
    async def test_valid_response_returns_dict(self, monkeypatch) -> None:
        """정상 응답 시 selected/reasons/citation_ids 포함 dict 반환 (success path, lines 127-131)."""
        import app.services.gemini_client as gc_mod

        async def _mock_valid(_: str) -> str:
            return '{"selected": ["r001", "r002", "r003"], "reasons": ["a", "b", "c"]}'

        monkeypatch.setattr(gc_mod, "_call_gemini_sdk", _mock_valid)

        result = await gemini_select_top3(_CANDIDATES_3, "맛있게")
        assert result is not None
        assert isinstance(result["selected"], list)
        assert "reasons" in result
        assert "citation_ids" in result

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self, monkeypatch) -> None:
        """# NFR-REL-001 — 타임아웃 시 None 반환 (폴백 경로, lines 115-117)."""
        import asyncio
        from dataclasses import replace

        import app.services.gemini_client as gc_mod
        from app.core import config as cfg

        async def _mock_slow(_: str) -> str:
            await asyncio.sleep(999)
            return ""  # pragma: no cover

        monkeypatch.setattr(gc_mod, "_call_gemini_sdk", _mock_slow)
        monkeypatch.setattr(
            gc_mod, "settings", replace(cfg.settings, gemini_timeout_s=0.001)
        )

        result = await gemini_select_top3(_CANDIDATES_3[:1], "")
        assert result is None

    @pytest.mark.asyncio
    async def test_unparseable_text_returns_none(self, monkeypatch) -> None:
        """_parse_response_text 가 None 을 반환하는 경우 → None 반환 (line 123)."""
        import app.services.gemini_client as gc_mod

        async def _mock_garbage(_: str) -> str:
            return "죄송합니다, 결과를 생성할 수 없습니다."  # JSON 없음

        monkeypatch.setattr(gc_mod, "_call_gemini_sdk", _mock_garbage)

        result = await gemini_select_top3(_CANDIDATES_3[:1], "")
        assert result is None

    @pytest.mark.asyncio
    async def test_call_gemini_sdk_no_api_key_returns_none(self) -> None:
        """# NFR-SEC-002 — GEMINI_API_KEY 미설정 시 SDK 호출 없이 None 반환 (lines 77-79)."""
        result = await _call_gemini_sdk("테스트 프롬프트")
        assert result is None


# ─────────────────────────────────────────────────────────────
class TestGeminiReasonsForModelA:
    """gemini_reasons_for_model_a — Model A 자연어 이유 생성 (GC-MA-001~006)."""

    @pytest.mark.asyncio
    async def test_gc_ma_001_empty_candidates_returns_none(self) -> None:
        """GC-MA-001 — candidates=[] 빈 리스트 → None 반환 (SDK 호출 없음)."""
        result = await gemini_reasons_for_model_a([], "테스트")
        assert result is None

    @pytest.mark.asyncio
    async def test_gc_ma_002_timeout_returns_none(self, monkeypatch) -> None:
        """# NFR-REL-001 — SDK 호출이 타임아웃 초과 시 None 반환 (폴백 경로)."""
        import asyncio
        from dataclasses import replace

        import app.services.gemini_client as gc_mod
        from app.core import config as cfg

        async def _slow_sdk(_: str) -> None:
            await asyncio.sleep(999)

        monkeypatch.setattr(gc_mod, "_call_gemini_sdk", _slow_sdk)
        monkeypatch.setattr(gc_mod, "settings", replace(cfg.settings, gemini_timeout_s=0.01))

        result = await gemini_reasons_for_model_a(_CANDIDATES_3[:1], "")
        assert result is None

    @pytest.mark.asyncio
    async def test_gc_ma_003_sdk_none_returns_none(self, monkeypatch) -> None:
        """GC-MA-003 — SDK가 None 반환 → None 반환."""
        import app.services.gemini_client as gc_mod

        async def _mock_none(_: str) -> None:
            return None

        monkeypatch.setattr(gc_mod, "_call_gemini_sdk", _mock_none)

        result = await gemini_reasons_for_model_a(_CANDIDATES_3[:1], "")
        assert result is None

    @pytest.mark.asyncio
    async def test_gc_ma_004_no_reasons_key_returns_none(self, monkeypatch) -> None:
        """GC-MA-004 — SDK가 'reasons' 키 없는 JSON 반환 → None 반환."""
        import app.services.gemini_client as gc_mod

        async def _mock_no_reasons(_: str) -> str:
            return '{"selected": ["r001"]}'

        monkeypatch.setattr(gc_mod, "_call_gemini_sdk", _mock_no_reasons)

        result = await gemini_reasons_for_model_a(_CANDIDATES_3[:1], "")
        assert result is None

    @pytest.mark.asyncio
    async def test_gc_ma_005_valid_response_returns_reasons_list(self, monkeypatch) -> None:
        """GC-MA-005 — SDK가 정상 JSON 반환 → reasons 리스트 반환."""
        import app.services.gemini_client as gc_mod

        async def _mock_valid(_: str) -> str:
            return '{"reasons": ["이유 하나", "이유 둘", "이유 셋"]}'

        monkeypatch.setattr(gc_mod, "_call_gemini_sdk", _mock_valid)

        result = await gemini_reasons_for_model_a(_CANDIDATES_3, "저녁 뭐 먹지")
        assert result == ["이유 하나", "이유 둘", "이유 셋"]

    @pytest.mark.asyncio
    async def test_gc_ma_006_partial_reasons_returns_available(self, monkeypatch) -> None:
        """GC-MA-006 — reasons 수가 candidates 수와 불일치 → 가능한 만큼 반환 (partial)."""
        import app.services.gemini_client as gc_mod

        async def _mock_partial(_: str) -> str:
            return '{"reasons": ["이유 하나"]}'

        monkeypatch.setattr(gc_mod, "_call_gemini_sdk", _mock_partial)

        # candidates 3개, reasons 1개 → partial 반환
        result = await gemini_reasons_for_model_a(_CANDIDATES_3, "저녁")
        assert result == ["이유 하나"]


# ─────────────────────────────────────────────────────────────
class _FakeHTTPResponse:
    """urllib.request.urlopen() 의 `with ... as resp:` 컨텍스트 매니저 모킹."""

    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> _FakeHTTPResponse:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


_OK_PAYLOAD = {"candidates": [{"content": {"parts": [{"text": "정상 응답"}]}}]}


class TestCallGeminiSdkRetry:
    """_call_gemini_sdk._sync_call — 503/429/500 지수 백오프 재시도 (GC-RT-001~005)."""

    @pytest.fixture(autouse=True)
    def _with_api_key(self, monkeypatch):
        """gemini_api_key 설정(early-return 우회) + time.sleep no-op(백오프 지연 제거)."""
        from dataclasses import replace

        import app.services.gemini_client as gc_mod
        from app.core import config as cfg

        monkeypatch.setattr(gc_mod, "settings", replace(cfg.settings, gemini_api_key="test-key"))
        monkeypatch.setattr("time.sleep", lambda *_: None)

    @pytest.mark.asyncio
    async def test_gc_rt_001_first_attempt_success_returns_text(self, monkeypatch) -> None:
        """GC-RT-001 — 1회차 호출 성공 → 텍스트 즉시 반환 (재시도 없음)."""
        import urllib.request

        attempts = {"n": 0}

        def _fake_urlopen(req, timeout=None):
            attempts["n"] += 1
            return _FakeHTTPResponse(_OK_PAYLOAD)

        monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

        result = await _call_gemini_sdk("프롬프트")
        assert result == "정상 응답"
        assert attempts["n"] == 1

    @pytest.mark.asyncio
    async def test_gc_rt_002_503_then_success_retries_once(self, monkeypatch) -> None:
        """GC-RT-002 — 1회차 503 → 재시도 → 2회차 성공 → 텍스트 반환."""
        import urllib.error
        import urllib.request

        attempts = {"n": 0}

        def _fake_urlopen(req, timeout=None):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise urllib.error.HTTPError(req.full_url, 503, "Service Unavailable", {}, None)
            return _FakeHTTPResponse(_OK_PAYLOAD)

        monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

        result = await _call_gemini_sdk("프롬프트")
        assert result == "정상 응답"
        assert attempts["n"] == 2

    @pytest.mark.asyncio
    async def test_gc_rt_003_all_503_exhausts_retries_returns_none(
        self, monkeypatch, caplog
    ) -> None:
        """GC-RT-003 — 3회 모두 503 → 재시도 소진 → None + 경고 로그."""
        import logging
        import urllib.error
        import urllib.request

        attempts = {"n": 0}

        def _fake_urlopen(req, timeout=None):
            attempts["n"] += 1
            raise urllib.error.HTTPError(req.full_url, 503, "Service Unavailable", {}, None)

        monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

        with caplog.at_level(logging.WARNING, logger="app.services.gemini_client"):
            result = await _call_gemini_sdk("프롬프트")

        assert result is None
        assert attempts["n"] == 3
        assert "재시도 소진" in caplog.text

    @pytest.mark.asyncio
    async def test_gc_rt_004_non_transient_http_error_breaks_immediately(
        self, monkeypatch
    ) -> None:
        """GC-RT-004 — 404(비-transient) HTTPError → 재시도 없이 즉시 중단 → None."""
        import urllib.error
        import urllib.request

        attempts = {"n": 0}

        def _fake_urlopen(req, timeout=None):
            attempts["n"] += 1
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

        monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

        result = await _call_gemini_sdk("프롬프트")
        assert result is None
        assert attempts["n"] == 1

    @pytest.mark.asyncio
    async def test_gc_rt_005_generic_exception_retries_then_none(self, monkeypatch) -> None:
        """GC-RT-005 — urlopen 일반 Exception(타임아웃 등) → 재시도 후 소진 → None."""
        import urllib.request

        attempts = {"n": 0}

        def _fake_urlopen(req, timeout=None):
            attempts["n"] += 1
            raise TimeoutError("timed out")

        monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

        result = await _call_gemini_sdk("프롬프트")
        assert result is None
        assert attempts["n"] == 3
