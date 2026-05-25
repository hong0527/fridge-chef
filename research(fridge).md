# 냉장고 기능 개선 분석 보고서 (research(fridge).md)

분석 대상: `workList(fridge).md`
비교 기준: `backend/app/api/fridge.py` / `backend/app/core/synonym_map.py` / `frontend/components/FridgeChip.tsx` / `frontend/app/(main)/fridge/page.tsx`
분석 기준: 기존 레이어를 무시하는 함수 여부 / ORM 관례를 무시하는 마이그레이션 여부 / 이미 있는 로직을 중복해서 만든 API 엔드포인트 여부

---

## 분석 요약

| # | 이슈 | 위치 | 심각도 | 분류 |
|---|---|---|---|---|
| RF-01 | 검색 로직이 라우터에서 SYNONYM_MAP 직접 접근 — 서비스 레이어 누락 | 기능 2 (`fridge.py`) | **중** | 레이어 위반 |
| RF-02 | 검색 엔드포인트에 `get_current_user` 인증 없음 — 기존 fridge 라우터와 불일치 | 기능 2 (`fridge.py`) | **중** | 레이어 위반 |
| RF-03 | 편집 원자성 미보장 — `removeIngredient` 성공 후 `addIngredient` 실패 시 재료 소실 | 기능 6 (`fridge/page.tsx`) | **중** | 로직 오류 |
| RF-04 | SYNONYM_MAP 역방향 검색 결과 혼란 — 동의어 입력 시 정규형으로 치환 반환 | 기능 2 (`fridge.py`) | 경 | 로직 모순 |
| RF-05 | 빠른 추가 중복 검사 불완전 — `raw_name`만 비교해 동의어 중복 허용 | 기능 1 (`fridge/page.tsx`) | 경 | 로직 모순 |
| RF-06 | 편집 후 재료 목록 순서 변경 — 편집된 재료가 목록 맨 뒤로 이동 | 기능 6 (`fridge/page.tsx`) | 경 | UX 모순 |
| RF-07 | `categoryColor` 적용 시 기존 어두운 그림자와 밝은 배경 불일치 | 기능 5 (`FridgeChip.tsx`) | 경 | UI 불일치 |

> **ORM 관례 / 마이그레이션**: workList(fridge).md의 7개 기능은 DB 스키마를 변경하지 않는다. `fridge_items` 테이블의 기존 컬럼으로 모든 기능을 구현하므로 Alembic 마이그레이션 이슈는 해당 없음.

---

## 상세 분석

---

### RF-01 — 검색 로직이 라우터에서 SYNONYM_MAP 직접 접근 (심각도: 중)

**분류**: 기존 레이어를 무시하는 함수 여부

**위치**: `workList(fridge).md` 기능 2 (`backend/app/api/fridge.py`)

**문제**:
workList(fridge).md가 제안한 검색 엔드포인트는 라우터(Presentation Layer)에서 `SYNONYM_MAP`을 직접 import해 루프 처리한다.

```python
# workList(fridge).md 제안 코드 — 라우터에서 직접 접근
from app.core.synonym_map import SYNONYM_MAP  # 라우터가 core를 직접 호출

@router.get("/search")
async def search_ingredients(q: str = "") -> dict:
    for synonym, canonical in SYNONYM_MAP.items():  # 비즈니스 로직이 라우터에 존재
        if needle in synonym.lower() and canonical not in seen:
            results.append(canonical)
```

이 프로젝트는 4계층 구조(SDD §1.3)를 따른다.

```
Presentation  → FastAPI 라우터 (HTTP 처리만)
Service       → 비즈니스 로직
Data          → ORM / Repository
```

`SYNONYM_MAP` 순회 및 검색 필터링은 비즈니스 로직이므로 Service Layer인 `fridge_service.py`에 위치해야 한다. 기존 `add_for_user()`도 `fridge_service.py`에서 `normalize()`를 호출하는 패턴을 따른다.

**권장 수정**:

`backend/app/services/fridge_service.py`에 함수 추가:
```python
from app.core.synonym_map import SYNONYM_MAP

def search_ingredient_suggestions(q: str, limit: int = 8) -> list[str]:
    """SYNONYM_MAP 기반 재료 이름 자동완성 (Service Layer)."""
    needle = q.strip().lower()
    if not needle:
        return []
    seen: set[str] = set()
    results: list[str] = []
    for synonym, canonical in SYNONYM_MAP.items():
        if needle in synonym.lower() and canonical not in seen:
            seen.add(canonical)
            results.append(canonical)
        if needle in canonical.lower() and canonical not in seen:
            seen.add(canonical)
            results.append(canonical)
        if len(results) >= limit:
            break
    return results
```

