"""대규모 레시피 데이터셋 ETL — CSV(CP949) + 이미지 1667건을 DB로 적재.

소스:
  CSV: /Users/honghwasu/softwareTeamProject/preprocessed_recipe (1).csv (CP949)
  이미지: /Users/honghwasu/softwareTeamProject/images/{cookid}.jpg

대상:
  Postgres recipes 테이블 (기존 35건은 비운 뒤 1667건 적재)
  backend/data/recipes_images/{cookid}.jpg (정적 서빙용 복사)

매핑:
  cookid           → recipe_id (str)
  메뉴 이름         → name
  국가 분류 (text)  → country: 한식=kr, 일본=jp, 중국=cn, 서양·이탈리아=west, 퓨전·동남아·멕시코=etc
  방법 분류 첫 원소 → theme: 밥/구이/볶음/찜/조림/만두/도시락→main,
                              국/찌개/탕→soup, 나물/밑반찬/김치/생채→side,
                              빵/케이크/쿠키/디저트→dessert, 음료→drink
  난이도 분류       → difficulty_level: 초보환영=1, 보통=2, 어려움=3
  spiciness (0~1)  → spicy (1~5): round(s*4)+1
  whole_ingredients → JSONB (Python list 그대로)
  조리 단계         → steps JSONB
  low_calorie       → is_low_calorie bool
  자동 알레르기 추출 → allergens JSONB (재료 키워드 패턴 매칭)

실행:
  docker exec fridgechef-backend python /backend_scripts/import_real_recipes.py
  또는 호스트에서: cd backend && python scripts/import_real_recipes.py
"""

from __future__ import annotations

import ast
import asyncio
import csv
import logging
import os
import shutil
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("import")

_BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_DIR))

# 환경변수 보정 (호스트 실행 시 .env 미적용 대비)
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod-padding-1234567890")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://fridgechef:fridgechef@localhost:5432/fridgechef",
)

from sqlalchemy import delete, text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.synonym_map import normalize_list  # noqa: E402
from app.models.orm import RecipeRow  # noqa: E402

# ─── 경로 ────────────────────────────────────────────────────
PROJECT_ROOT = Path("/Users/honghwasu/softwareTeamProject")
CSV_PATH = PROJECT_ROOT / "preprocessed_recipe (1).csv"
IMG_SRC_DIR = PROJECT_ROOT / "images"
IMG_DST_DIR = _BACKEND_DIR / "data" / "recipes_images"

# ─── 매핑 테이블 ─────────────────────────────────────────────
COUNTRY_MAP = {
    "한식": "kr",
    "일본": "jp",
    "중국": "cn",
    "서양": "west",
    "이탈리아": "west",
    "퓨전": "etc",
    "동남아시아": "etc",
    "멕시코": "etc",
}

THEME_MAP = {
    # main
    "밥": "main", "만두": "main", "구이": "main", "볶음": "main",
    "튀김": "main", "찜": "main", "부침": "main", "조림": "main",
    "도시락": "main", "면": "main", "죽": "main", "스프": "main",
    "회": "main", "초밥": "main", "전골": "main",
    # soup
    "국": "soup", "찌개": "soup", "탕": "soup",
    # side
    "나물": "side", "밑반찬": "side", "김치": "side", "생채": "side",
    "젓갈": "side", "장아찌": "side", "샐러드": "side", "양념": "side",
    # dessert
    "빵": "dessert", "케이크": "dessert", "쿠키": "dessert",
    "디저트": "dessert", "후식": "dessert", "과자": "dessert",
    "떡": "dessert", "잼": "dessert", "타르트": "dessert", "푸딩": "dessert",
    # drink
    "음료": "drink", "차": "drink", "주스": "drink", "커피": "drink",
    "스무디": "drink", "셰이크": "drink",
}

DIFFICULTY_MAP = {"초보환영": 1, "보통": 2, "어려움": 3}

