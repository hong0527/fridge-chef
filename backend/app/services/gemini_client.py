"""Gemini 2.5 Flash 클라이언트 (Free Tier, 결정론적 호출).

NFR-REL-001: 외부 호출 8초 타임아웃 후 폴백 경로 (model_b 호출 측에서 처리).
NFR-EVAL-002: citation_id 화이트리스트 검증 ≥95%.
NFR-SEC-002: API 키 환경변수 (`GEMINI_API_KEY`).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.core.config import settings

_logger = logging.getLogger(__name__)


_COUNTRY_KR = {"kr": "한식", "cn": "중식", "jp": "일식", "west": "양식", "etc": "기타"}
_THEME_KR = {"main": "메인", "side": "반찬", "soup": "국·탕", "dessert": "디저트", "drink": "음료"}
_DIFF_KR = {1: "초보", 2: "중급", 3: "고급"}


def _build_prompt(candidates: list[dict], user_context: str) -> str:
    """JSON-only 큐레이터 프롬프트 — 메타데이터(맵기·국가·테마·난이도) 전달 + reason 규칙 강제.

    이전 버전: name/cook_min/have/missing/final_score 만 전달 → Gemini가 일반화 회피.
    Critic 결과 반영 (사용자 시연 피드백: 'reason 빈약·일반화').
    """
    lines = []
    for i, c in enumerate(candidates, 1):
        have = c.get("have", []) or []
        missing = c.get("missing", []) or []
        lines.append(
            f"[{i}] id={c['recipe_id']} | {c['name']} | "
            f"{_COUNTRY_KR.get(c.get('country', 'kr'), '한식')}·"
            f"{_THEME_KR.get(c.get('theme', 'main'), '메인')} | "
            f"조리 {c['cook_min']}분 | 맵기 {c.get('spicy', 1)}/5 | "
            f"난이도 {_DIFF_KR.get(c.get('difficulty_level', 1), '초보')} | "
            f"보유재료({len(have)}): {', '.join(have) if have else '없음'} | "
            f"부족재료({len(missing)}): {', '.join(missing) if missing else '없음'}"
        )
    candidate_block = "\n".join(lines)
    ctx = user_context.strip() or "(특이사항 없음)"
    return f"""당신은 한국어 요리 큐레이터입니다. 후보 3개를 골라 각 추천 이유를 작성하세요.

[사용자 문맥]
{ctx}

[후보 목록]
{candidate_block}

[reason 작성 규칙 — 반드시 준수]
1) 각 reason 은 한국어 2~3문장, 80~140자.
2) 첫 문장: 사용자 문맥("{ctx}")의 키워드를 직접 인용하거나 명시적으로 연결.
3) 둘째 문장: 이 레시피의 매력 포인트 1가지 (맛 특징·식감·향·풍미·궁합 등 구체).
4) (선택) 셋째 문장: 보유재료·조리시간·매운맛 중 1개를 구체 수치·이름으로 활용 제안.
5) 금지어: "맛있는", "인기", "추천합니다", "좋습니다", "높은 점수" (일반화 회피).
6) 3개 reason 은 서로 다른 매력 포인트 축(맛·재료 활용·조리 편의 등)으로 차별화.

[좋은 예시]
사용자 문맥: "비 오는 날 따뜻하게"
reason: "비 오는 날 마음까지 데워주는 든든한 한 그릇입니다. 진한 된장 국물에 두부의 부드러운 식감이 어우러져 깊은 풍미가 일품이죠. 보유한 두부·대파만으로 25분 만에 완성 가능합니다."