`backend/app/api/fridge.py` 라우터는 서비스만 호출:
```python
@router.get("/search")
async def search_ingredients(
    q: str = "",
    _: User = Depends(get_current_user),  # RF-02 인증 추가
) -> dict:
    results = fridge_service.search_ingredient_suggestions(q)
    return {"suggestions": results}
```

---

### RF-02 — 검색 엔드포인트 인증 없음 (심각도: 중)

**분류**: 기존 레이어를 무시하는 함수 여부

**위치**: `workList(fridge).md` 기능 2 (`backend/app/api/fridge.py`)

**문제**:
기존 fridge 라우터의 모든 엔드포인트는 `Depends(get_current_user)`가 필수다.

```python
# 기존 fridge.py — 모든 엔드포인트에 인증 적용
@router.get("", ...)
async def list_ingredients(user: User = Depends(get_current_user), ...):

@router.post("", ...)
async def create_ingredient(... user: User = Depends(get_current_user), ...):

@router.delete("/{ingredient_id}", ...)
async def delete_ingredient(... user: User = Depends(get_current_user), ...):
```

workList(fridge).md의 제안 코드:
```python
# 인증 없음 — 기존 패턴과 불일치
@router.get("/search")
async def search_ingredients(q: str = "") -> dict:
    ...
```

미인증 상태에서 자유롭게 재료명 검색 쿼리를 보낼 수 있다. SYNONYM_MAP 데이터가 외부에 노출되며, rate limiting도 없어 반복 조회를 막을 수 없다. 기존 fridge 라우터의 설계 원칙과도 불일치한다.

**권장 수정**:
```python
@router.get("/search")
async def search_ingredients(
    q: str = "",
    _: User = Depends(get_current_user),  # 기존 패턴과 동일하게 인증 추가
) -> dict:
    results = fridge_service.search_ingredient_suggestions(q)
    return {"suggestions": results}
```

---

### RF-03 — 편집 원자성 미보장 (심각도: 중)

**분류**: 로직 오류

**위치**: `workList(fridge).md` 기능 6 (`frontend/app/(main)/fridge/page.tsx`)

**문제**:
인라인 편집 로직이 기존 재료 삭제 후 새 재료 추가의 2단계로 구현된다.

```tsx
// workList(fridge).md 제안 코드
const handleEditSubmit = async (id: number) => {
  try:
    await removeIngredient(id);       // 1단계: 삭제 성공
    const added = await addIngredient(newName);  // 2단계: 추가 실패 가능
    setIngredients((prev) => [...prev.filter((i) => i.id !== id), added]);
  } catch (err) {
    toast.show(apiErrorMessage(err), 'error');
  }
};
```

`removeIngredient(id)` 성공 후 `addIngredient(newName)`이 네트워크 오류, 서버 오류, 인증 만료 등으로 실패하면 기존 재료는 이미 DB에서 삭제됐고 새 재료는 추가되지 않는다. 사용자 입장에서 재료가 영구 소실된다. catch 블록이 있지만 이 시점에서는 이미 삭제가 완료된 상태이므로 롤백이 불가능하다.

**권장 수정**:
추가 먼저 → 성공 시 삭제의 순서로 변경해 실패 시 기존 재료 보존:
```tsx
const handleEditSubmit = async (id: number) => {
  const newName = editValue.trim();
  const original = ingredients.find((i) => i.id === id);
  if (!newName || !original || newName === original.raw_name) {
    setEditingId(null);
    return;
  }
  try {
    // 1단계: 새 재료 추가 먼저 (실패해도 기존 재료 보존)
    const added = await addIngredient(newName);
    // 2단계: 추가 성공 후 기존 재료 삭제
    await removeIngredient(id);
    setIngredients((prev) => [...prev.filter((i) => i.id !== id), added]);
    toast.show(`'${original.raw_name}' → '${newName}' 수정됨`, 'success');
  } catch (err) {
    toast.show(apiErrorMessage(err), 'error');
  } finally {
    setEditingId(null);
  }
};
```

---

### RF-04 — SYNONYM_MAP 역방향 검색 결과 혼란 (심각도: 경)

**분류**: 로직 모순

**위치**: `workList(fridge).md` 기능 2 (`backend/app/api/fridge.py`)

**문제**:
백엔드 `SYNONYM_MAP`은 `동의어 → 정규형` 방향으로 저장되어 있다.

```python
# backend/app/core/synonym_map.py
SYNONYM_MAP = {
    "달걀": "계란",      # 동의어 → 정규형
    "삼겹살": "돼지고기",
    "왕새우": "새우",
    ...
}
```