# 알레르기 자동 태깅 키워드 (재료 기반) — false positive 방지를 위해 정확 매칭 위주.
# code-reviewer HIGH 수정: "파슬리"→밀, "닭갈비양념"→돼지고기 같은 부분 문자열 오탐 차단.
# 매칭 규칙은 _ingredient_has_allergen()에서 단어 경계·완전 일치 우선으로 처리.
ALLERGEN_PATTERNS = {
    "계란": ["계란", "달걀", "노른자", "흰자", "메추리알"],
    "우유": ["우유", "치즈", "버터", "크림", "요거트", "요구르트", "생크림", "휘핑크림", "분유"],
    "메밀": ["메밀"],
    "땅콩": ["땅콩"],
    # "콩" 단독 패턴 제거 — "땅콩"이 substring 매칭되어 false positive.
    "대두": ["대두", "두부", "된장", "간장", "두유", "콩나물", "메주콩", "검은콩", "흰콩", "백태", "흑태"],
    "밀": ["밀가루", "빵", "면", "스파게티", "파스타", "라면", "우동", "라멘", "칼국수", "수제비", "만두피", "튀김가루", "부침가루", "통밀", "펜네", "마카로니", "라자냐", "푸실리", "리조니", "탈리아텔레", "링귀니"],
    "고등어": ["고등어"],
    "게": ["꽃게", "대게", "킹크랩", "게살"],  # "게" 단독 제거 — "게맛살" 등 false positive 위험
    "새우": ["새우", "왕새우", "흰다리새우"],
    "돼지고기": ["돼지고기", "삼겹살", "삼겹", "돼지목살", "돼지등심", "돼지안심", "돼지갈비"],
    "복숭아": ["복숭아"],
    "토마토": ["토마토"],
    "호두": ["호두"],
    # "닭갈비" 같은 합성어가 "갈비"(쇠고기) substring 매칭되지 않도록 닭 패턴을 더 구체화.
    "닭고기": ["닭고기", "닭가슴살", "닭다리", "닭날개", "닭안심", "닭정육", "닭갈비", "닭갈비살", "닭다리살", "닭봉", "백숙용닭"],
    # "안심" 단독 제거 — "닭안심"이 닭고기로 분류되어야 하므로 쇠고기 패턴에 단독 substring 금지.
    "쇠고기": ["소고기", "쇠고기", "차돌박이", "우삼겹", "한우", "쇠갈비", "소갈비", "갈빗살", "LA갈비", "양념갈비살", "갈비찜용", "갈비찜"],
    "오징어": ["오징어", "낙지", "주꾸미", "문어"],
    "조개류(굴, 전복, 홍합 포함)": ["조개", "굴", "전복", "홍합", "바지락"],
    "잣": ["잣"],
    "어류": ["어묵", "생선", "고등어", "연어", "삼치", "참치", "명태", "동태", "갈치", "꽁치", "도미", "조기", "황태"],
}

# false positive 방지 — 알레르기와 무관한데 패턴 substring 매칭되는 단어 차단 리스트.
ALLERGEN_FALSE_POSITIVE_SUBSTRINGS = {
    "파슬리",  # "밀" 패턴이 "파슬리"의 부분이라고 매칭되는 것 차단 (실제론 그렇지 않지만 안전망)
    "닭갈비양념",  # "갈비" → 쇠고기 false positive
    "양념갈비",
    "밀크씨슬", "밀크쉐이크",  # "밀" 매칭 차단
}

# ─── 변환 함수 ───────────────────────────────────────────────


def parse_listish(value: str) -> list[str]:
    """Python repr 형식 리스트 안전 파싱. 실패 시 빈 리스트."""
    if not value or not value.strip():
        return []
    try:
        result = ast.literal_eval(value)
        if isinstance(result, list):
            return [str(x).strip() for x in result if x]
        return []
    except (ValueError, SyntaxError):
        return []


def to_country(text: str) -> str:
    return COUNTRY_MAP.get(text.strip(), "etc")


def to_theme(method_list: list[str]) -> str:
    """방법 분류 리스트 → theme. 매칭 우선순위 — 더 구체적인 단어 먼저."""
    for m in method_list:
        m = m.strip()
        if m in THEME_MAP:
            return THEME_MAP[m]
    # 부분 매칭 fallback
    for m in method_list:
        for key, theme in THEME_MAP.items():
            if key in m:
                return theme
    return "main"