[출력 — JSON 객체만, 마크다운·코드펜스·설명 금지]
{{
  "selected": ["recipe_id", "recipe_id", "recipe_id"],
  "reasons":  ["규칙을 따른 2문장 이유", "이유 2", "이유 3"],
  "citation_ids": ["selected와 동일한 3개 recipe_id"]
}}
"""


def _parse_response_text(text: str) -> dict[str, Any] | None:
    """모델 응답에서 JSON 객체를 추출. 코드펜스/잡음 허용."""
    if not text:
        return None
    text = text.strip()
    # 코드펜스 제거 — strip("`") 은 내용 중 backtick 도 제거할 위험이 있어 줄 단위로 처리
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
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
    """Gemini REST 호출 (stdlib urllib, 스레드 격리로 비동기화).

    SDK(google-generativeai 0.8.x) 가 thinking_config 를 지원하지 않아 REST 로 호출한다.
    gemini-2.5 의 thinking(추론) 모드를 thinkingBudget=0 으로 끄면 응답이 8s→1s 로 단축돼
    recommend_timeout_s(12s) 안에 실제 Gemini 결과를 받는다(폴백 회피). responseMimeType=JSON
    유지로 기존 _parse_response_text 호환. 실패/타임아웃 시 None → 호출측 결정론 폴백.
    """
    if not settings.gemini_api_key:
        _logger.warning("GEMINI_API_KEY 미설정 → 폴백")
        return None
    import json as _json
    import time
    import urllib.error
    import urllib.request

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
            # thinking 끄기 — 2.5 모델 지연 주범. flash 는 0 지원. (pro 는 무시될 수 있음)
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    data = _json.dumps(body).encode("utf-8")

    def _sync_call() -> str | None:
        # 503(과부하)/429(레이트리밋)/500 일시 오류는 구글 쪽 transient — 지수 백오프로 재시도.
        # 운영 로그 'HTTP Error 503: Service Unavailable' 대응. gemini_timeout_s 안에서 최대 3회.
        last_err = "unknown"
        for attempt in range(3):
            try:
                req = urllib.request.Request(
                    url, data=data, headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=settings.gemini_timeout_s) as resp:
                    d = _json.loads(resp.read().decode("utf-8"))
                return d["candidates"][0]["content"]["parts"][0]["text"]
            except urllib.error.HTTPError as e:
                last_err = f"HTTP {e.code}"
                if e.code in (429, 500, 503) and attempt < 2:
                    time.sleep(0.7 * (attempt + 1))  # 0.7s → 1.4s
                    continue
                break
            except Exception as exc:  # 네트워크/타임아웃 등 — 1회 재시도 후 폴백
                last_err = str(exc)
                if attempt < 2:
                    time.sleep(0.7 * (attempt + 1))
                    continue
                break
        _logger.warning("Gemini REST 호출 실패(재시도 소진): %s", last_err)
        return None

    return await asyncio.to_thread(_sync_call)


def _build_prompt_model_a(candidates: list[dict], user_context: str) -> str:
    """Model A(냉털)용 reason 생성 프롬프트 — 모든 후보의 보유율 100% 가정.

    Model B 와 달리 missing 이 없으므로 "지금 바로 만들 수 있다"는 톤으로 작성.
    """
    lines = []
    for i, c in enumerate(candidates, 1):
        have = c.get("have", []) or []
        lines.append(
            f"[{i}] id={c['recipe_id']} | {c['name']} | "
            f"{_COUNTRY_KR.get(c.get('country', 'kr'), '한식')}·"
            f"{_THEME_KR.get(c.get('theme', 'main'), '메인')} | "
            f"조리 {c['cook_min']}분 | 맵기 {c.get('spicy', 1)}/5 | "
            f"난이도 {_DIFF_KR.get(c.get('difficulty_level', 1), '초보')} | "
            f"보유재료: {', '.join(have) if have else '냉장고 재료'}"
        )
    candidate_block = "\n".join(lines)
    ctx = user_context.strip() or "(특이사항 없음)"
    return f"""당신은 한국어 요리 큐레이터입니다. 모든 후보의 추천 이유를 작성하세요.

[사용자 문맥]
{ctx}

[후보 목록 — 모든 재료가 냉장고에 있어 바로 만들 수 있음]
{candidate_block}

[reason 작성 규칙 — 반드시 준수]
1) 각 reason 은 한국어 2~3문장, 80~140자.
2) 첫 문장: 사용자 문맥("{ctx}")의 키워드를 직접 인용하거나 명시적으로 연결.
3) 둘째 문장: 이 레시피의 매력 포인트 1가지 (맛 특징·식감·향·풍미·궁합 등 구체).
4) (선택) 셋째 문장: 보유 재료·조리시간·매운맛 중 1개를 구체 활용 제안.
5) 금지어: "맛있는", "인기", "추천합니다", "좋습니다", "높은 점수" (일반화 회피).
6) 후보 모두 reason 은 서로 다른 매력 포인트 축으로 차별화.

[출력 — JSON 객체만, 마크다운·코드펜스·설명 금지]
{{
  "reasons": ["입력 순서대로 후보 1의 이유", "후보 2의 이유", ...]
}}
"""


async def gemini_reasons_for_model_a(
    candidates: list[dict],
    user_context: str,
) -> list[str] | None:
    """Model A 후보 N개에 자연어 추천 이유를 생성.

    Model B(`gemini_select_top3`)와 달리 후보 순서·개수 그대로 유지하고 reason 만 생성.
    실패/타임아웃 시 None 반환 → 호출자는 결정론 폴백으로 처리.
    """
    if not candidates:
        return None
    prompt = _build_prompt_model_a(candidates, user_context)
    try:
        text = await asyncio.wait_for(_call_gemini_sdk(prompt), timeout=settings.gemini_timeout_s)
    except TimeoutError:
        _logger.warning("Gemini A 타임아웃 (%.1fs) → 폴백", settings.gemini_timeout_s)
        return None
    if not text:
        return None
    parsed = _parse_response_text(text)
    if not parsed or "reasons" not in parsed or not isinstance(parsed["reasons"], list):
        return None
    reasons = [str(r).strip() for r in parsed["reasons"] if r]
    if len(reasons) != len(candidates):
        # 부분 일치 시에도 가능한 만큼 반환 (호출자가 padding).
        return reasons
    return reasons


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
    except TimeoutError:
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
    # NFR-EVAL-002: citation_ids 누락 시 빈 리스트로 폴백 → model_b 검증에서 환각 차단.
    # 자기인용(selected 그대로 채우기)은 환각 차단을 무력화하므로 금지.
    parsed.setdefault("citation_ids", [])
    return parsed
