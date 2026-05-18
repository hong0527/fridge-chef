"""Gemini 2.5 Flash 클라이언트 (Free Tier, 결정론적 호출).

NFR-REL-001: 외부 호출 8초 타임아웃 후 폴백 경로 (model_b 호출 측에서 처리).
NFR-EVAL-002: citation_id 화이트리스트 검증 ≥95%.
NFR-SEC-001: API 키 환경변수 (`GEMINI_API_KEY`).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.core.config import settings

_logger = logging.getLogger(__name__)


def _build_prompt(candidates: list[dict], user_context: str) -> str:
    """JSON-only 응답을 강제하는 시스템 프롬프트."""
    candidate_lines = []
    for c in candidates:
        candidate_lines.append(
            f"- recipe_id={c['recipe_id']} | name={c['name']} | cook_min={c['cook_min']} | "
            f"have={c.get('have', [])} | missing={c.get('missing', [])} | "
            f"final_score={c.get('final_score', 0)}"
        )
    candidate_block = "\n".join(candidate_lines)
    ctx = user_context.strip() or "(특이사항 없음)"
    return (
        "당신은 한국어 요리 추천 큐레이터입니다.\n"
        "아래 후보 레시피 중에서 사용자의 문맥과 가장 잘 어울리는 3개를 골라\n"
        "JSON 객체만 출력하세요. 마크다운, 설명, 코드펜스 금지.\n\n"
        f"사용자 문맥: {ctx}\n\n"
        "후보:\n"
        f"{candidate_block}\n\n"
        "출력 스키마 (반드시 이 키만 사용):\n"
        '{\n'
        '  "selected": ["recipe_id", "recipe_id", "recipe_id"],\n'
        '  "reasons":  ["한국어 한 문장 이유 1", "이유 2", "이유 3"],\n'
        '  "citation_ids": ["selected와 동일한 3개 recipe_id"]\n'
        '}\n'
    )


def _parse_response_text(text: str) -> dict[str, Any] | None:
    """모델 응답에서 JSON 객체를 추출. 코드펜스/잡음 허용."""
    if not text:
        return None
    text = text.strip()
    # 코드펜스 제거
    if text.startswith("```"):
        # ```json ... ``` 처리
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    # 첫 { ~ 마지막 } 사이만 추출
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


async def _call_gemini_sdk(prompt: str) -> str | None:
    """동기 SDK를 스레드로 격리해 비동기화."""
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError:
        _logger.warning("google-generativeai 미설치 → 폴백")
        return None
    if not settings.gemini_api_key:
        _logger.warning("GEMINI_API_KEY 미설정 → 폴백")
        return None

    def _sync_call() -> str | None:
        try:
            genai.configure(api_key=settings.gemini_api_key)
            model = genai.GenerativeModel(
                settings.gemini_model,
                generation_config={
                    "temperature": 0.0,
                    "response_mime_type": "application/json",
                },
            )
            resp = model.generate_content(prompt)
            return getattr(resp, "text", None)
        except Exception as exc:  # pragma: no cover — 네트워크 의존
            _logger.warning("Gemini SDK 호출 실패: %s", exc)
            return None

    return await asyncio.to_thread(_sync_call)


async def gemini_select_top3(
    candidates: list[dict],
    user_context: str,
) -> dict | None:
    """후보 중 3개를 Gemini로 선별 + 한국어 이유 반환.

    Returns:
        성공: {"selected": [id*3], "reasons": [str*3], "citation_ids": [id*3]}
        실패/타임아웃: None  (호출자는 final_score 폴백으로 처리)
    """
    if not candidates:
        return None
    prompt = _build_prompt(candidates, user_context)
    try:
        text = await asyncio.wait_for(_call_gemini_sdk(prompt), timeout=settings.gemini_timeout_s)
    except asyncio.TimeoutError:
        _logger.warning("Gemini 타임아웃 (%.1fs) → 폴백", settings.gemini_timeout_s)
        return None
    if not text:
        return None

    parsed = _parse_response_text(text)
    if not parsed or not isinstance(parsed, dict):
        return None
    if "selected" not in parsed or not isinstance(parsed["selected"], list):
        return None
    # 형 보정
    parsed.setdefault("reasons", [])
    parsed.setdefault("citation_ids", parsed["selected"])
    return parsed