def to_difficulty(text: str) -> int:
    return DIFFICULTY_MAP.get(text.strip(), 1)


def to_spicy(spiciness: str) -> int:
    """0.0~1.0 float → 1~5 정수."""
    try:
        s = float(spiciness)
        return max(1, min(5, round(s * 4) + 1))
    except (ValueError, TypeError):
        return 1


def to_low_calorie(value: str) -> bool:
    return str(value).strip() in ("1", "True", "true")


def _ingredient_has_allergen(ing: str, patterns: list[str]) -> bool:
    """단일 재료 문자열이 알레르기 패턴 중 하나에 매칭되는지 (false positive 방지).

    매칭 전략 (우선순위):
    1) FALSE_POSITIVE 셋에 있으면 무조건 미매칭.
    2) 정확 일치 (재료명 == 패턴) 또는
    3) substring 매칭. 단 "닭/돼지" 접두사가 있는 재료는 "쇠고기" 패턴 substring 매칭에서 제외
       — "닭갈비"가 "갈비"(쇠고기) 패턴에 잡히는 false positive 차단.
    """
    if ing in ALLERGEN_FALSE_POSITIVE_SUBSTRINGS:
        return False
    # 닭/돼지 접두사 합성어는 쇠고기 패턴(LA갈비/쇠갈비/...)에서 분리.
    # 패턴 자체가 "쇠/소/한우" 명시이거나 닭/돼지 접두사가 재료에 없으면 substring 매칭 OK.
    if ing.startswith(("닭", "돼지")):
        return any(p in ing for p in patterns if p.startswith(("닭", "돼지")))
    return any(p in ing for p in patterns)


def extract_allergens(whole_ingredients: list[str]) -> list[str]:
    """재료 리스트에서 알레르기 카테고리 자동 추출 (NFR-EVAL-001 자동화)."""
    found: set[str] = set()
    for ing in whole_ingredients:
        ing_norm = ing.strip()
        for category, patterns in ALLERGEN_PATTERNS.items():
            if _ingredient_has_allergen(ing_norm, patterns):
                found.add(category)
    return sorted(found)


# ─── 행 → ORM ─────────────────────────────────────────────────


def row_to_recipe(row: dict) -> RecipeRow | None:
    """CSV 한 행을 RecipeRow로 변환. 잘못된 행은 None 반환.

    contains_all 매칭용 재료는 **주재료(main_ingredients)+부재료(sub_ingredients)만** 사용.
    양념(seasoning)은 BASIC_SEASONINGS 외에도 매우 다양하므로 매칭에서 제외 — 사용자 보유 가정.
    """
    cookid = row.get("cookid", "").strip()
    name = row.get("메뉴 이름", "").strip()
    if not cookid or not name:
        return None

    # 주재료 + 부재료만 (양념 제외) → contains_all 통과율 정상화
    main_ing = parse_listish(row.get("main_ingredients", "[]"))
    sub_ing = parse_listish(row.get("sub_ingredients", "[]"))
    whole_ing_raw = main_ing + sub_ing
    whole_ing_norm = normalize_list(whole_ing_raw)
    method_list = parse_listish(row.get("방법 분류", "[]"))
    steps = parse_listish(row.get("조리 단계", "[]"))

    try:
        cook_min = int(row.get("조리시간", "30") or 30)
    except ValueError:
        cook_min = 30

    # 알레르기 자동 태깅 — 재료 + 메뉴 이름 양쪽에서 추출 (이름·재료 불일치 보강).
    # 예: "치즈토마토"의 main_ingredients=["토마토"]만 있어도 name "치즈토마토"에서 "치즈"→우유 태깅.
    name_allergens = extract_allergens([name])
    ing_allergens = extract_allergens(whole_ing_norm)
    allergens_combined = sorted(set(name_allergens + ing_allergens))

    return RecipeRow(
        recipe_id=cookid,
        name=name,
        whole_ingredients=whole_ing_norm,
        steps=steps,
        cook_min=cook_min,
        spicy=to_spicy(row.get("spiciness", "0")),
        difficulty_level=to_difficulty(row.get("난이도 분류", "초보환영")),
        is_low_calorie=to_low_calorie(row.get("low_calorie", "0")),
        country=to_country(row.get("국가 분류", "")),
        theme=to_theme(method_list),
        allergens=allergens_combined,
        image_url=f"/static/recipes/{cookid}.jpg" if (IMG_SRC_DIR / f"{cookid}.jpg").exists() else None,
    )


