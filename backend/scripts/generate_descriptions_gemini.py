"""1667 레시피 description 자동 생성 (Gemini 2.5 Flash) — 누락분 처리용.

용도: worker Agent (Sonnet) 가 stream watchdog timeout 으로 실패한 963 개 description 을
Gemini API 로 1개씩 안정적으로 생성. 결과는 batch_03.json/batch_04.json/batch_05.json 에 누적 저장.

학계 근거:
  - LLM-Augmented Content Vectorization (Wang 2023)
  - Manning et al. 2008 §9 Query Expansion (도메인 어휘 흡수)

가드레일 (code-reviewer 1차 검수 결과 반영):
  1. 지역 유래 단정 금지
  2. main_ingredients 외 재료 추측 금지
  3. country 분류 그대로 사용
  4. 상투구 빈도 제한 (해장/다이어트/비 오는 날/별미)

필수 키워드 (scientist 평가 결과 반영):
  - 약한 축 보강: 아이·자취·와인안주·혼밥·야식·간식
  - 강한 축 유지: 계절·날씨·해장·다이어트
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("gen-desc")

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR = _BACKEND_DIR / "data"
_OUT_DIR = _DATA_DIR / "recipe_descriptions"
_OUT_DIR.mkdir(parents=True, exist_ok=True)

_GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if not _GEMINI_KEY:
    # backend/.env 또는 프로젝트 root .env 에서 로드 시도
    for env_path in [_BACKEND_DIR / ".env", _BACKEND_DIR.parent / ".env"]:
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    _GEMINI_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        if _GEMINI_KEY:
            break

if not _GEMINI_KEY:
    log.error("GEMINI_API_KEY missing — set env or backend/.env")
    sys.exit(1)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)

_PROMPT_TEMPLATE = """한국 음식 레시피 추천 시스템의 TF-IDF 매칭 vocab 풍부화를 위한 description 을 작성해주세요.

[음식 정보]
- 음식명: {name}
- 국가 분류: {country_label}
- 테마 분류: {theme_label}
- 주재료: {main_ingredients}

[작성 규칙 — 절대 위반 금지]
1. 지역 유래 단정 금지: "강원도식"·"평안도식"·"함흥식"·"전라도식" 등 출처가 확실하지 않으면 사용 X. 모호하면 "이북식"·"전통" 또는 생략.
2. 주재료 외 재료 추측 금지: 위 "주재료" 목록에 없는 재료를 "들어간다"고 단정하지 말 것. 일반화 시 "보통 ~을 곁들임" 같은 완곡 표현 사용.
3. 국가 분류 그대로 사용: 음식 정의에 국가 분류와 다른 국적을 부여하지 말 것.
4. 상투구 자제: "해장"·"다이어트"·"비 오는 날"·"별미" 같은 표현 남용 X.

[필수 포함 키워드 (자연스럽게 1~3개)]
- 계절(봄/여름/가을/겨울) 또는 날씨(추운/따뜻한/시원한)
- 상황(손님 접대/도시락/명절/생일/야식/아침/점심/저녁/간식/혼자/자취생/가족)
- 대상(아이/어르신/가족/자취생/혼자)
- 건강·식단(가벼운/든든한/보양/소화/저칼로리/단백질/채식)
- 맛(매콤/달콤/짭짤/새콤/고소/구수/담백/진한/시원한)

[출력 형식 — 오직 2~3 문장의 한국어 description 만 평문으로 출력. JSON·따옴표·접두어·접미어 일절 금지]

음식명만으로 정확한 정의가 어려우면 주재료를 기반으로 합리적 추정 작성. "정확한 정의는 변형이 있을 수 있음" 같은 모호 표현 금지.
"""

_COUNTRY_LABEL = {
    "kr": "한식",
    "jp": "일식",
    "cn": "중식",
    "west": "양식",
    "etc": "동남아·멕시코·퓨전",
}
_THEME_LABEL = {
    "main": "메인요리",
    "soup": "국·찌개·탕",
    "side": "반찬·나물",
    "dessert": "디저트·간식",
    "drink": "음료",
}


def _label_country(c: str) -> str:
    return _COUNTRY_LABEL.get(c, c)


def _label_theme(t: str) -> str:
    return _THEME_LABEL.get(t, t)


async def _call_gemini(client: httpx.AsyncClient, payload: dict) -> str:
    """단일 Gemini 호출 → description 문자열 반환. 실패 시 빈 문자열."""
    url = f"{_GEMINI_URL}?key={_GEMINI_KEY}"
    try:
        resp = await client.post(url, json=payload, timeout=60.0)
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        # 평문 description — 줄바꿈·따옴표 정리, 한 줄로 합침
        text = text.replace("\n", " ").replace('"', "").strip()
        # 코드 블록 잔여물 방어
        if text.startswith("```"):
            text = text.strip("`").strip()
        # 길이 sanity (10자 이상)
        if len(text) < 10:
            return ""
        return text
    except (httpx.HTTPError, KeyError, IndexError) as e:
        log.warning("gemini call failed: %s", e)
        return ""


async def _process_one(client: httpx.AsyncClient, sem: asyncio.Semaphore, rec: dict) -> tuple[str, str]:
    """1개 레시피 → (cookid, description). 빈 description 도 반환 (호출자가 retry 결정)."""
    async with sem:
        prompt = _PROMPT_TEMPLATE.format(
            name=rec["name"],
            country_label=_label_country(rec.get("country", "kr")),
            theme_label=_label_theme(rec.get("theme", "main")),
            main_ingredients=rec.get("main_ingredients", ""),
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 1024,
            },
        }
        desc = await _call_gemini(client, payload)
        return rec["cookid"], desc


async def run(input_path: Path, output_path: Path, concurrency: int = 5) -> None:
    """input_path (jsonl) → output_path (json {cookid: desc}). 기존 항목 보존 (append 모드)."""
    existing: dict[str, str] = {}
    if output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        log.info("existing: %d entries in %s", len(existing), output_path.name)

    records: list[dict] = []
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rec = json.loads(line)
                if rec["cookid"] not in existing:
                    records.append(rec)

    if not records:
        log.info("no missing records — skip")
        return
    log.info("processing %d new records (concurrency=%d)", len(records), concurrency)

    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(http2=False) as client:
        tasks = [_process_one(client, sem, r) for r in records]
        done = 0
        for coro in asyncio.as_completed(tasks):
            cookid, desc = await coro
            if desc:
                existing[cookid] = desc
            done += 1
            if done % 20 == 0:
                # 중간 저장 (장애 대비)
                output_path.write_text(
                    json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                log.info("progress: %d/%d (saved)", done, len(records))

    output_path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info("DONE: %d entries written to %s", len(existing), output_path.name)


def main() -> None:
    """CLI: python generate_descriptions_gemini.py <input.jsonl> <output.json> [concurrency]"""
    if len(sys.argv) < 3:
        log.error("usage: %s <input.jsonl> <output.json> [concurrency=5]", sys.argv[0])
        sys.exit(2)
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    concurrency = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    asyncio.run(run(input_path, output_path, concurrency))


if __name__ == "__main__":
    main()
