"""preprocessed CSV → /tmp/recipes_1667.pkl 재생성 (DB 없이).

/tmp 는 재부팅·날짜경계에 비워질 수 있다. 평가 스크립트(evaluate_recommend.py,
evaluate_semantic_nl.py)가 기대하는 1667 코퍼스 캐시를 CSV 에서 직접 복원한다.
import_real_recipes.py 의 변환 로직(country/theme/spicy/allergen 매핑)을 재사용.

실행: cd backend && python scripts/rebuild_corpus_cache.py
"""

from __future__ import annotations

import csv
import os
import pickle
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_BACKEND / "scripts"))

os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod-padding-1234567890")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("GEMINI_API_KEY", "")

CSV_PATH = Path(
    os.environ.get(
        "RECIPE_CSV_PATH",
        str(_BACKEND.parents[1] / "preprocessed_recipe (1).csv"),
    )
)
OUT = Path("/tmp/recipes_1667.pkl")


def main() -> int:
    if not CSV_PATH.exists():
        print(f"❌ CSV 없음: {CSV_PATH}")
        return 1

    from app.core.synonym_map import normalize_list
    import import_real_recipes as imp

    rows: list[dict] = []
    with CSV_PATH.open("r", encoding="cp949", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cookid = (row.get("cookid") or "").strip()
            name = (row.get("메뉴 이름") or "").strip()
            if not cookid or not name:
                continue
            main_ing = imp.parse_listish(row.get("main_ingredients", "[]"))
            sub_ing = imp.parse_listish(row.get("sub_ingredients", "[]"))
            whole = normalize_list(main_ing + sub_ing)
            method = imp.parse_listish(row.get("방법 분류", "[]"))
            try:
                cook = int(row.get("조리시간", "30") or 30)
            except ValueError:
                cook = 30
            allergens = sorted(set(imp.extract_allergens([name]) + imp.extract_allergens(whole)))
            rows.append({
                "recipe_id": cookid,
                "name": name,
                "whole_ingredients": whole,
                "cook_min": cook,
                "spicy": imp.to_spicy(row.get("spiciness", "0")),
                "difficulty_level": imp.to_difficulty(row.get("난이도 분류", "초보환영")),
                "is_low_calorie": imp.to_low_calorie(row.get("low_calorie", "0")),
                "country": imp.to_country(row.get("국가 분류", "")),
                "theme": imp.to_theme(method),
                "allergens": allergens,
            })

    if not rows:
        print("❌ 파싱된 레시피 0건 — CSV 컬럼명 확인 필요")
        return 1

    OUT.write_bytes(pickle.dumps(rows))
    # 분포 요약 (검증)
    from collections import Counter
    cc = Counter(r["country"] for r in rows)
    tc = Counter(r["theme"] for r in rows)
    print(f"✅ {OUT} 저장: {len(rows)}건")
    print(f"   country 분포: {dict(cc)}")
    print(f"   theme 분포:   {dict(tc)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