workList(fridge).md의 검색 로직:
```python
for synonym, canonical in SYNONYM_MAP.items():
    if needle in synonym.lower():
        results.append(canonical)  # "달" 입력 → "달걀" 발견 → "계란" 반환
```

사용자가 "달"을 입력하면 자동완성에 "계란"이 표시된다. 사용자가 기대하는 "달걀"이 아닌 정규형이 반환되어 혼란을 준다. 사용자가 "달걀"을 선택하고 싶어도 "계란"만 보인다.

**권장 수정**:
동의어 자체도 제안 목록에 포함하거나, 정규형과 매칭되는 동의어를 함께 반환:
```python
for synonym, canonical in SYNONYM_MAP.items():
    if needle in synonym.lower():
        # 동의어를 그대로 반환 (사용자가 입력하던 형태)
        if synonym not in seen:
            seen.add(synonym)
            results.append(synonym)
    if needle in canonical.lower():
        if canonical not in seen:
            seen.add(canonical)
            results.append(canonical)
```

---

### RF-05 — 빠른 추가 중복 검사 불완전 (심각도: 경)

**분류**: 로직 모순

**위치**: `workList(fridge).md` 기능 1 (`frontend/app/(main)/fridge/page.tsx`)

**문제**:
빠른 추가 버튼의 중복 검사가 `raw_name`만 확인한다.

```tsx
// workList(fridge).md 제안 코드
const added = ingredients.some((i) => i.raw_name === name);
```

사용자가 "달걀"을 직접 타이핑해 추가하면 DB에 `raw_name: "달걀"`, `normalized_name: "계란"`으로 저장된다. 이후 빠른 추가 버튼에서 "계란"을 클릭하면 `ingredients.some((i) => i.raw_name === "계란")`이 `false`를 반환해 버튼이 활성화된다. 클릭 시 "계란"이 추가되어 냉장고에 "달걀"과 "계란" 두 개가 공존한다. 추천 필터에서 동일한 `normalized_name: "계란"`을 가진 재료가 중복으로 처리된다.

**권장 수정**:
`normalized_name`도 함께 비교:
```tsx
const normalizedName = name; // 빠른 추가 버튼의 이름은 이미 정규형
const added = ingredients.some(
  (i) => i.raw_name === name || i.normalized_name === normalizedName
);
```

---

### RF-06 — 편집 후 재료 목록 순서 변경 (심각도: 경)

**분류**: UX 모순

**위치**: `workList(fridge).md` 기능 6 (`frontend/app/(main)/fridge/page.tsx`)

**문제**:
편집 완료 후 재료를 목록 마지막에 추가한다.

```tsx
// workList(fridge).md 제안 코드
setIngredients((prev) => [...prev.filter((i) => i.id !== id), added]);
//                                                              ↑ 맨 뒤에 추가
```

냉장고에 재료가 10개 있을 때 3번째 재료를 편집하면 편집 완료 후 해당 재료가 10번째로 이동한다. 사용자는 편집한 재료가 사라진 것처럼 느낄 수 있고, 스크롤해 찾아야 한다.

**권장 수정**:
원래 위치(index)를 기억해 동일 위치에 삽입:
```tsx
const handleEditSubmit = async (id: number) => {
  const originalIndex = ingredients.findIndex((i) => i.id === id);
  ...
  const added = await addIngredient(newName);
  await removeIngredient(id);
  setIngredients((prev) => {
    const next = prev.filter((i) => i.id !== id);
    next.splice(originalIndex, 0, added);  // 원래 위치에 삽입
    return next;
  });
};
```

---

### RF-07 — `categoryColor` 적용 시 그림자 색상 불일치 (심각도: 경)

**분류**: UI 불일치

**위치**: `workList(fridge).md` 기능 5 (`frontend/components/FridgeChip.tsx`)

**문제**:
기존 `FridgeChip`에는 어두운 고정 색상의 그림자가 적용되어 있다.

```tsx
// 기존 FridgeChip.tsx
variant !== 'compact' && 'shadow-[0_2px_0_0_rgba(26,23,21,0.85)]'
// rgba(26,23,21) = 거의 검정에 가까운 어두운 색
```

workList(fridge).md의 categoryColor 스타일:
```tsx
vegetable: 'border-green-600 bg-green-50 ...',  // 밝은 초록 배경
meat:      'border-red-500  bg-red-50  ...',     // 밝은 빨강 배경
```

밝은 파스텔 계열 배경(bg-green-50, bg-red-50 등)에 거의 검정에 가까운 그림자가 적용되면 기존 default 칩(bg-cream-50)보다 시각적으로 과도하게 강조된다. 기존 그림자 색은 clay-900(다크 브라운)과 잘 어울리도록 설계됐지만, 컬러 배경에서는 어색해 보일 수 있다.

