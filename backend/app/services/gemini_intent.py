"""자연어 의도 파싱 (LLM-augmented) — 감정·간접 표현을 음식 검색 의도로 변환.

문제: 의미 임베딩은 '비 오는 날 국물' 같은 상황어는 잡지만, '오늘 짜증나'(→매운),
'축하할 일 있어'(→특별한)처럼 음식 단어가 전혀 없는 감정/간접 표현은 추론하지 못한다.

해결: Gemini 가 사용자의 자유로운 한국어를 '음식 검색용 묘사 + 맵기 추정'으로 번역한다.
MOOD_MAP 수동 사전과의 결정적 차이 — 미리 적은 표현만 아는 게 아니라 임의의 말투를 추론.
입력 제한이 불필요해진다 (사용자는 자유 입력, LLM이 음식 의도로 변환).

폴백: 키 미설정·네트워크 실패·파싱 실패 시 원문을 그대로 반환 → 임베딩이 원문으로 동작.
"""

from __future__ import annotations

import logging

from app.services.gemini_client import _call_gemini_sdk, _parse_response_text

_logger = logging.getLogger(__name__)

_PROMPT = """너는 한국 음식 추천 도우미다. 사용자의 자유로운 한국어 입력을 '음식 검색에 쓸 구체적 묘사'로 변환하라.
입력이 감정·상황·날씨처럼 음식과 무관해 보여도, 그 의도를 음식 특성(맛·종류·온도·상황)으로 추론하라.

예시:
- "오늘 짜증나" → 스트레스 풀리는 맵고 얼큰하고 자극적인 음식, 매운 볶음이나 칼칼한 국물
- "축하할 일이 있어" → 근사하고 특별한 고급 요리, 스테이크나 잡채 같은 정성 요리
- "몸이 으슬으슬 추워" → 뜨끈하고 따뜻한 국물 요리, 얼큰한 찌개나 국
- "입맛이 없어" → 담백하고 새콤한 가벼운 음식, 비빔국수나 샐러드
- "기분 꿀꿀해" → 따뜻하게 위로되는 음식, 부드러운 죽이나 국물

반드시 JSON만 출력:
{{"food_query": "음식 묘사 (한국어, 맛·종류·재료 포함, 1~2문장)", "spicy": 1에서 5 사이 정수 또는 null}}

사용자 입력: "{text}"
"""


async def parse_food_intent(user_context: str) -> dict:
    """자연어 → {"food_query": 음식묘사, "spicy": 1~5|None, "source": gemini|fallback|empty}.

    food_query 는 임베딩 nl_text 로, spicy 는 맵기 선호 추정치로 사용 가능.
    """
    uc = (user_context or "").strip()
    if not uc:
        return {"food_query": "", "spicy": None, "source": "empty"}
    raw = await _call_gemini_sdk(_PROMPT.format(text=uc.replace('"', "'")))
    parsed = _parse_response_text(raw or "")
    if not parsed or not parsed.get("food_query"):
        return {"food_query": uc, "spicy": None, "source": "fallback"}
    spicy = parsed.get("spicy")
    try:
        spicy = int(spicy) if spicy is not None else None
        if spicy is not None and not (1 <= spicy <= 5):
            spicy = None
    except (ValueError, TypeError):
        spicy = None
    return {"food_query": str(parsed["food_query"]).strip(), "spicy": spicy, "source": "gemini"}
