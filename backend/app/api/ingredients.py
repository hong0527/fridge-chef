"""/api/ingredients/* — 재료 자동완성 검색 (FR-FRIDGE-03).

frontend/lib/api.ts:searchIngredients()가 호출. SYNONYM_MAP 기반 prefix 매칭으로
사용자가 타이핑할 때마다 정규화된 대표 키워드를 반환한다.

NFR-PERF-001: 자동완성 응답은 인메모리 dict 조회로 < 50ms.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.synonym_map import SYNONYM_MAP, normalize

router = APIRouter()


# 검색 후보 = SYNONYM_MAP의 키(동의어) ∪ 값(대표 키워드) 합집합.
# 사용자가 "달걀"을 타이핑하든 "계란"을 타이핑하든 둘 다 후보로 나타나야 한다.
_ALL_INGREDIENTS: list[str] = sorted(set(SYNONYM_MAP.keys()) | set(SYNONYM_MAP.values()))


@router.get("/search", response_model=list[str])
async def search_ingredients(
    q: str = Query(default="", min_length=0, max_length=50, description="검색 prefix"),
    limit: int = Query(default=8, ge=1, le=20),
) -> list[str]:
    """재료명 prefix 매칭 — 정규화된 대표 키워드를 우선 반환.

    예: q="달" → ["달걀", "닭고기", "닭가슴살", ...] (prefix 일치 + 정규형 우선)
    """
    query = q.strip()
    if not query:
        return []
    # 정규형 우선 정렬 (SYNONYM_MAP의 value에 등장하는 키워드를 앞에)
    canonical = set(SYNONYM_MAP.values())
    matches = [ing for ing in _ALL_INGREDIENTS if ing.startswith(query)]
    matches.sort(key=lambda x: (x not in canonical, x))  # canonical 먼저, 그 후 알파벳
    # 정규화한 결과로 dedup (예: "달걀"과 "계란"이 둘 다 prefix 매칭이면 "계란"만)
    seen: set[str] = set()
    out: list[str] = []
    for m in matches:
        norm = normalize(m)
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
        if len(out) >= limit:
            break
    return out