**권장 수정**:
`categoryColor` 지정 시 그림자 생략 또는 카테고리 색상에 맞는 그림자 적용:
```tsx
// categoryColor가 있을 때 그림자 제거
variant !== 'compact' && !categoryColor && 'shadow-[0_2px_0_0_rgba(26,23,21,0.85)]',
```

---

## ORM 관례 / 마이그레이션 분석

workList(fridge).md의 7개 기능은 **DB 스키마를 변경하지 않는다.**

| 기능 | DB 변경 | 근거 |
|---|---|---|
| 기능 1 — 빠른 추가 버튼 | 없음 | 기존 `addIngredient` API 재사용 |
| 기능 2 — 서버 자동완성 | 없음 | SYNONYM_MAP(인메모리) 검색, DB 조회 없음 |
| 기능 3 — 기본 양념 토글 | 없음 | 기존 `addIngredient` / `removeIngredient` 반복 |
| 기능 4 — 빈 상태 개선 | 없음 | 순수 UI 변경 |
| 기능 5 — 카테고리 색상 | 없음 | 순수 UI 변경 |
| 기능 6 — 인라인 편집 | 없음 | 삭제+추가 조합, 기존 API 재사용 |
| 기능 7 — 선택 삭제 | 없음 | 기존 `removeIngredient` 반복 |

**Alembic 마이그레이션 불필요** — 기존 `fridge_items` 테이블의 컬럼으로 모두 처리 가능.

---

## 이미 있는 로직을 중복해서 만든 API 엔드포인트 분석

| 신규 엔드포인트 | 기존 유사 로직 | 중복 여부 |
|---|---|---|
| `GET /api/fridge/search` | `frontend/lib/synonyms.ts`의 `localSuggest()` | **중복 아님** — 로컬은 40개, 서버는 100쌍 전체. 서버가 더 풍부한 결과 제공 |
| `GET /api/fridge/search` | `backend/core/synonym_map.py`의 `normalize()` | **중복 아님** — `normalize()`는 단방향 변환, search는 양방향 prefix 검색. 목적이 다름 |

신규 검색 엔드포인트는 기존 로직과 중복되지 않는다. 단, RF-01에서 지적한 것처럼 **비즈니스 로직의 위치**(라우터 vs 서비스)가 문제이지 중복 자체는 아니다.

---

## NFR 확인

| NFR | 영향 여부 | 근거 |
|---|---|---|
| NFR-PERF-001 | 영향 없음 | 레시피 목록 페이지 미변경 |
| NFR-PERF-002 | 영향 없음 | 추천 모델 A 미변경 |
| NFR-PERF-003 | 영향 없음 | 추천 모델 B 미변경 |
| NFR-SEC-001 | 영향 없음 | bcrypt 관련 코드 미변경 |
| NFR-SEC-002 | 영향 없음 | Gemini API 키 관련 미변경 |
| NFR-SEC-003 | **주의** | RF-02: 검색 엔드포인트 인증 없음. 단, 검색은 민감 데이터를 반환하지 않아 직접적인 NFR-SEC 위반은 아님 |
| NFR-USE-001 | **개선** | 기능 1(빠른 추가), 기능 3(양념 토글)으로 재료 등록 시간 단축 → 3분 이내 추천 흐름 개선 |
| NFR-USE-002 | 만족 | 신규 UI 요소들이 `flex flex-wrap` 반응형 패턴 사용 |
| NFR-REL-001 | 영향 없음 | Gemini 폴백 로직 미변경 |

---

## 수정 우선순위

| 우선순위 | 이슈 | 조치 |
|---|---|---|
| **즉시 수정** | RF-03 (편집 원자성) | 추가 먼저 → 성공 후 삭제 순서로 변경 |
| **즉시 수정** | RF-01 (검색 로직 레이어) | `fridge_service.py`에 `search_ingredient_suggestions()` 분리 |
| **즉시 수정** | RF-02 (검색 인증 없음) | `Depends(get_current_user)` 추가 |
| 작업 전 수정 | RF-04 (역방향 검색 혼란) | 동의어 자체를 결과에 포함 |
| 작업 전 수정 | RF-05 (중복 검사 불완전) | `normalized_name` 비교 추가 |
| 병행 처리 | RF-06 (편집 후 순서 변경) | `splice(originalIndex, 0, added)` 적용 |
| 나중에 보완 | RF-07 (그림자 색상 불일치) | `categoryColor` 지정 시 그림자 제거 |