# ─── 메인 ────────────────────────────────────────────────────


async def main() -> int:
    if not CSV_PATH.exists():
        log.error("CSV not found: %s", CSV_PATH)
        return 1
    log.info("CSV source: %s", CSV_PATH)
    log.info("Image source: %s (%d files)", IMG_SRC_DIR, len(list(IMG_SRC_DIR.glob("*.jpg"))))

    # 1) 이미지 복사
    IMG_DST_DIR.mkdir(parents=True, exist_ok=True)
    img_copied = 0
    for jpg in IMG_SRC_DIR.glob("*.jpg"):
        dst = IMG_DST_DIR / jpg.name
        if not dst.exists():
            shutil.copy2(jpg, dst)
        img_copied += 1
    log.info("Images copied to %s: %d", IMG_DST_DIR, img_copied)

    # 2) CSV 파싱
    recipes: list[RecipeRow] = []
    skipped = 0
    with CSV_PATH.open("r", encoding="cp949", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            r = row_to_recipe(row)
            if r is None:
                skipped += 1
                continue
            recipes.append(r)
    log.info("Parsed %d recipes, skipped %d", len(recipes), skipped)

    # 3) DB 적재
    engine = create_async_engine(os.environ["DATABASE_URL"], echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as session:
        await session.execute(delete(RecipeRow))
        await session.commit()
        log.info("Cleared existing recipes")

        BATCH = 200
        for i in range(0, len(recipes), BATCH):
            session.add_all(recipes[i : i + BATCH])
            await session.commit()
            log.info("  Inserted %d/%d", min(i + BATCH, len(recipes)), len(recipes))

        # 4) 인덱스 추가 (1667건 운영용)
        for stmt in [
            "CREATE INDEX IF NOT EXISTS ix_recipes_country ON recipes (country);",
            "CREATE INDEX IF NOT EXISTS ix_recipes_theme ON recipes (theme);",
            "CREATE INDEX IF NOT EXISTS ix_recipes_difficulty ON recipes (difficulty_level);",
            "CREATE INDEX IF NOT EXISTS ix_recipes_low_calorie ON recipes (is_low_calorie);",
            "CREATE INDEX IF NOT EXISTS ix_recipes_country_theme_diff ON recipes (country, theme, difficulty_level);",
            "CREATE INDEX IF NOT EXISTS ix_recipes_ingredients_gin ON recipes USING GIN (whole_ingredients);",
            "CREATE INDEX IF NOT EXISTS ix_recipes_allergens_gin ON recipes USING GIN (allergens);",
        ]:
            await session.execute(text(stmt))
        await session.commit()
        log.info("Indexes created")

        # 5) 검증 — 분포 출력
        from sqlalchemy import func as sa_func
        from sqlalchemy import select
        for col, label in [
            (RecipeRow.country, "country"),
            (RecipeRow.theme, "theme"),
            (RecipeRow.difficulty_level, "difficulty"),
        ]:
            rows = (
                await session.execute(
                    select(col, sa_func.count()).group_by(col).order_by(sa_func.count().desc())
                )
            ).all()
            log.info("%s 분포: %s", label, [(v, c) for v, c in rows])

        total = await session.scalar(select(sa_func.count()).select_from(RecipeRow))
        with_img = await session.scalar(
            select(sa_func.count()).select_from(RecipeRow).where(RecipeRow.image_url.isnot(None))
        )
        log.info("총 레시피: %d, 이미지 보유: %d", total, with_img)

    await engine.dispose()
    log.info("✅ Import complete")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
